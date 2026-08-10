from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from importlib.resources import files
import json
import math
import re
from typing import cast
import xml.etree.ElementTree as ET

from jsonschema import Draft202012Validator
import yaml

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

REQUIRED_ROOT = (
    "data-sema-version",
    "data-sema-project",
    "data-sema-view",
    "data-sema-view-kind",
    "data-sema-coordinate-mode",
    "data-sema-profiles",
)

QTYPE_RE = re.compile(r"^[a-z][a-z0-9.-]*:[a-z][a-z0-9-]*$")
PROFILE_DECLARATION_RE = re.compile(
    r"^(?P<profile>[a-z][a-z0-9.-]*)@(?P<version>\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)$"
)
INTEGER_RE = re.compile(r"^[+-]?\d+$")
PROJECT_MANIFEST_NAME = "semasvg.project.yaml"
SUPPORTED_SEMASVG_VERSION = "0.1.0"
OFFICIAL_VOCABULARY_FILES = {
    "core": "core.yaml",
    "building": "profiles/building.yaml",
    "electrical": "profiles/electrical.yaml",
}
# Deliberately limited to stable entity facts; local annotations and derived values are not compared.
CONSISTENT_ENTITY_ATTRIBUTES = (
    "data-sema-rated-current-a",
    "data-sema-voltage-v",
    "data-sema-poles",
    "data-sema-manufacturer",
    "data-sema-model",
)

ManifestView = tuple[dict[str, str], Path]
LINK_HREF_ATTRS = {"href", f"{{{XLINK_NS}}}href"}
# Browsers can normalize ASCII controls and spaces while parsing URI schemes.
URI_NORMALIZATION_CHARS = "".join(chr(code) for code in range(0x21))


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    file: Path
    message: str
    element_id: str | None = None

    def render(self, base: Path | None = None) -> str:
        file = self.file
        if base is not None:
            try:
                file = file.relative_to(base)
            except ValueError:
                pass
        where = str(file)
        if self.element_id:
            where += f"#{self.element_id}"
        return f"{self.severity} {self.code} {where}: {self.message}"


@dataclass
class ParsedSvg:
    file: Path
    root: ET.Element
    project: str
    profiles: dict[str, str]
    entities: dict[str, str]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def is_javascript_uri(value: str) -> bool:
    normalized = "".join(char for char in value if char not in URI_NORMALIZATION_CHARS)
    return normalized.lower().startswith("javascript:")


def collect_svg_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.rglob("*.svg")
        if not any(part.startswith(".") for part in p.parts)
    )


def collect_yaml_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.rglob("*")
        if p.suffix in {".yaml", ".yml"} and not any(part.startswith(".") for part in p.parts)
    )


def load_schema(name: str) -> dict[str, object]:
    # Installed validators must not depend on a source-checkout-relative schema path.
    schema = files("semasvg_validator.schemas").joinpath(name)
    return json.loads(schema.read_text(encoding="utf-8"))


def load_official_vocabularies() -> dict[str, dict[str, object]]:
    vocabularies: dict[str, dict[str, object]] = {}
    # Profile conformance must use the registry shipped with an installed validator.
    resource_root = files("semasvg_validator.vocab")
    for profile, relative_path in OFFICIAL_VOCABULARY_FILES.items():
        vocabulary = yaml.safe_load(resource_root.joinpath(relative_path).read_text(encoding="utf-8"))
        vocabularies[profile] = cast(dict[str, object], vocabulary)
    return vocabularies


OFFICIAL_VOCABULARIES = load_official_vocabularies()


