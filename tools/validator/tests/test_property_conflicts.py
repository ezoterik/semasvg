from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "validator" / "src"))

from semasvg_validator.cli import main
from semasvg_validator.graph import inspect_graph
from semasvg_validator.validator import ParsedSvg, validate, validate_property_conflicts


class PropertyConflictTest(unittest.TestCase):
    def test_reports_selected_conflicting_facts_with_both_locations(self) -> None:
        cases = (
            ("data-sema-rated-current-a", "16", "25"),
            ("data-sema-voltage-v", "230", "400"),
            ("data-sema-poles", "1P+N", "3P+N"),
            ("data-sema-manufacturer", "Maker A", "Maker B"),
            ("data-sema-model", "Model A", "Model B"),
        )
        for name, first, second in cases:
            with self.subTest(attribute=name):
                issues = validate_property_conflicts([
                    self._document("first.svg", {name: first}),
                    self._document("second.svg", {name: second}),
                ])
                self.assertEqual(1, len(issues))
                issue = issues[0]
                self.assertEqual(("WARNING", "W220"), (issue.severity, issue.code))
                for text in ("device-a", name, repr(first), repr(second), "first.svg#repr-first", "second.svg#repr-second"):
                    self.assertIn(text, issue.render())

    def test_numbers_compare_by_value_and_strings_compare_exactly(self) -> None:
        first = self._document("first.svg", {
            "data-sema-rated-current-a": "16", "data-sema-voltage-v": "230", "data-sema-model": "Model A",
        })
        second = self._document("second.svg", {
            "data-sema-rated-current-a": "16.0", "data-sema-voltage-v": "2.30e2", "data-sema-model": "Model A",
        })
        self.assertEqual([], validate_property_conflicts([first, second]))

        second.root[0].set("data-sema-model", "model a")
        self.assertEqual(1, len(validate_property_conflicts([first, second])))

    def test_decimal_comparison_does_not_hide_distinct_authored_values(self) -> None:
        documents = [
            self._document("first.svg", {"data-sema-voltage-v": "230.00000000000000001"}),
            self._document("second.svg", {"data-sema-voltage-v": "230.00000000000000002"}),
        ]
        self.assertEqual(1, len(validate_property_conflicts(documents)))

    def test_missing_local_derived_and_unknown_properties_are_not_compared(self) -> None:
        documents = [
            self._document("first.svg", {
                "data-sema-rated-current-a": "16", "data-sema-certainty": "measured",
                "data-sema-source": "manual-measurement", "data-sema-route-length-mm": "1000",
                "data-sema-x-note": "first", "x": "10",
            }),
            self._document("second.svg", {
                "data-sema-certainty": "estimated", "data-sema-source": "original-plan",
                "data-sema-route-length-mm": "2000", "data-sema-x-note": "second", "x": "20",
            }),
        ]
        self.assertEqual([], validate_property_conflicts(documents))

    def test_project_and_active_vocabulary_boundaries_are_preserved(self) -> None:
        first = self._document("first.svg", {"data-sema-rated-current-a": "16"})
        second = self._document("second.svg", {"data-sema-rated-current-a": "25"})
        second.project = "separate-project"
        self.assertEqual([], validate_property_conflicts([first, second]))
        second.project = first.project
        second.profiles = {}
        self.assertEqual([], validate_property_conflicts([first, second]))

    def test_invalid_numbers_do_not_create_secondary_conflict_warnings(self) -> None:
        for value in ("NaN", "inf", "invalid", "1e9999"):
            with self.subTest(value=value):
                documents = [
                    self._document("first.svg", {"data-sema-rated-current-a": "16"}),
                    self._document("second.svg", {"data-sema-rated-current-a": value}),
                ]
                self.assertEqual([], validate_property_conflicts(documents))

    def test_warning_keeps_validation_successful_and_graph_values_unmodified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for filename, value in (("first.svg", "16"), ("second.svg", "25")):
                document = self._document(filename, {"data-sema-rated-current-a": value})
                ET.ElementTree(document.root).write(project / filename, encoding="utf-8", xml_declaration=True)
            before = {file: file.read_bytes() for file in project.glob("*.svg")}
            self.assertEqual(["W220"], [issue.code for issue in validate(project)])
            output = StringIO()
            with patch.object(sys, "argv", ["semasvg", "validate", str(project)]), redirect_stdout(output):
                self.assertEqual(0, main())
            self.assertIn("WARNING W220", output.getvalue())
            self.assertIn("0 error(s), 1 warning(s)", output.getvalue())
            self.assertIn("first.svg#repr-first", output.getvalue())
            self.assertIn("second.svg#repr-second", output.getvalue())
            self.assertNotIn(str(project), output.getvalue())
            graph = inspect_graph(project)
            representations = graph["entities"][0]["representations"]
            self.assertEqual(["16", "25"], [item["attributes"]["data-sema-rated-current-a"] for item in representations])
            self.assertEqual(before, {file: file.read_bytes() for file in before})

    def _document(self, filename: str, attributes: dict[str, str]) -> ParsedSvg:
        root = ET.Element("{http://www.w3.org/2000/svg}svg", {
            "data-sema-version": "0.1.0", "data-sema-project": "test-project",
            "data-sema-view": Path(filename).stem, "data-sema-view-kind": "schematic",
            "data-sema-coordinate-mode": "diagrammatic", "data-sema-profiles": "electrical@0.1.0",
        })
        entity = ET.SubElement(root, "{http://www.w3.org/2000/svg}g", {
            "id": f"repr-{Path(filename).stem}", "data-sema-entity": "device-a",
            "data-sema-type": "electrical:protective-device",
        })
        entity.attrib.update(attributes)
        return ParsedSvg(Path(filename), root, "test-project", {"electrical": "0.1.0"}, {
            "device-a": "electrical:protective-device",
        })
