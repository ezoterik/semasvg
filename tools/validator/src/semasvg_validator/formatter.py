from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
import tempfile
from xml.parsers import expat

from .validator import PROJECT_MANIFEST_NAME, validate_project_manifest


PRESERVED_CONTENT = {"text", "tspan", "textPath", "title", "desc", "metadata", "style", "script", "foreignObject"}


@dataclass(frozen=True)
class FormatIssue:
    file: Path
    message: str

    def render(self, base: Path) -> str:
        try:
            name = self.file.relative_to(base)
        except ValueError:
            name = self.file
        return f"ERROR format {name}: {self.message}"


@dataclass(frozen=True)
class FormatResult:
    issues: list[FormatIssue]
    stale_files: int
    updated_files: int


@dataclass
class Element:
    name: str
    start: int
    start_end: int
    end: int | None = None
    end_end: int | None = None
    children: list["Element"] = field(default_factory=list)
    xml_space: str | None = None
    xml_space_preserve: bool = False
    inherited_preserve: bool = False
    preserve: bool = False
    mixed: bool = False


def _tag_end(source: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start, len(source)):
        character = source[index]
        if quote is not None:
            if character == quote:
                quote = None
        elif character in (ord("'"), ord('"')):
            quote = character
        elif character == ord(">"):
            return index + 1
    raise ValueError("unterminated XML tag")


def _attributes(tag: bytes) -> tuple[bytes, list[bytes], bool]:
    """Split a start tag without decoding values, preserving every lexical spelling."""
    body = tag[1:-1]
    self_closing = body.rstrip().endswith(b"/")
    if self_closing:
        body = body.rstrip()[:-1]
    position = 0
    while position < len(body) and not body[position:position + 1].isspace():
        position += 1
    name = body[:position]
    attributes: list[bytes] = []
    while position < len(body):
        while position < len(body) and body[position:position + 1].isspace():
            position += 1
        if position >= len(body):
            break
        start = position
        while position < len(body) and body[position:position + 1] not in b"= \t\r\n":
            position += 1
        while position < len(body) and body[position:position + 1].isspace():
            position += 1
        if position >= len(body) or body[position] != ord("="):
            raise ValueError("malformed XML attribute")
        position += 1
        while position < len(body) and body[position:position + 1].isspace():
            position += 1
        if position >= len(body) or body[position] not in (ord("'"), ord('"')):
            raise ValueError("malformed XML attribute value")
        quote = body[position]
        position += 1
        while position < len(body) and body[position] != quote:
            position += 1
        if position >= len(body):
            raise ValueError("unterminated XML attribute value")
        position += 1
        attributes.append(body[start:position])
    return name, attributes, self_closing


def _markup_chunks(raw: bytes) -> list[bytes] | None:
    """Return standalone comments and PIs, or None when the gap contains content."""
    chunks: list[bytes] = []
    position = 0
    while position < len(raw):
        while position < len(raw) and raw[position:position + 1].isspace():
            position += 1
        if position == len(raw):
            return chunks
        if raw.startswith(b"<!--", position):
            terminator = b"-->"
            search_from = position + 4
        elif raw.startswith(b"<?", position):
            terminator = b"?>"
            search_from = position + 2
        else:
            return None
        end = raw.find(terminator, search_from)
        if end < 0:
            return None
        chunks.append(raw[position:end + len(terminator)])
        position = end + len(terminator)
    return chunks


def _format_plain_style_content(content: bytes, depth: int) -> bytes | None:
    """Normalize only multiline CSS boundary indentation without parsing CSS tokens."""
    if not content.startswith(b"\n") or not content.endswith(b"\n"):
        return None
    if any(marker in content for marker in (b"<![CDATA[", b"<?", b"<!--")):
        return None

    lines = content[1:-1].split(b"\n")
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        return None

    def leading_width(line: bytes) -> int:
        return len(line) - len(line.lstrip(b" \t"))

    common_indent = min(leading_width(line) for line in nonempty)
    prefix = b" " * ((depth + 1) * 2)
    normalized = [prefix + line[common_indent:] if line.strip() else b"" for line in lines]
    return b"\n" + b"\n".join(normalized) + b"\n"