def parse_profile_declarations(file: Path, raw: str) -> tuple[dict[str, str], list[Issue]]:
    profiles: dict[str, str] = {}
    issues: list[Issue] = []
    for token in raw.split():
        match = PROFILE_DECLARATION_RE.fullmatch(token)
        if match is None:
            issues.append(Issue("ERROR", "E104", file, f"malformed profile declaration {token!r}"))
            continue

        profile = match["profile"]
        version = match["version"]
        if profile == "core":
            issues.append(Issue("ERROR", "E106", file, "Core is implicit and must not be declared as a profile"))
            continue
        profiles[profile] = version
        if profile in OFFICIAL_VOCABULARIES:
            supported_version = cast(str, OFFICIAL_VOCABULARIES[profile]["version"])
            if version != supported_version:
                issues.append(Issue(
                    "ERROR",
                    "E105",
                    file,
                    f"unsupported {profile!r} profile version {version!r}",
                ))

    return profiles, issues


def active_vocabulary_names(profiles: dict[str, str]) -> tuple[str, ...]:
    active_profiles = ["core"]
    for profile in sorted(profiles):
        version = profiles[profile]
        vocabulary = OFFICIAL_VOCABULARIES.get(profile)
        if profile != "core" and vocabulary is not None and version == vocabulary["version"]:
            active_profiles.append(profile)
    return tuple(active_profiles)


def active_vocabulary_attributes(profiles: dict[str, str]) -> dict[str, dict[str, object]]:
    attributes: dict[str, dict[str, object]] = {}
    for profile in active_vocabulary_names(profiles):
        vocabulary = OFFICIAL_VOCABULARIES[profile]
        attributes.update(cast(dict[str, dict[str, object]], vocabulary.get("attributes", {})))
    return attributes


def validate_registered_attribute(
    file: Path,
    element_id: str | None,
    name: str,
    value: str,
    definition: dict[str, object],
    profiles: dict[str, str],
) -> Issue | None:
    kind = definition["kind"]
    if kind == "number":
        try:
            is_finite = math.isfinite(float(value))
        except ValueError:
            is_finite = False
        if not is_finite:
            return Issue("ERROR", "E212", file, f"attribute {name!r} must be a finite number", element_id)
    elif kind == "entity-id" and (not value or any(char.isspace() for char in value)):
        return Issue("ERROR", "E213", file, f"attribute {name!r} must be non-empty and contain no whitespace", element_id)
    elif kind == "entity-ref" and len(value.split()) != 1:
        return Issue("ERROR", "E214", file, f"attribute {name!r} must reference exactly one entity", element_id)
    elif kind == "integer" and INTEGER_RE.fullmatch(value) is None:
        return Issue("ERROR", "E212", file, f"attribute {name!r} must be an integer", element_id)
    elif kind == "boolean" and value not in {"true", "false"}:
        return Issue("ERROR", "E212", file, f"attribute {name!r} must be true or false", element_id)
    elif kind == "enum":
        enum_name = cast(str, definition["enum"])
        enum_values: list[str] = []
        for profile in active_vocabulary_names(profiles):
            vocabulary = OFFICIAL_VOCABULARIES[profile]
            enums = cast(dict[str, list[str]], vocabulary.get("enums", {}))
            if enum_name in enums:
                enum_values = enums[enum_name]
                break
        if value not in enum_values:
            code = {
                "data-sema-coordinate-mode": "E101",
                "data-sema-state": "E210",
                "data-sema-certainty": "E211",
            }.get(name, "E212")
            message = f"attribute {name!r} must use a value from enum {enum_name!r}"
            if name == "data-sema-coordinate-mode":
                message = f"invalid coordinate mode {value!r}"
            elif name == "data-sema-state":
                message = f"unknown state {value!r}"
            elif name == "data-sema-certainty":
                message = f"unknown certainty {value!r}"
            return Issue(
                "ERROR",
                code,
                file,
                message,
                element_id,
            )
    return None


