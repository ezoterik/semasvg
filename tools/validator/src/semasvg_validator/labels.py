from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
from xml.sax.saxutils import escape

from .validator import PROJECT_MANIFEST_NAME, validate_project_manifest

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
TEXT_TAG = f"{{{SVG_NAMESPACE}}}text"
EXPAT_TEXT_TAG = f"{SVG_NAMESPACE}}}text"
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_:][A-Za-z0-9_.:-]*)\}")


@dataclass(frozen=True)
class LabelIssue:
    file: Path
    label_id: str | None
    message: str
    code: str | None = None

    def render(self, base: Path | None = None) -> str:
        file = self.file
        if base is not None:
            try:
                file = file.relative_to(base)
            except ValueError:
                pass
        location = str(file)
        if self.label_id is not None:
            location += f"#{self.label_id}"
        code = f" {self.code}" if self.code is not None else ""
        return f"ERROR label{code} {location}: {self.message}"


@dataclass(frozen=True)
class MaterializeLabelsResult:
    issues: list[LabelIssue]
    stale_labels: int
    updated_files: int


def find_text_spans(
    source: bytes,
    label_ids: set[str],
) -> tuple[dict[str, list[tuple[int, int]]], set[str]]:
    spans: dict[str, list[tuple[int, int]]] = {}
    self_closing_labels: set[str] = set()
    active_labels: list[tuple[str, int]] = []
    parser = expat.ParserCreate(namespace_separator="}")

    def start_element(name: str, attributes: dict[str, str]) -> None:
        if name != EXPAT_TEXT_TAG:
            return
        label_id = attributes.get("id")
        if label_id not in label_ids:
            return
        content_start = find_start_tag_end(source, parser.CurrentByteIndex)
        if source[parser.CurrentByteIndex:content_start].rstrip().endswith(b"/>"):
            self_closing_labels.add(label_id)
            return
        active_labels.append((label_id, content_start))

    def end_element(name: str) -> None:
        if name != EXPAT_TEXT_TAG or not active_labels:
            return
        label_id, content_start = active_labels.pop()
        spans.setdefault(label_id, []).append((content_start, parser.CurrentByteIndex))

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.Parse(source, True)
    return spans, self_closing_labels


def find_start_tag_end(source: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start, len(source)):
        character = source[index]
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {ord("\""), ord("'")}:
            quote = character
        elif character == ord(">"):
            return index + 1
    raise ValueError("unterminated XML start tag")