def _format_start_tag(raw: bytes, indent: int, force_expanded: bool) -> bytes:
    name, attributes, self_closing = _attributes(raw)
    suffix = b"/>" if self_closing else b">"
    prefix = b" " * indent + b"<" + name
    if not attributes:
        return prefix + suffix
    compact = prefix + b" " + b" ".join(attributes) + suffix
    if not force_expanded and len(compact) <= 120:
        return compact

    # A leading namespace declaration or id helps identify the element at a glance.
    # Keep only the original leading run; moving a later attribute would alter order.
    leading: list[bytes] = []
    for attribute in attributes:
        attribute_name = attribute.split(b"=", 1)[0]
        if attribute_name == b"id" or attribute_name == b"xmlns" or attribute_name.startswith(b"xmlns:"):
            candidate = prefix + b" " + b" ".join(leading + [attribute])
            if len(candidate) + len(suffix) <= 120:
                leading.append(attribute)
                continue
        break
    if leading:
        prefix += b" " + b" ".join(leading)
        attributes = attributes[len(leading):]
    if not attributes:
        return prefix + suffix
    lines = [prefix]
    # Continuations align with the first attribute position after the element name,
    # even when a leading id or namespace declaration remains on the opening line.
    aligned = b" " * (indent + len(name.decode("utf-8")) + 2)
    line = aligned
    for attribute in attributes:
        is_sema = attribute.startswith(b"data-sema-")
        if is_sema:
            if line != aligned:
                lines.append(line)
            lines.append(aligned + attribute)
            line = aligned
            continue
        candidate = line + (b"" if line == aligned else b" ") + attribute
        if line != aligned and len(candidate) + len(suffix) > 120:
            lines.append(line)
            line = aligned + attribute
        else:
            line = candidate
    if line != aligned:
        lines.append(line)
    lines[-1] += suffix
    return b"\n".join(lines)


def _parse_tree(source: bytes) -> Element:
    # Expat validates XML while CurrentByteIndex lets the renderer retain lexical source.
    parser = expat.ParserCreate()
    stack: list[Element] = []
    root: Element | None = None

    def start(name: str, attributes: dict[str, str]) -> None:
        nonlocal root
        offset = parser.CurrentByteIndex
        node = Element(
            name.rsplit("}", 1)[-1].rsplit(":", 1)[-1],
            offset,
            _tag_end(source, offset),
            xml_space=attributes.get("xml:space"),
        )
        if stack:
            stack[-1].children.append(node)
        else:
            root = node
        stack.append(node)

    def end(_name: str) -> None:
        node = stack.pop()
        if source[node.start:node.start_end].rstrip().endswith(b"/>"):
            node.end = node.start_end
            node.end_end = node.start_end
            return
        node.end = parser.CurrentByteIndex
        node.end_end = _tag_end(source, node.end)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(source, True)
    if root is None:
        raise ValueError("XML document has no root element")

    def mark(node: Element, inherited_preserve: bool, inherited_xml_space_preserve: bool) -> None:
        node.inherited_preserve = inherited_preserve
        node.xml_space_preserve = inherited_xml_space_preserve or node.xml_space == "preserve"
        preserve = (
            inherited_preserve
            or node.name in PRESERVED_CONTENT
            or node.xml_space_preserve
        )
        node.preserve = preserve
        cursor = node.start_end
        for child in node.children:
            if _markup_chunks(source[cursor:child.start]) is None:
                node.mixed = True
            cursor = child.end_end or cursor
        if node.end is not None and _markup_chunks(source[cursor:node.end]) is None:
            node.mixed = True
        for child in node.children:
            mark(child, preserve, node.xml_space_preserve)

    mark(root, False, False)
    return root