def validate_yaml_schema(file: Path, schema_name: str) -> tuple[dict[str, object] | None, list[Issue]]:
    try:
        with file.open(encoding="utf-8") as stream:
            document = yaml.safe_load(stream)
    except OSError as exc:
        return None, [Issue("ERROR", "E400", file, f"YAML read error: {exc}")]
    except yaml.YAMLError as exc:
        return None, [Issue("ERROR", "E401", file, f"YAML parse error: {exc}")]

    errors = sorted(
        Draft202012Validator(load_schema(schema_name)).iter_errors(document),
        key=lambda error: (error.json_path, error.message),
    )
    if errors:
        return None, [
            Issue("ERROR", "E402", file, f"schema validation error at {error.json_path}: {error.message}")
            for error in errors
        ]

    # Both published schemas require objects. The cast makes the validated
    # document usable for manifest-specific checks without trusting YAML input.
    return cast(dict[str, object], document), []


def validate_vocabulary_metadata(file: Path, vocabulary: dict[str, object]) -> list[Issue]:
    issues: list[Issue] = []
    type_prefix = cast(str, vocabulary["type_prefix"])
    if type_prefix != vocabulary["id"]:
        issues.append(Issue(
            "ERROR",
            "E415",
            file,
            f"type_prefix {type_prefix!r} must match vocabulary id {vocabulary['id']!r}",
        ))

    types = cast(dict[str, dict[str, object]], vocabulary.get("types", {}))
    for local_name, type_definition in types.items():
        qualified = type_definition["qualified"]
        if qualified != f"{type_prefix}:{local_name}":
            issues.append(Issue(
                "ERROR",
                "E413",
                file,
                f"type {local_name!r} must be qualified as {type_prefix}:{local_name}",
            ))

    enums = cast(dict[str, list[str]], vocabulary.get("enums", {}))
    attributes = cast(dict[str, dict[str, object]], vocabulary.get("attributes", {}))
    for name, definition in attributes.items():
        if definition["kind"] == "enum" and definition["enum"] not in enums:
            issues.append(Issue(
                "ERROR",
                "E414",
                file,
                f"attribute {name!r} references undefined enum {definition['enum']!r}",
            ))

    return issues


def validate_vocabulary_directory_metadata(vocabularies: list[tuple[Path, dict[str, object]]]) -> list[Issue]:
    issues: list[Issue] = []
    ids: dict[str, Path] = {}
    prefixes: dict[str, Path] = {}
    attributes: dict[str, tuple[dict[str, object], Path]] = {}
    enums: dict[str, tuple[list[str], Path]] = {}

    for file, vocabulary in vocabularies:
        vocabulary_id = cast(str, vocabulary["id"])
        type_prefix = cast(str, vocabulary["type_prefix"])
        if vocabulary_id in ids:
            issues.append(Issue(
                "ERROR",
                "E416",
                file,
                f"duplicate vocabulary id {vocabulary_id!r}; first declared in {ids[vocabulary_id].name!r}",
            ))
        else:
            ids[vocabulary_id] = file
        if type_prefix in prefixes:
            issues.append(Issue(
                "ERROR",
                "E417",
                file,
                f"duplicate vocabulary type_prefix {type_prefix!r}; first declared in {prefixes[type_prefix].name!r}",
            ))
        else:
            prefixes[type_prefix] = file

        vocabulary_attributes = cast(dict[str, dict[str, object]], vocabulary.get("attributes", {}))
        for name, definition in vocabulary_attributes.items():
            prior = attributes.get(name)
            if prior is not None and definition != prior[0]:
                issues.append(Issue(
                    "ERROR",
                    "E418",
                    file,
                    f"attribute {name!r} conflicts with definition in {prior[1].name!r}",
                ))
            else:
                attributes.setdefault(name, (definition, file))

        vocabulary_enums = cast(dict[str, list[str]], vocabulary.get("enums", {}))
        for name, values in vocabulary_enums.items():
            prior = enums.get(name)
            if prior is not None and values != prior[0]:
                issues.append(Issue(
                    "ERROR",
                    "E419",
                    file,
                    f"enum {name!r} conflicts with values in {prior[1].name!r}",
                ))
            else:
                enums.setdefault(name, (values, file))

    return issues


