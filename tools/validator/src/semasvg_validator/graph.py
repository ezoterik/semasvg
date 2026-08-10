"""Read-only, non-normative inspection of registered SemaSVG entity relations."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

from .validator import (
    PROJECT_MANIFEST_NAME,
    active_vocabulary_attributes,
    collect_svg_files,
    parse_svg,
    validate,
    validate_project_manifest,
)


class GraphError(ValueError):
    """Raised when a graph cannot be safely built from the requested input."""


def inspect_graph(
    path: Path,
    entity: str | None = None,
    depth: int | None = None,
    attributes: Collection[str] | None = None,
) -> dict[str, Any]:
    """Return a deterministic graph of source-authored registered entity references.

    Validation is deliberately a gate: consumers must not receive a partial graph
    whose identity or reference errors could make it look authoritative.
    Optional attribute filters constrain emitted edges and traversal, but never
    turn an inferred relation into a source-authored graph edge.
    """
    if depth is not None and entity is None:
        raise GraphError("--depth requires --entity")
    if depth is not None and depth < 0:
        raise GraphError("--depth must be non-negative")
    requested_attributes = set(attributes) if attributes else None

    target = path.resolve()
    errors = [issue for issue in validate(target) if issue.severity == "ERROR"]
    if errors:
        base = target if target.is_dir() else target.parent
        first_error = errors[0].render(base)
        remaining = len(errors) - 1
        suffix = f"; {remaining} additional error(s)" if remaining else ""
        raise GraphError(f"validation failed: {first_error}{suffix}")

    base, files, manifest_authoritative = _select_files(target)
    entities: dict[str, list[dict[str, object]]] = {}
    edges: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    entity_types: dict[str, str] = {}
    available_attributes: set[str] = set()
    project: str | None = None

    for file in files:
        document, parse_issues = parse_svg(file)
        if document is None or any(issue.severity == "ERROR" for issue in parse_issues):
            # validate() above already rejects this state. Keep the builder safe
            # if validator internals change independently in a later release.
            raise GraphError("validation failed while reading SVG input")

        relative_file = str(file.relative_to(base))
        view = document.root.get("data-sema-view", "")
        project = document.project
        active_attributes = active_vocabulary_attributes(document.profiles)
        reference_attributes = {
            name for name, definition in active_attributes.items()
            if definition["kind"] in {"entity-ref", "entity-ref-list"}
        }
        available_attributes.update(reference_attributes)

        for element in document.root.iter():
            source = element.get("data-sema-entity")
            if source is None:
                continue

            representation = {
                "attributes": dict(sorted(
                    (name, value) for name, value in element.attrib.items()
                    if name.startswith("data-sema-")
                )),
                "file": relative_file,
                "svg_id": element.get("id", ""),
                "view": view,
            }
            entities.setdefault(source, []).append(representation)
            entity_types.setdefault(source, element.get("data-sema-type", ""))

            provenance = {
                "file": relative_file,
                "svg_id": element.get("id", ""),
                "view": view,
            }
            for attribute in sorted(reference_attributes):
                raw = element.get(attribute)
                if not raw:
                    continue
                for destination in sorted(set(raw.split())):
                    edges.setdefault((source, attribute, destination), []).append(provenance)

    if requested_attributes is not None:
        unknown_attributes = sorted(requested_attributes - available_attributes)
        if unknown_attributes:
            joined = ", ".join(repr(attribute) for attribute in unknown_attributes)
            raise GraphError(f"attribute filter is not a registered active entity reference: {joined}")

    graph = {
        "entities": [
            {
                "entity": entity_id,
                "representations": sorted(representations, key=_representation_key),
                "type": entity_types[entity_id],
            }
            for entity_id, representations in sorted(entities.items())
        ],
        "edges": [
            {
                "attribute": attribute,
                "provenance": sorted(provenance, key=_provenance_key),
                "source": source,
                "target": destination,
            }
            for (source, attribute, destination), provenance in sorted(edges.items())
            if requested_attributes is None or attribute in requested_attributes
        ],
        "metadata": {
            "edge_policy": "source-authored registered entity references only; no inferred relations",
            "experimental": True,
            "manifest_authoritative": manifest_authoritative,
            "project": project,
        },
        "schema_version": 1,
    }
    if entity is None:
        return graph
    if entity not in entities:
        raise GraphError(f"unknown entity {entity!r}")

    selected_entities = _neighborhood(entity, graph["edges"], depth if depth is not None else 1)
    graph["entities"] = [item for item in graph["entities"] if item["entity"] in selected_entities]
    graph["edges"] = [
        edge for edge in graph["edges"]
        if edge["source"] in selected_entities and edge["target"] in selected_entities
    ]
    query: dict[str, object] = {"depth": depth if depth is not None else 1, "entity": entity}
    if requested_attributes is not None:
        query["attributes"] = sorted(requested_attributes)
    graph["query"] = query
    return graph


def _select_files(path: Path) -> tuple[Path, list[Path], bool]:
    if path.is_file() and path.name == PROJECT_MANIFEST_NAME:
        manifest_file = path
    elif path.is_dir() and (path / PROJECT_MANIFEST_NAME).is_file():
        manifest_file = path / PROJECT_MANIFEST_NAME
    else:
        manifest_file = None

    if manifest_file is not None:
        manifest, views, issues = validate_project_manifest(manifest_file)
        if manifest is None or any(issue.severity == "ERROR" for issue in issues):
            raise GraphError("validation failed while reading project manifest")
        return manifest_file.parent, [file for _, file in views], True
    if path.is_dir():
        return path, collect_svg_files(path), False
    return path.parent, [path], False


def _neighborhood(entity: str, edges: list[dict[str, object]], depth: int) -> set[str]:
    """Return entities within depth hops, using explicit edge direction as adjacency."""
    selected = {entity}
    frontier = {entity}
    for _ in range(depth):
        adjacent = {
            str(edge["target"] if edge["source"] in frontier else edge["source"])
            for edge in edges
            if edge["source"] in frontier or edge["target"] in frontier
        }
        frontier = adjacent - selected
        selected.update(frontier)
    return selected


def _representation_key(representation: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(representation["file"]),
        str(representation["view"]),
        str(representation["svg_id"]),
    )


def _provenance_key(provenance: dict[str, str]) -> tuple[str, str, str]:
    return provenance["file"], provenance["view"], provenance["svg_id"]