def format_svg(source: bytes) -> bytes:
    """Format only structural whitespace after Expat has validated source offsets."""
    source.decode("utf-8")
    root = _parse_tree(source)

    def render(node: Element, depth: int) -> bytes:
        raw_start = source[node.start:node.start_end]
        force_expanded = node.name == "svg" or b"data-sema-" in raw_start
        opening = _format_start_tag(raw_start, depth * 2, force_expanded)
        if node.preserve or node.mixed:
            # Content can be text-like or mixed; only the boundary tag is safe to move.
            if node.name == "style" and not node.inherited_preserve and not node.xml_space_preserve and node.end is not None:
                content = _format_plain_style_content(source[node.start_end:node.end], depth)
                if content is not None:
                    return opening + content + b" " * (depth * 2) + source[node.end:node.end_end]
            return opening + source[node.start_end:node.end_end]
        if node.end == node.start_end:
            return opening
        if not node.children:
            chunks = _markup_chunks(source[node.start_end:node.end])
            if chunks:
                indented = [b" " * ((depth + 1) * 2) + chunk for chunk in chunks]
                return b"\n".join([opening, *indented]) + b"\n" + b" " * (depth * 2) + source[node.end:node.end_end]
            return opening + source[node.start_end:node.end] + source[node.end:node.end_end]
        content: list[bytes] = [opening]
        cursor = node.start_end
        for child in node.children:
            chunks = _markup_chunks(source[cursor:child.start])
            if chunks:
                content.extend(b" " * ((depth + 1) * 2) + chunk for chunk in chunks)
            content.append(render(child, depth + 1))
            cursor = child.end_end or cursor
        chunks = _markup_chunks(source[cursor:node.end])
        if chunks:
            content.extend(b" " * ((depth + 1) * 2) + chunk for chunk in chunks)
        return b"\n".join(content) + b"\n" + b" " * (depth * 2) + source[node.end:node.end_end]

    before = source[:root.start]
    after = source[root.end_end:]
    # Keep declarations, DOCTYPE, comments and PIs outside the root byte-for-byte.
    rendered = before + render(root, 0) + after
    return rendered if rendered.endswith(b"\n") else rendered + b"\n"


def _regular_svg(path: Path) -> bool:
    return path.suffix.lower() == ".svg" and not path.is_symlink() and path.is_file()


def _select_files(path: Path) -> tuple[list[Path], list[FormatIssue]]:
    if not path.exists():
        return [], [FormatIssue(path, "target path does not exist")]
    if path.is_symlink():
        return [], [FormatIssue(path, "symlinked targets are not allowed")]
    if path.is_file():
        if path.name == PROJECT_MANIFEST_NAME:
            manifest, views, issues = validate_project_manifest(path)
            errors = [FormatIssue(issue.file, issue.message) for issue in issues if issue.severity == "ERROR"]
            files = [file for _, file in views if _regular_svg(file)] if manifest is not None and not errors else []
            if manifest is not None:
                for view, file in views:
                    authored = path.parent / view["file"]
                    # validate_project_manifest resolves views; retain authored-path symlink evidence.
                    if authored.is_symlink() or not _regular_svg(file):
                        errors.append(FormatIssue(authored, "target must be a regular non-symlink SVG file"))
            return files, errors or ([] if files else [FormatIssue(path, "no SVG files selected")])
        if not _regular_svg(path):
            return [], [FormatIssue(path, "target must be a regular non-symlink SVG file")]
        return [path], []
    if not path.is_dir() or path.is_symlink():
        return [], [FormatIssue(path, "target must be a directory")]
    manifest = path / PROJECT_MANIFEST_NAME
    if manifest.is_file():
        return _select_files(manifest)
    selected: list[Path] = []
    issues: list[FormatIssue] = []
    for candidate in path.rglob("*.svg"):
        relative = candidate.relative_to(path)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if candidate.is_symlink():
            issues.append(FormatIssue(candidate, "symlinked SVG targets are not allowed"))
        elif candidate.is_file():
            selected.append(candidate)
    if not selected and not issues:
        issues.append(FormatIssue(path, "no SVG files selected"))
    return sorted(selected), issues


def _atomic_write(path: Path, content: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        # Replacement is atomic for this file only; callers intentionally do not promise batch rollback.
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def format_path(path: Path, check: bool = False) -> FormatResult:
    files, issues = _select_files(path)
    rendered: dict[Path, bytes] = {}
    # Complete every read and parse before any write can change a selected source.
    for file in files:
        try:
            source = file.read_bytes()
            output = format_svg(source)
        except (OSError, UnicodeDecodeError, ValueError, expat.ExpatError) as error:
            issues.append(FormatIssue(file, f"cannot format SVG: {error}"))
            continue
        if output != source:
            rendered[file] = output
    if issues or check:
        return FormatResult(issues, len(rendered), 0)
    updated = 0
    for file, output in rendered.items():
        try:
            _atomic_write(file, output)
            updated += 1
        except OSError as error:
            issues.append(FormatIssue(file, f"cannot write formatted SVG: {error}"))
    return FormatResult(issues, len(rendered), updated)