def validate_manifest_views(
    manifest: dict[str, object],
    project_dir: Path,
    manifest_file: Path,
) -> tuple[list[ManifestView], list[Issue]]:
    issues: list[Issue] = []
    declared_views: list[ManifestView] = []
    view_ids: set[str] = set()
    view_files: set[Path] = set()
    views = cast(list[dict[str, str]], manifest["views"])
    for view in views:
        view_id = view["id"]
        if view_id in view_ids:
            issues.append(Issue("ERROR", "E421", manifest_file, f"duplicate view id {view_id!r}"))
            continue
        view_ids.add(view_id)

        file_value = view["file"]
        view_path = Path(file_value)
        if view_path.is_absolute():
            issues.append(Issue("ERROR", "E403", manifest_file, f"view file {file_value!r} must be relative"))
            continue

        # Resolve before containment testing so a symlink cannot escape the project root.
        resolved = (project_dir / view_path).resolve()
        try:
            resolved.relative_to(project_dir.resolve())
        except ValueError:
            issues.append(Issue("ERROR", "E404", manifest_file, f"view file {file_value!r} escapes the project directory"))
            continue

        if resolved.suffix.lower() != ".svg":
            issues.append(Issue("ERROR", "E406", manifest_file, f"view file {file_value!r} must be an SVG file"))
            continue

        if not resolved.is_file():
            issues.append(Issue("ERROR", "E405", manifest_file, f"view file {file_value!r} does not exist as a file"))
            continue

        # Different path spellings or symlinks must not select one document twice.
        if resolved in view_files:
            issues.append(Issue("ERROR", "E422", manifest_file, f"view file {file_value!r} is already declared"))
            continue
        view_files.add(resolved)
        declared_views.append((view, resolved))

    return declared_views, issues


def validate_project_manifest(
    manifest_file: Path,
) -> tuple[dict[str, object] | None, list[ManifestView], list[Issue]]:
    manifest, issues = validate_yaml_schema(manifest_file, "project.schema.json")
    if manifest is None:
        return None, [], issues

    if manifest["semasvg"] != SUPPORTED_SEMASVG_VERSION:
        issues.append(Issue(
            "ERROR",
            "E407",
            manifest_file,
            f"unsupported SemaSVG version {manifest['semasvg']!r}",
        ))

    manifest_profiles = cast(dict[str, str], manifest["profiles"])
    for profile, version in manifest_profiles.items():
        if profile == "core":
            issues.append(Issue(
                "ERROR",
                "E420",
                manifest_file,
                "Core is implicit and must not be declared as a manifest profile",
            ))
            continue
        vocabulary = OFFICIAL_VOCABULARIES.get(profile)
        if vocabulary is not None and version != vocabulary["version"]:
            issues.append(Issue(
                "ERROR",
                "E411",
                manifest_file,
                f"unsupported {profile!r} manifest profile version {version!r}",
            ))

    declared_views, view_issues = validate_manifest_views(manifest, manifest_file.parent, manifest_file)
    issues.extend(view_issues)
    return manifest, declared_views, issues