def materialize_labels(path: Path, check: bool = False) -> MaterializeLabelsResult:
    # A dangling symlink does not exist() but is still an authored unsafe target.
    if path.is_symlink():
        return MaterializeLabelsResult(
            [LabelIssue(path, None, "symlinked targets are not allowed")],
            0,
            0,
        )
    if not path.exists():
        return MaterializeLabelsResult(
            [LabelIssue(path, None, "target path does not exist")],
            0,
            0,
        )

    files, selection_issues = select_label_files(path)
    if selection_issues:
        return MaterializeLabelsResult(selection_issues, 0, 0)
    issues: list[LabelIssue] = []
    replacements: dict[Path, list[tuple[int, int, bytes]]] = {}

    for file in files:
        try:
            source_bytes = file.read_bytes()
            source = source_bytes.decode("utf-8")
            root = ET.fromstring(source)
        except (OSError, UnicodeDecodeError, ET.ParseError) as error:
            issues.append(LabelIssue(file, None, f"cannot parse SVG: {error}"))
            continue

        entities: dict[str, list[ET.Element]] = {}
        for element in root.iter():
            entity = element.get("data-sema-entity")
            if entity is not None:
                entities.setdefault(entity, []).append(element)

        derived_labels = [
            label
            for label in root.iter(TEXT_TAG)
            if label.get("data-sema-type") == "core:label"
            and label.get("data-sema-x-label-template") is not None
        ]
        try:
            # ElementTree resolves semantic attributes; Expat keeps byte offsets for surgical source edits.
            source_spans, self_closing_labels = find_text_spans(
                source_bytes,
                {label_id for label in derived_labels if (label_id := label.get("id")) is not None},
            )
        except (ValueError, expat.ExpatError) as error:
            issues.append(LabelIssue(file, None, f"cannot locate XML text spans: {error}"))
            continue
        file_replacements: list[tuple[int, int, bytes]] = []
        for label in derived_labels:
            template = label.get("data-sema-x-label-template")
            assert template is not None

            label_id = label.get("id")
            target_id = label.get("data-sema-for")
            if label_id is None:
                issues.append(LabelIssue(file, None, "derived label requires an SVG id"))
                continue
            if label_id in self_closing_labels:
                issues.append(LabelIssue(file, label_id, "derived label must not be self-closing"))
                continue
            if target_id is None or target_id == "":
                issues.append(LabelIssue(file, label_id, "derived label requires data-sema-for"))
                continue
            if len(label) != 0:
                issues.append(LabelIssue(file, label_id, "derived label must not contain nested markup"))
                continue

            target_matches = entities.get(target_id, [])
            if len(target_matches) != 1:
                issues.append(
                    LabelIssue(file, label_id, f"data-sema-for target '{target_id}' must resolve exactly once")
                )
                continue

            attributes = PLACEHOLDER_RE.findall(template)
            literal = PLACEHOLDER_RE.sub("", template)
            if "{" in literal or "}" in literal or not attributes:
                issues.append(LabelIssue(file, label_id, "invalid data-sema-x-label-template placeholder syntax"))
                continue

            target = target_matches[0]
            missing = [attribute for attribute in attributes if target.get(attribute) is None]
            if missing:
                issues.append(
                    LabelIssue(file, label_id, f"target '{target_id}' is missing attribute '{missing[0]}'")
                )
                continue

            generated = PLACEHOLDER_RE.sub(lambda match: target.get(match.group(1), ""), template)
            current = label.text or ""
            if current == generated:
                continue

            spans = source_spans.get(label_id, [])
            if len(spans) != 1:
                issues.append(LabelIssue(file, label_id, "cannot locate direct source text for derived label"))
                continue
            content_start, content_end = spans[0]
            file_replacements.append((content_start, content_end, escape(generated).encode("utf-8")))

        if file_replacements:
            replacements[file] = file_replacements

    # A complete scan must succeed before materialization can change any source file.
    if issues or check:
        return MaterializeLabelsResult(issues, sum(len(items) for items in replacements.values()), 0)

    for file, file_replacements in replacements.items():
        source = file.read_bytes()
        # Later spans stay valid while replacements are applied from the end of the source.
        for content_start, content_end, replacement in sorted(file_replacements, reverse=True):
            source = source[:content_start] + replacement + source[content_end:]
        file.write_bytes(source)

    return MaterializeLabelsResult([], sum(len(items) for items in replacements.values()), len(replacements))


def select_label_files(path: Path) -> tuple[list[Path], list[LabelIssue]]:
    """Select label sources without letting undeclared project files affect a batch."""
    if path.is_symlink():
        return [], [LabelIssue(path, None, "symlinked targets are not allowed")]

    if path.is_file() and path.name == PROJECT_MANIFEST_NAME:
        manifest, views, manifest_issues = validate_project_manifest(path)
        issues = [
            LabelIssue(issue.file, None, issue.message, issue.code)
            for issue in manifest_issues
            if issue.severity == "ERROR"
        ]
        if manifest is None or issues:
            return [], issues
        files: list[Path] = []
        for view, file in views:
            # validate_project_manifest resolves views; retain authored-path symlink evidence.
            authored = path.parent / view["file"]
            if authored.is_symlink() or not is_regular_svg(file):
                issues.append(LabelIssue(authored, None, "target must be a regular non-symlink SVG file"))
            else:
                files.append(file)
        if issues:
            return [], issues
        if not files:
            return [], [LabelIssue(path, None, "no SVG files selected")]
        return files, []

    if path.is_dir():
        manifest = path / PROJECT_MANIFEST_NAME
        if manifest.is_symlink():
            return [], [LabelIssue(manifest, None, "symlinked targets are not allowed")]
        if manifest.is_file():
            return select_label_files(manifest)

    if path.is_file():
        if not is_regular_svg(path):
            return [], [LabelIssue(path, None, "target must be a regular non-symlink SVG file")]
        return [path], []

    if not path.is_dir():
        return [], [LabelIssue(path, None, "target must be a directory")]

    files: list[Path] = []
    issues: list[LabelIssue] = []
    for candidate in sorted(path.rglob("*.svg")):
        relative = candidate.relative_to(path)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if candidate.is_symlink():
            issues.append(LabelIssue(candidate, None, "symlinked SVG targets are not allowed"))
        elif candidate.is_file():
            files.append(candidate)
    if not files and not issues:
        return [], [LabelIssue(path, None, "no SVG files selected")]
    return sorted(files), issues


def is_regular_svg(path: Path) -> bool:
    return path.suffix.lower() == ".svg" and not path.is_symlink() and path.is_file()
