from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

try:
    from .graph import GraphError, inspect_graph
    from .formatter import format_path
    from .labels import materialize_labels
    from .validator import validate, validate_vocabulary
except ImportError:
    # Supports direct execution of this file from a source checkout.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from semasvg_validator.graph import GraphError, inspect_graph
    from semasvg_validator.formatter import format_path
    from semasvg_validator.labels import materialize_labels
    from semasvg_validator.validator import validate, validate_vocabulary


def main() -> int:
    parser = argparse.ArgumentParser(prog="semasvg")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="validate a SemaSVG file or project directory")
    validate_parser.add_argument("path", type=Path)
    vocabulary_parser = sub.add_parser("validate-vocabulary", help="validate a vocabulary YAML file or directory")
    vocabulary_parser.add_argument("path", type=Path)
    labels_parser = sub.add_parser("materialize-labels", help="materialize derived core labels in SVG files")
    labels_parser.add_argument("path", type=Path)
    labels_parser.add_argument("--check", action="store_true", help="fail when a derived label is stale")
    format_parser = sub.add_parser("format", help="format SVG source without changing semantics")
    format_parser.add_argument("path", type=Path)
    format_parser.add_argument("--check", action="store_true", help="fail when SVG formatting is stale")
    graph_parser = sub.add_parser("inspect-graph", help="inspect registered project-wide entity references")
    graph_parser.add_argument("path", type=Path)
    graph_parser.add_argument("--entity", help="return a bidirectional neighborhood of this entity")
    graph_parser.add_argument("--depth", type=int, help="neighborhood depth; requires --entity")
    graph_parser.add_argument(
        "--attribute",
        action="append",
        dest="attributes",
        help="include only this registered entity-reference attribute; repeatable",
    )

    args = parser.parse_args()

    if args.command == "format":
        # Do not resolve here: format_path must see a user-supplied symlink to reject it.
        target = args.path.absolute()
        result = format_path(target, check=args.check)
        base = target if target.is_dir() and not target.is_symlink() else target.parent
        for issue in result.issues:
            print(issue.render(base))
        if result.issues:
            print(f"{len(result.issues)} error(s)")
            return 1
        if args.check and result.stale_files:
            print(f"{result.stale_files} unformatted file(s)")
            return 1
        if args.check:
            print("OK: SVG formatting is current")
        else:
            print(f"OK: formatted {result.updated_files} file(s)")
        return 0

    if args.command == "materialize-labels":
        # Do not resolve here: materialize_labels must see a user-supplied symlink to reject it.
        target = args.path.absolute()
        result = materialize_labels(target, check=args.check)
        base = target if target.is_dir() and not target.is_symlink() else target.parent
        for issue in result.issues:
            print(issue.render(base))
        if result.issues:
            print(f"{len(result.issues)} error(s)")
            return 1
        if args.check and result.stale_labels:
            print(f"{result.stale_labels} stale derived label(s)")
            return 1
        if args.check:
            print("OK: derived labels are current")
        else:
            print(f"OK: materialized {result.stale_labels} derived label(s) in {result.updated_files} file(s)")
        return 0

    if args.command == "inspect-graph":
        try:
            graph = inspect_graph(args.path, entity=args.entity, depth=args.depth, attributes=args.attributes)
        except GraphError as exc:
            print(f"ERROR inspect-graph: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.command == "validate":
        target = args.path.resolve()
        issues = validate(target)
        base = target if target.is_dir() else target.parent

    elif args.command == "validate-vocabulary":
        target = args.path.resolve()
        issues = validate_vocabulary(target)
        base = target if target.is_dir() else target.parent

    else:
        return 2

    for issue in issues:
        print(issue.render(base))

    errors = sum(1 for i in issues if i.severity == "ERROR")
    warnings = sum(1 for i in issues if i.severity == "WARNING")

    if not issues:
        print("OK: no SemaSVG validation issues found")
    else:
        print(f"{errors} error(s), {warnings} warning(s)")

    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