def parse_svg(file: Path) -> tuple[ParsedSvg | None, list[Issue]]:
    issues: list[Issue] = []

    try:
        tree = ET.parse(file)
    except ET.ParseError as exc:
        return None, [Issue("ERROR", "E001", file, f"XML parse error: {exc}")]
    except OSError as exc:
        return None, [Issue("ERROR", "E003", file, f"XML read error: {exc}")]

    root = tree.getroot()
    if root.tag != f"{{{SVG_NS}}}svg":
        issues.append(Issue("ERROR", "E002", file, "root element is not SVG <svg> in the SVG namespace"))

    for attr in REQUIRED_ROOT:
        value = root.get(attr)
        if value is None or (attr != "data-sema-profiles" and not value):
            issues.append(Issue("ERROR", "E100", file, f"missing root attribute {attr}"))

    version = root.get("data-sema-version")
    if version and version != SUPPORTED_SEMASVG_VERSION:
        issues.append(Issue("ERROR", "E103", file, f"unsupported SemaSVG version {version!r}"))

    mode = root.get("data-sema-coordinate-mode")
    if mode == "physical" and not root.get("data-sema-unit"):
        issues.append(Issue("ERROR", "E102", file, "physical view requires data-sema-unit"))

    profiles_raw = root.get("data-sema-profiles", "")
    profiles, profile_issues = parse_profile_declarations(file, profiles_raw)
    issues.extend(profile_issues)
    registered_attributes = active_vocabulary_attributes(profiles)

    ids: set[str] = set()
    entities: dict[str, str] = {}

    for elem in root.iter():
        elem_id = elem.get("id")
        if elem_id:
            if elem_id in ids:
                issues.append(Issue("ERROR", "E200", file, f"duplicate SVG id {elem_id!r}", elem_id))
            ids.add(elem_id)

        # Passive-document policy.
        element_name = local_name(elem.tag)
        if element_name == "script":
            issues.append(Issue("ERROR", "E500", file, "<script> is not allowed in canonical SemaSVG", elem_id))
        elif element_name in {"iframe", "object", "embed"}:
            issues.append(Issue(
                "ERROR",
                "E502",
                file,
                f"embedded executable container <{element_name}> is not allowed in canonical SemaSVG",
                elem_id,
            ))
        for attr in elem.attrib:
            if attr.lower().startswith("on"):
                issues.append(Issue("ERROR", "E501", file, f"inline event handler {attr!r} is not allowed", elem_id))
        for attr, value in elem.attrib.items():
            if attr in LINK_HREF_ATTRS and is_javascript_uri(value):
                issues.append(Issue(
                    "ERROR",
                    "E503",
                    file,
                    f"executable URI scheme is not allowed in {local_name(attr)!r}",
                    elem_id,
                ))

        entity = elem.get("data-sema-entity")
        qtype = elem.get("data-sema-type")

        for attr, value in elem.attrib.items():
            definition = registered_attributes.get(attr)
            if definition is None:
                continue
            attribute_issue = validate_registered_attribute(file, elem_id, attr, value, definition, profiles)
            if attribute_issue is not None:
                issues.append(attribute_issue)

        if entity:
            if not elem_id:
                issues.append(Issue("ERROR", "E201", file, "entity representation requires SVG id"))
            if not qtype:
                issues.append(Issue("ERROR", "E202", file, "entity representation requires data-sema-type", elem_id))
            else:
                prior = entities.get(entity)
                if prior is not None and prior != qtype:
                    issues.append(Issue(
                        "ERROR",
                        "E203",
                        file,
                        f"entity {entity!r} has conflicting types {prior!r} and {qtype!r}",
                        elem_id,
                    ))
                entities.setdefault(entity, qtype)

        if qtype:
            if not elem_id:
                issues.append(Issue("ERROR", "E204", file, "typed semantic element requires SVG id"))
            if not QTYPE_RE.match(qtype):
                issues.append(Issue("ERROR", "E205", file, f"type {qtype!r} is not profile-qualified", elem_id))
            else:
                prefix = qtype.split(":", 1)[0]
                if prefix != "core" and prefix not in profiles:
                    issues.append(Issue(
                        "ERROR",
                        "E206",
                        file,
                        f"type prefix {prefix!r} is not declared in data-sema-profiles",
                        elem_id,
                    ))
                elif prefix in active_vocabulary_names(profiles):
                    vocabulary = OFFICIAL_VOCABULARIES[prefix]
                    local_type = qtype.split(":", 1)[1]
                    types = cast(dict[str, dict[str, object]], vocabulary.get("types", {}))
                    type_definition = types.get(local_type)
                    if type_definition is None:
                        issues.append(Issue(
                            "ERROR",
                            "E207",
                            file,
                            f"type {qtype!r} is not registered by profile {prefix!r}",
                            elem_id,
                        ))
                    elif type_definition.get("entity_required", True) and not entity:
                        issues.append(Issue(
                            "ERROR",
                            "E208",
                            file,
                            f"type {qtype!r} requires data-sema-entity",
                            elem_id,
                        ))

    return ParsedSvg(
        file=file,
        root=root,
        project=root.get("data-sema-project", ""),
        profiles=profiles,
        entities=entities,
    ), issues


