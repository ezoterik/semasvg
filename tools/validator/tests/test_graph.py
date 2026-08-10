from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
SRC = REPO / "tools" / "validator" / "src"
sys.path.insert(0, str(SRC))

from semasvg_validator.cli import main
from semasvg_validator.graph import GraphError, inspect_graph
from semasvg_validator.validator import validate


class GraphTest(unittest.TestCase):
    def test_native_descriptions_do_not_conflict_or_create_semantic_entities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self._write_svg(project / "first.svg", "first", '''
              <title>Floor plan</title>
              <desc>Partial planning view.</desc>
              <rect id="a-first" data-sema-entity="a" data-sema-type="building:furniture">
                <title>Cabinet footprint</title>
                <desc>Check access before placing the cabinet.</desc>
              </rect>
            ''')
            self._write_svg(project / "second.svg", "second", '''
              <g id="a-second" data-sema-entity="a" data-sema-type="building:furniture">
                <title>Cabinet overview</title>
                <desc>See the floor plan for placement.</desc>
              </g>
            ''')

            self.assertEqual([], validate(project))
            graph = inspect_graph(project)

        self.assertEqual(["a"], [entity["entity"] for entity in graph["entities"]])
        self.assertEqual(2, len(graph["entities"][0]["representations"]))
        self.assertEqual([], graph["edges"])

    def test_certainty_and_source_remain_optional_and_representation_local(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self._write_svg(project / "first.svg", "first", '''
              <g id="a-first" data-sema-entity="a" data-sema-type="building:furniture"
                 data-sema-certainty="measured" data-sema-source="manual-measurement">
                <g id="b-first" data-sema-entity="b" data-sema-type="building:furniture" />
              </g>
            ''')
            self._write_svg(project / "second.svg", "second", '''
              <g id="a-second" data-sema-entity="a" data-sema-type="building:furniture"
                 data-sema-certainty="estimated" data-sema-source="original-plan" />
            ''')
            self._write_svg(project / "third.svg", "third", '''
              <g id="a-third" data-sema-entity="a" data-sema-type="building:furniture" />
            ''')

            self.assertEqual([], validate(project))
            graph = inspect_graph(project)

        entities = {entity["entity"]: entity for entity in graph["entities"]}
        annotations = [
            (representation["attributes"].get("data-sema-certainty"),
             representation["attributes"].get("data-sema-source"))
            for representation in entities["a"]["representations"]
        ]
        self.assertEqual([
            ("measured", "manual-measurement"),
            ("estimated", "original-plan"),
            (None, None),
        ], annotations)
        child_attributes = entities["b"]["representations"][0]["attributes"]
        self.assertNotIn("data-sema-certainty", child_attributes)
        self.assertNotIn("data-sema-source", child_attributes)

    def test_single_references_cannot_create_multiple_edges_or_disappear(self) -> None:
        cases = (
            ("data-sema-parent", "a b", "E214", []),
            ("data-sema-parent", "", "E214", []),
            ("data-sema-parent", "   ", "E214", []),
            ("data-sema-parent", " a ", None, ["a"]),
            ("data-sema-connects", "a b", None, ["a", "b"]),
        )
        for attribute, value, error, targets in cases:
            with self.subTest(attribute=attribute, value=value), tempfile.TemporaryDirectory() as directory:
                file = Path(directory) / "references.svg"
                self._write_svg(file, "references", f'''
                  <g id="a" data-sema-entity="a" data-sema-type="building:space" />
                  <g id="b" data-sema-entity="b" data-sema-type="building:space" />
                  <g id="child" data-sema-entity="child" data-sema-type="building:space" {attribute}="{value}" />
                ''')

                issues = validate(file)
                if error is not None:
                    self.assertEqual([error], [issue.code for issue in issues])
                    with self.assertRaisesRegex(GraphError, error):
                        inspect_graph(file)
                else:
                    self.assertEqual([], issues)
                    graph = inspect_graph(file)
                    self.assertEqual(targets, [edge["target"] for edge in graph["edges"]])

    def test_manifest_rejects_repeated_view_ids_and_resolved_files(self) -> None:
        cases = (
            ("main", "first.svg", "E421"),
            ("main", "second.svg", "E421"),
            ("other", "first.svg", "E422"),
            ("other", "./first.svg", "E422"),
            ("other", "alias.svg", "E422"),
        )
        for second_id, second_file, error in cases:
            with self.subTest(view=second_id, file=second_file), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                body = '<g id="a" data-sema-entity="a" data-sema-type="building:space" />'
                self._write_svg(project / "first.svg", "main", body)
                self._write_svg(project / "second.svg", "main", body)
                (project / "alias.svg").symlink_to("first.svg")
                manifest = project / "semasvg.project.yaml"
                manifest.write_text(yaml.safe_dump({
                    "semasvg": "0.1.0",
                    "project": "test-project",
                    "profiles": {"building": "0.1.0"},
                    "views": [
                        {"id": "main", "file": "first.svg", "kind": "floor-plan"},
                        {"id": second_id, "file": second_file, "kind": "floor-plan"},
                    ],
                }), encoding="utf-8")

                for target in (project, manifest):
                    self.assertEqual([error], [issue.code for issue in validate(target)])
                    with self.assertRaisesRegex(GraphError, error):
                        inspect_graph(target)

    def test_merges_representations_and_deduplicates_registered_edges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self._write_svg(project / "first.svg", "first", """
              <rect id="repr-a-first" data-sema-entity="entity-a" data-sema-type="building:space" data-sema-parent="entity-b" data-sema-x-related="ignored" />
              <rect id="repr-b-first" data-sema-entity="entity-b" data-sema-type="building:space" />
            """)
            self._write_svg(project / "second.svg", "second", """
              <rect id="repr-a-second" data-sema-entity="entity-a" data-sema-type="building:space" data-sema-parent="entity-b" data-sema-name="Second representation" />
              <rect id="repr-b-second" data-sema-entity="entity-b" data-sema-type="building:space" />
            """)

            graph = inspect_graph(project)
            standalone = inspect_graph(project / "first.svg")

        entity_a = next(item for item in graph["entities"] if item["entity"] == "entity-a")
        self.assertEqual("building:space", entity_a["type"])
        self.assertEqual(["first", "second"], [item["view"] for item in entity_a["representations"]])
        edge = next(item for item in graph["edges"] if item["source"] == "entity-a")
        self.assertEqual(("data-sema-parent", "entity-b"), (edge["attribute"], edge["target"]))
        self.assertEqual(2, len(edge["provenance"]))
        self.assertFalse(any(edge["attribute"] == "data-sema-x-related" for edge in graph["edges"]))
        self.assertEqual(["entity-a", "entity-b"], [item["entity"] for item in standalone["entities"]])

    def test_neighborhood_is_bidirectional_and_depth_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self._write_svg(project / "graph.svg", "graph", """
              <rect id="a" data-sema-entity="a" data-sema-type="building:space" data-sema-parent="b" />
              <rect id="b" data-sema-entity="b" data-sema-type="building:space" data-sema-parent="c" />
              <rect id="c" data-sema-entity="c" data-sema-type="building:space" />
            """)

            depth_zero = inspect_graph(project, entity="b", depth=0)
            depth_one = inspect_graph(project, entity="b", depth=1)

        self.assertEqual(["b"], [item["entity"] for item in depth_zero["entities"]])
        self.assertEqual({"a", "b", "c"}, {item["entity"] for item in depth_one["entities"]})
        self.assertEqual(2, len(depth_one["edges"]))

    def test_manifest_membership_is_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            self._write_svg(project / "listed.svg", "listed", """
              <rect id="listed" data-sema-entity="listed" data-sema-type="building:space" />
            """)
            self._write_svg(project / "unlisted.svg", "unlisted", """
              <rect id="unlisted" data-sema-entity="unlisted" data-sema-type="building:space" />
            """)
            (project / "semasvg.project.yaml").write_text(yaml.safe_dump({
                "semasvg": "0.1.0",
                "project": "test-project",
                "profiles": {"building": "0.1.0"},
                "views": [{"id": "listed", "file": "listed.svg", "kind": "floor-plan"}],
            }), encoding="utf-8")

            graph = inspect_graph(project)
            direct_manifest_graph = inspect_graph(project / "semasvg.project.yaml")

        self.assertTrue(graph["metadata"]["manifest_authoritative"])
        self.assertEqual(["listed"], [item["entity"] for item in graph["entities"]])
        self.assertEqual(graph["entities"], direct_manifest_graph["entities"])

    def test_cli_is_deterministic_and_rejects_invalid_queries_without_json(self) -> None:
        target = REPO / "examples" / "reference" / "renovation-demo"
        first = self._run_cli("inspect-graph", str(target))
        second = self._run_cli("inspect-graph", str(target))
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertIn("entities", decoded)
        self.assertEqual(1, decoded["schema_version"])

        stdout, stderr, code = self._run_cli_result("inspect-graph", str(target), "--depth", "1")
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("--depth requires --entity", stderr)
        stdout, stderr, code = self._run_cli_result(
            "inspect-graph", str(target), "--attribute", "data-sema-typo"
        )
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("not a registered active entity reference", stderr)
        stdout, stderr, code = self._run_cli_result("inspect-graph", str(target / "missing.svg"))
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("validation failed", stderr)
        self.assertIn("E000", stderr)
        with self.assertRaises(GraphError):
            inspect_graph(target, entity="missing")

    def test_renovation_breaker_query_reaches_load_spaces_without_invented_edge(self) -> None:
        graph = inspect_graph(
            REPO / "examples" / "reference" / "renovation-demo",
            entity="breaker-general-sockets",
            depth=3,
            attributes={"data-sema-circuit", "data-sema-space"},
        )

        entities = {item["entity"] for item in graph["entities"]}
        required_entities = {
            "circuit-general-sockets",
            "socket-bedroom-bedside",
            "socket-living-tv",
            "room-bedroom",
            "room-living",
        }
        self.assertTrue(required_entities <= entities)
        self.assertFalse({"panel-main", "system-electrical"} & entities)
        self.assertFalse(any(
            edge["source"] == "breaker-general-sockets" and edge["target"] in {"room-bedroom", "room-living"}
            for edge in graph["edges"]
        ))

    def _write_svg(self, path: Path, view: str, body: str) -> None:
        path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg"
            data-sema-version="0.1.0" data-sema-project="test-project"
            data-sema-view="{view}" data-sema-view-kind="floor-plan"
            data-sema-coordinate-mode="diagrammatic" data-sema-profiles="building@0.1.0">
            {body}
        </svg>''', encoding="utf-8")

    def _run_cli(self, *arguments: str) -> str:
        stdout, stderr, code = self._run_cli_result(*arguments)
        self.assertEqual("", stderr)
        self.assertEqual(0, code)
        return stdout

    def _run_cli_result(self, *arguments: str) -> tuple[str, str, int]:
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(sys, "argv", ["semasvg", *arguments]), redirect_stdout(stdout), redirect_stderr(stderr):
            code = main()
        return stdout.getvalue(), stderr.getvalue(), code