def validate_manifest_metadata(manifest: dict[str, object], view: dict[str, str], document: ParsedSvg) -> list[Issue]:
    issues: list[Issue] = []
    expected_project = cast(str, manifest["project"])
    expected_view = view["id"]
    expected_kind = view["kind"]

    if document.project != expected_project:
        issues.append(Issue(
            "ERROR",
            "E408",
            document.file,
            f"data-sema-project {document.project!r} does not match manifest project {expected_project!r}",
        ))
    if document.root.get("data-sema-view") != expected_view:
        issues.append(Issue(
            "ERROR",
            "E409",
            document.file,
            f"data-sema-view {document.root.get('data-sema-view')!r} does not match manifest view id {expected_view!r}",
        ))
    if document.root.get("data-sema-view-kind") != expected_kind:
        issues.append(Issue(
            "ERROR",
            "E410",
            document.file,
            f"data-sema-view-kind {document.root.get('data-sema-view-kind')!r} does not match manifest view kind {expected_kind!r}",
        ))

    return issues


def validate_manifest_profiles(manifest: dict[str, object], document: ParsedSvg) -> list[Issue]:
    manifest_profiles = cast(dict[str, str], manifest["profiles"])
    issues: list[Issue] = []
    for profile, version in document.profiles.items():
        if manifest_profiles.get(profile) != version:
            issues.append(Issue(
                "ERROR",
                "E412",
                document.file,
                f"profile {profile!r}@{version} does not match the project manifest",
            ))
    return issues


def validate_property_conflicts(documents: list[ParsedSvg], base: Path | None = None) -> list[Issue]:
    """Compare selected authored facts without choosing an authoritative representation."""
    first_values: dict[tuple[str, str, str], tuple[str | Decimal, str, Path, str | None]] = {}
    issues: list[Issue] = []
    for document in documents:
        attributes = active_vocabulary_attributes(document.profiles)
        for element in document.root.iter():
            entity = element.get("data-sema-entity")
            if not entity or entity not in document.entities:
                continue
            for name in CONSISTENT_ENTITY_ATTRIBUTES:
                definition = attributes.get(name)
                raw = element.get(name)
                if definition is None or raw is None:
                    continue

                value: str | Decimal = raw
                if definition["kind"] == "number":
                    try:
                        # Match scalar acceptance, then compare exact decimals rather than rounded floats.
                        if not math.isfinite(float(raw)):
                            continue
                        value = Decimal(raw)
                    except (ValueError, InvalidOperation):
                        continue

                key = (document.project, entity, name)
                element_id = element.get("id")
                prior = first_values.get(key)
                if prior is None:
                    first_values[key] = (value, raw, document.file, element_id)
                    continue
                if value == prior[0]:
                    continue

                # The first occurrence is only a comparison anchor, never the chosen project value.
                prior_file = prior[2]
                if base is not None:
                    try:
                        prior_file = prior_file.absolute().relative_to(base.absolute())
                    except ValueError:
                        pass
                prior_location = str(prior_file)
                if prior[3]:
                    prior_location += f"#{prior[3]}"
                issues.append(Issue(
                    "WARNING",
                    "W220",
                    document.file,
                    f"entity {entity!r} has conflicting {name}: {prior[1]!r} at {prior_location}, {raw!r} here",
                    element_id,
                ))
    return issues


def validate(path: Path) -> list[Issue]:
    if path.is_file() and path.name == PROJECT_MANIFEST_NAME:
        project_dir = path.parent
        manifest_file: Path | None = path
    elif path.is_dir():
        project_dir = path
        candidate = path / PROJECT_MANIFEST_NAME
        manifest_file = candidate if candidate.is_file() else None
    else:
        project_dir = path
        manifest_file = None

    issues: list[Issue] = []

    if manifest_file is not None:
        manifest, declared_views, manifest_issues = validate_project_manifest(manifest_file)
        issues.extend(manifest_issues)
    else:
        manifest = None
        declared_views = []

    if manifest is None:
        selected_files: list[tuple[dict[str, str] | None, Path]] = [
            (None, file) for file in collect_svg_files(project_dir)
        ]
        if not selected_files:
            issues.append(Issue("ERROR", "E000", project_dir, "no SVG files found"))
    else:
        # Once the manifest is schema-valid, it defines project membership;
        # unlisted SVG files may belong to another project or be work-in-progress.
        selected_files = declared_views
        if not selected_files:
            issues.append(Issue("ERROR", "E000", project_dir, "no SVG files found"))

    parsed: list[ParsedSvg] = []
    for view, file in selected_files:
        doc, doc_issues = parse_svg(file)
        issues.extend(doc_issues)
        if doc:
            parsed.append(doc)
            if manifest is not None and view is not None:
                issues.extend(validate_manifest_metadata(manifest, view, doc))
                issues.extend(validate_manifest_profiles(manifest, doc))

    # A manifest establishes membership itself. Without one, a recursive target
    # must not silently combine independent SemaSVG projects.
    if manifest_file is None and project_dir.is_dir():
        project_ids = {document.project for document in parsed}
        if len(project_ids) > 1:
            joined_projects = ", ".join(repr(project_id) for project_id in sorted(project_ids))
            issues.append(Issue(
                "ERROR",
                "E221",
                project_dir,
                f"SVG files declare multiple SemaSVG projects: {joined_projects}",
            ))

    # Project-wide entity registry. Multiple representations of the same entity
    # are expected, but their semantic type must stay consistent.
    project_entities: dict[str, dict[str, str]] = {}
    for doc in parsed:
        registry = project_entities.setdefault(doc.project, {})
        for entity, qtype in doc.entities.items():
            prior = registry.get(entity)
            if prior is not None and prior != qtype:
                issues.append(Issue(
                    "ERROR",
                    "E220",
                    doc.file,
                    f"project entity {entity!r} changes type from {prior!r} to {qtype!r}",
                ))
            registry.setdefault(entity, qtype)

    # Resolve only attributes whose active vocabulary gives them entity-reference semantics.
    for doc in parsed:
        registry = project_entities.get(doc.project, {})
        attributes = active_vocabulary_attributes(doc.profiles)
        for elem in doc.root.iter():
            elem_id = elem.get("id")
            for attr, definition in attributes.items():
                if definition["kind"] not in {"entity-ref", "entity-ref-list"}:
                    continue
                raw = elem.get(attr)
                if not raw:
                    continue
                for target in raw.split():
                    if target not in registry:
                        issues.append(Issue(
                            "ERROR",
                            "E300",
                            doc.file,
                            f"{attr} references unknown project entity {target!r}",
                            elem_id,
                        ))

    diagnostic_base = project_dir if project_dir.is_dir() else project_dir.parent
    issues.extend(validate_property_conflicts(parsed, diagnostic_base))
    return issues


def validate_vocabulary(path: Path) -> list[Issue]:
    files = collect_yaml_files(path)
    if not files:
        return [Issue("ERROR", "E400", path, "no YAML files found")]

    issues: list[Issue] = []
    parsed_vocabularies: list[tuple[Path, dict[str, object]]] = []
    for file in files:
        vocabulary, file_issues = validate_yaml_schema(file, "vocabulary.schema.json")
        issues.extend(file_issues)
        if vocabulary is not None:
            issues.extend(validate_vocabulary_metadata(file, vocabulary))
            parsed_vocabularies.append((file, vocabulary))
    if path.is_dir():
        issues.extend(validate_vocabulary_directory_metadata(parsed_vocabularies))
    return issues
