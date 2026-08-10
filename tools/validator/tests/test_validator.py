from __future__ import annotations

from contextlib import redirect_stdout
from importlib.resources import files
from io import StringIO
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import yaml

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
REFERENCE_PANEL_CIRCUITS: dict[str, tuple[str, str]] = {
    "circuit-general-sockets": ("C1", "terminal-outgoing-c1"),
    "circuit-kitchen-sockets": ("C2", "terminal-outgoing-c2"),
    "circuit-office-sockets": ("C3", "terminal-outgoing-c3"),
    "circuit-hob": ("C4", "terminal-outgoing-c4"),
    "circuit-lighting-ground": ("C5", "terminal-outgoing-c5"),
}


def _parse_polyline_points(points: str) -> list[tuple[float, float]]:
    """Parse the intentionally restricted x,y point list used by the panel layout."""
    parsed_points: list[tuple[float, float]] = []
    for point in points.split():
        coordinates = point.split(",")
        if len(coordinates) != 2:
            raise ValueError(f"point '{point}' must contain exactly one comma")
        x, y = (float(coordinate) for coordinate in coordinates)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"point '{point}' must be finite")
        parsed_points.append((x, y))
    return parsed_points


def _parse_orthogonal_path_points(path_data: str) -> list[tuple[float, float]]:
    """Return every vertex from the absolute M/H/V/L paths used by floor-plan routes."""
    tokens = re.findall(r"[MHVL]|-?(?:\d+(?:\.\d*)?|\.\d+)", path_data)
    if len(tokens) < 3 or tokens[0] != "M":
        raise ValueError("route path must begin with an absolute moveto")
    index = 1
    x = float(tokens[index])
    y = float(tokens[index + 1])
    points = [(x, y)]
    index += 2
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command == "H":
            x = float(tokens[index])
            index += 1
        elif command == "V":
            y = float(tokens[index])
            index += 1
        elif command == "L":
            x = float(tokens[index])
            y = float(tokens[index + 1])
            index += 2
        else:
            raise ValueError(f"unsupported floor-plan route command '{command}'")
        points.append((x, y))
    return points


def _parse_orthogonal_path_endpoints(path_data: str) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return endpoints from the absolute M/H/V/L paths used by the floor-plan routes."""
    points = _parse_orthogonal_path_points(path_data)
    return points[0], points[-1]


def _reference_panel_terminal_anchors(root: ET.Element) -> dict[str, tuple[float, float]]:
    """Return the one local connection coordinate declared by each panel terminal."""
    anchors: dict[str, tuple[float, float]] = {}
    for terminal in root.iter():
        if terminal.get("data-sema-type") != "electrical:terminal":
            continue
        entity = terminal.get("data-sema-entity")
        terminal_anchors = [
            anchor
            for anchor in terminal.iter()
            if anchor.get("data-sema-role") == "terminal-anchor"
        ]
        if entity is None:
            continue
        if len(terminal_anchors) != 1:
            raise ValueError(f"terminal '{entity}' must have exactly one local anchor")
        anchor = terminal_anchors[0]
        if anchor.tag.rsplit("}", 1)[-1] == "circle":
            x = float(anchor.get("cx", "nan"))
            y = float(anchor.get("cy", "nan"))
        elif anchor.tag.rsplit("}", 1)[-1] == "rect":
            x = float(anchor.get("x", "nan"))
            y = float(anchor.get("y", "nan"))
        else:
            raise ValueError(f"terminal '{entity}' anchor must be a circle or rectangle")
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"terminal '{entity}' anchor must be finite")
        anchors[entity] = (x, y)
    return anchors


SRC = REPO / "tools" / "validator" / "src"
sys.path.insert(0, str(SRC))

from semasvg_validator.validator import parse_svg, validate, validate_vocabulary
from semasvg_validator.cli import main
from semasvg_validator.formatter import format_path
from semasvg_validator.graph import inspect_graph
from semasvg_validator.labels import materialize_labels


class ValidatorTest(unittest.TestCase):
    def test_minimal_valid_fixture(self) -> None:
        issues = validate(REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
        self.assertEqual([], [i for i in issues if i.severity == "ERROR"])

    def test_physical_requires_unit(self) -> None:
        issues = validate(REPO / "tests" / "fixtures" / "invalid" / "physical-without-unit.sema.svg")
        self.assertIn("E102", {i.code for i in issues})

    def test_physical_unit_must_be_millimeters(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "unsupported-unit.sema.svg"
            file.write_text(fixture.replace('data-sema-unit="mm"', 'data-sema-unit="cm"'), encoding="utf-8")

            issues = validate(file)

        self.assertIn("E212", {issue.code for issue in issues})

    def test_coordinate_mode_must_use_the_core_enum(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "unsupported-coordinate-mode.sema.svg"
            file.write_text(
                fixture.replace('data-sema-coordinate-mode="physical"', 'data-sema-coordinate-mode="spatial"'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertEqual(["E101"], [issue.code for issue in issues if issue.code in {"E101", "E212"}])

    def test_core_only_view_requires_an_empty_profile_attribute(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        core_only = (
            fixture
            .replace('data-sema-profiles="building@0.1.0"', 'data-sema-profiles=""')
            .replace('        data-sema-entity="room-a"\n', '')
            .replace('data-sema-type="building:space"', 'data-sema-type="core:annotation"')
        )
        missing_profiles = core_only.replace('     data-sema-profiles="">\n', '>\n')
        missing_project = core_only.replace('     data-sema-project="fixture-valid"\n', '')

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            core_only_file = project / "core-only.sema.svg"
            missing_profiles_file = project / "missing-profiles.sema.svg"
            missing_project_file = project / "missing-project.sema.svg"
            core_only_file.write_text(core_only, encoding="utf-8")
            missing_profiles_file.write_text(missing_profiles, encoding="utf-8")
            missing_project_file.write_text(missing_project, encoding="utf-8")

            core_only_issues = validate(core_only_file)
            missing_profiles_issues = validate(missing_profiles_file)
            missing_project_issues = validate(missing_project_file)

        self.assertEqual([], [issue for issue in core_only_issues if issue.severity == "ERROR"])
        self.assertIn("E100", {issue.code for issue in missing_profiles_issues})
        self.assertIn("E100", {issue.code for issue in missing_project_issues})

    def test_type_must_be_qualified(self) -> None:
        issues = validate(REPO / "tests" / "fixtures" / "invalid" / "unqualified-type.sema.svg")
        self.assertIn("E205", {i.code for i in issues})

    def test_entity_reference_must_resolve(self) -> None:
        issues = validate(REPO / "tests" / "fixtures" / "invalid" / "missing-reference.sema.svg")
        self.assertIn("E300", {i.code for i in issues})

    def test_svg_root_requires_svg_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "no-namespace.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace(' xmlns="http://www.w3.org/2000/svg"', ''),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E002", {issue.code for issue in issues})

    def test_foreign_object_iframe_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "iframe.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace(
                    "</svg>",
                    "<foreignObject><iframe src=\"https://example.test\" /></foreignObject></svg>",
                ),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E502", {issue.code for issue in issues})

    def test_javascript_uri_is_rejected_but_ordinary_links_are_allowed(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        executable = fixture.replace(
            "</svg>",
            "<a xmlns:xlink=\"http://www.w3.org/1999/xlink\" xlink:href=\"\tJaVa\tsCrIpT:alert(1)\n\"><text>Unsafe</text></a></svg>",
        )
        allowed = fixture.replace(
            "</svg>",
            "<a href=\"#room-a\"><text>Local reference</text></a><image href=\"https://example.test/image.svg\" /></svg>",
        )

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            executable_file = project / "executable-uri.sema.svg"
            allowed_file = project / "allowed-links.sema.svg"
            executable_file.write_text(executable, encoding="utf-8")
            allowed_file.write_text(allowed, encoding="utf-8")

            executable_issues = validate(executable_file)
            allowed_issues = validate(allowed_file)

        self.assertIn("E503", {issue.code for issue in executable_issues})
        self.assertEqual([], [issue for issue in allowed_issues if issue.severity == "ERROR"])

    def test_malformed_profile_declaration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "malformed-profile.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('data-sema-profiles="building@0.1.0"', 'data-sema-profiles="building"'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E104", {issue.code for issue in issues})

    def test_core_must_not_be_declared_as_a_profile(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "explicit-core-profile.sema.svg"
            file.write_text(
                fixture.replace('building@0.1.0', 'core@0.1.0 building@0.1.0'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E106", {issue.code for issue in issues})

    def test_unsupported_official_profile_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "unsupported-profile.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('building@0.1.0', 'building@0.2.0'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E105", {issue.code for issue in issues})

    def test_unknown_official_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "unknown-type.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('building:space', 'building:unknown'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E207", {issue.code for issue in issues})

    def test_unknown_core_type_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "unknown-core-type.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('building:space', 'core:unknown'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E207", {issue.code for issue in issues})

    def test_registered_entity_required_type_requires_entity(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        entity_required = fixture.replace('data-sema-entity="room-a"\n        ', '')
        core_label = entity_required.replace('building:space', 'core:label')

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            required_file = project / "entity-required.sema.svg"
            core_label_file = project / "core-label.sema.svg"
            required_file.write_text(entity_required, encoding="utf-8")
            core_label_file.write_text(core_label, encoding="utf-8")

            required_issues = validate(required_file)
            core_label_issues = validate(core_label_file)

        self.assertIn("E208", {issue.code for issue in required_issues})
        self.assertEqual([], [issue for issue in core_label_issues if issue.severity == "ERROR"])

    def test_registered_entity_id_requires_non_whitespace_value(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            whitespace_file = project / "whitespace-entity.sema.svg"
            legacy_file = project / "legacy-entity.sema.svg"
            valid_file = project / "valid-entity.sema.svg"
            whitespace_file.write_text(fixture.replace("room-a", "room a"), encoding="utf-8")
            legacy_file.write_text(fixture.replace("room-a", "Room-A"), encoding="utf-8")
            valid_file.write_text(fixture, encoding="utf-8")

            whitespace_issues = validate(whitespace_file)
            legacy_issues = validate(legacy_file)
            valid_issues = validate(valid_file)

        self.assertIn("E213", {issue.code for issue in whitespace_issues})
        self.assertEqual([], [issue for issue in legacy_issues if issue.severity == "ERROR"])
        self.assertEqual([], [issue for issue in valid_issues if issue.severity == "ERROR"])

    def test_unknown_third_party_profile_type_remains_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "third-party.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('building@0.1.0', 'example.vendor@1.2.3')
                .replace('building:space', 'example.vendor:thing'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertEqual([], [issue for issue in issues if issue.severity == "ERROR"])

    def test_registered_attribute_values_are_validated(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        fixture = fixture.replace('building@0.1.0', 'building@0.1.0 electrical@0.1.0')
        valid = fixture.replace(
            'data-sema-state="existing"',
            'data-sema-state="planned" data-sema-voltage-v="230" data-sema-phases="3" data-sema-dedicated-line="true"',
        )
        invalid = fixture.replace(
            'data-sema-state="existing"',
            'data-sema-state="invalid" data-sema-voltage-v="NaN" data-sema-phases="3.5" data-sema-dedicated-line="yes"',
        )

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            valid_file = project / "valid.sema.svg"
            invalid_file = project / "invalid.sema.svg"
            valid_file.write_text(valid, encoding="utf-8")
            invalid_file.write_text(invalid, encoding="utf-8")

            valid_issues = validate(valid_file)
            invalid_issues = validate(invalid_file)

        self.assertEqual([], [issue for issue in valid_issues if issue.severity == "ERROR"])
        codes = {issue.code for issue in invalid_issues}
        self.assertIn("E210", codes)
        self.assertIn("E212", codes)

    def test_registered_entity_references_are_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "registry-reference.sema.svg"
            file.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('data-sema-state="existing"', 'data-sema-connects="missing-space" data-sema-state="existing"'),
                encoding="utf-8",
            )

            issues = validate(file)

        self.assertIn("E300", {issue.code for issue in issues})

    def test_building_opening_contract_validates_kind_traversability_and_swing_space(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        opening = """
  <rect id="repr-wall-exterior"
        data-sema-entity="wall-exterior"
        data-sema-type="building:wall"
        data-sema-wall-kind="exterior" />
  <rect id="repr-yard"
        data-sema-entity="yard-main"
        data-sema-type="building:space"
        data-sema-space-kind="outdoor" />
  <rect id="repr-window"
        data-sema-entity="window-main"
        data-sema-type="building:opening"
        data-sema-opening-kind="window"
        data-sema-opening-operation="tilt-turn"
        data-sema-host="wall-exterior"
        data-sema-connects="room-a yard-main"
        data-sema-traversable="false"
        data-sema-swing-space="room-a" />
"""
        valid = fixture.replace("</svg>", opening + "</svg>")
        invalid = (
            valid
            .replace('data-sema-opening-kind="window"', 'data-sema-opening-kind="hatch"')
            .replace('data-sema-traversable="false"', 'data-sema-traversable="yes"')
            .replace('data-sema-swing-space="room-a"', 'data-sema-swing-space="missing-room"')
        )

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            valid_file = project / "valid-opening.sema.svg"
            invalid_file = project / "invalid-opening.sema.svg"
            valid_file.write_text(valid, encoding="utf-8")
            invalid_file.write_text(invalid, encoding="utf-8")

            valid_issues = validate(valid_file)
            invalid_issues = validate(invalid_file)

        self.assertEqual([], [issue for issue in valid_issues if issue.severity == "ERROR"])
        self.assertTrue(any(issue.code == "E212" and "data-sema-opening-kind" in issue.message for issue in invalid_issues))
        self.assertTrue(any(issue.code == "E212" and "data-sema-traversable" in issue.message for issue in invalid_issues))
        self.assertTrue(any(issue.code == "E300" and "data-sema-swing-space" in issue.message for issue in invalid_issues))

    def test_building_structural_and_vertical_connection_types_are_registered(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        building_elements = """
  <rect id="repr-level-ground" data-sema-entity="level-ground" data-sema-type="building:level" />
  <rect id="repr-level-first" data-sema-entity="level-first" data-sema-type="building:level" />
  <rect id="repr-slab-ground" data-sema-entity="slab-ground" data-sema-type="building:slab" />
  <rect id="repr-column-main" data-sema-entity="column-main" data-sema-type="building:column" />
  <path id="repr-roof-main" data-sema-entity="roof-main" data-sema-type="building:roof" data-sema-roof-kind="gable" />
  <path id="repr-stair-main" data-sema-entity="stair-main"
        data-sema-type="building:vertical-connection"
        data-sema-vertical-connection-kind="stair"
        data-sema-connects-levels="level-ground level-first" />
"""
        valid = fixture.replace("</svg>", building_elements + "</svg>")
        invalid = valid.replace(
            'data-sema-connects-levels="level-ground level-first"',
            'data-sema-connects-levels="level-ground missing-level"',
        )

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            valid_file = project / "valid-building-elements.sema.svg"
            invalid_file = project / "invalid-building-elements.sema.svg"
            valid_file.write_text(valid, encoding="utf-8")
            invalid_file.write_text(invalid, encoding="utf-8")

            valid_issues = validate(valid_file)
            invalid_issues = validate(invalid_file)

        self.assertEqual([], [issue for issue in valid_issues if issue.severity == "ERROR"])
        self.assertTrue(any(issue.code == "E300" and "missing-level" in issue.message for issue in invalid_issues))

    def test_electrical_supply_device_and_cable_contract_is_validated(self) -> None:
        fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
        fixture = fixture.replace('building@0.1.0', 'building@0.1.0 electrical@0.1.0')
        electrical_elements = """
  <g id="repr-supply-main" data-sema-entity="supply-main"
     data-sema-type="electrical:supply"
     data-sema-supply-kind="utility"
     data-sema-frequency-hz="50" />
  <g id="repr-panel-main" data-sema-entity="panel-main" data-sema-type="electrical:panel" />
  <line id="repr-rail-main" data-sema-entity="rail-main" data-sema-type="electrical:din-rail" />
  <rect id="repr-meter-main" data-sema-entity="meter-main"
        data-sema-type="electrical:device"
        data-sema-device-kind="energy-meter"
        data-sema-rail="rail-main"
        data-sema-slot-start="1"
        data-sema-module-count="2" />
  <g id="repr-circuit-main" data-sema-entity="circuit-main"
     data-sema-type="electrical:circuit"
     data-sema-circuit-kind="feeder"
     data-sema-phase="L1" />
  <path id="repr-cable-main" data-sema-entity="cable-main"
        data-sema-type="electrical:cable"
        data-sema-from="supply-main"
        data-sema-to="panel-main"
        data-sema-circuit="circuit-main"
        data-sema-core-count="3"
        data-sema-core-cross-section-mm2="10" />
  <path id="repr-route-main" data-sema-entity="route-main"
        data-sema-type="electrical:route-segment"
        data-sema-cable="cable-main" />
"""
        valid = fixture.replace("</svg>", electrical_elements + "</svg>")
        invalid = (
            valid
            .replace('data-sema-rail="rail-main"', 'data-sema-rail="missing-rail"')
            .replace('data-sema-module-count="2"', 'data-sema-module-count="2.5"')
            .replace('data-sema-cable="cable-main"', 'data-sema-cable="missing-cable"')
        )

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            valid_file = project / "valid-electrical-elements.sema.svg"
            invalid_file = project / "invalid-electrical-elements.sema.svg"
            valid_file.write_text(valid, encoding="utf-8")
            invalid_file.write_text(invalid, encoding="utf-8")

            valid_issues = validate(valid_file)
            invalid_issues = validate(invalid_file)

        self.assertEqual([], [issue for issue in valid_issues if issue.severity == "ERROR"])
        self.assertTrue(any(issue.code == "E212" and "data-sema-module-count" in issue.message for issue in invalid_issues))
        self.assertTrue(any(issue.code == "E300" and "missing-rail" in issue.message for issue in invalid_issues))
        self.assertTrue(any(issue.code == "E300" and "missing-cable" in issue.message for issue in invalid_issues))

    def test_directory_without_manifest_requires_one_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fixture = (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8")
            (project / "first.sema.svg").write_text(fixture, encoding="utf-8")
            (project / "second.sema.svg").write_text(
                fixture.replace('data-sema-project="fixture-valid"', 'data-sema-project="other-project"'),
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertIn("E221", {issue.code for issue in issues})


class MaterializedLabelTest(unittest.TestCase):
    def test_materialization_preserves_source_and_escapes_interpolation(self) -> None:
        source = """<svg xmlns=\"http://www.w3.org/2000/svg\">\n  <!-- <text id='derived' data-sema-type='core:label'>comment decoy</text> -->\n  <text>préface</text>\n  <rect id=\"device\" data-sema-entity=\"device-a\" data-sema-name=\"A&amp;B\"/>\n  <text id='derived' data-note='x > y' data-sema-type='core:label' data-sema-for='device-a' data-sema-x-label-template='Load {data-sema-name}'>café stale</text>\n</svg>\n"""
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "labels.svg"
            file.write_text(source, encoding="utf-8")

            result = materialize_labels(file)
            updated = file.read_text(encoding="utf-8")

        self.assertEqual([], result.issues)
        self.assertEqual(1, result.stale_labels)
        self.assertEqual(
            source.replace(">café stale</text>", ">Load A&amp;B</text>"),
            updated,
        )

    def test_check_mode_detects_stale_labels_without_writing(self) -> None:
        source = """<svg xmlns=\"http://www.w3.org/2000/svg\"><rect data-sema-entity=\"device-a\" data-sema-rated-current-a=\"16\"/><text id=\"derived\" data-sema-type=\"core:label\" data-sema-for=\"device-a\" data-sema-x-label-template=\"{data-sema-rated-current-a}A\">stale</text></svg>"""
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "labels.svg"
            file.write_text(source, encoding="utf-8")

            stale_result = materialize_labels(file, check=True)
            self.assertEqual(source, file.read_text(encoding="utf-8"))
            with patch.object(sys, "argv", ["semasvg", "materialize-labels", str(file), "--check"]):
                with redirect_stdout(StringIO()):
                    cli_status = main()
            current_result = materialize_labels(file)
            no_op_result = materialize_labels(file, check=True)

            self.assertEqual(1, stale_result.stale_labels)
            self.assertEqual([], stale_result.issues)
            self.assertEqual(1, cli_status)
            self.assertEqual([], current_result.issues)
            self.assertEqual([], no_op_result.issues)
            self.assertEqual(0, no_op_result.stale_labels)

    def test_materialization_supports_prefixed_svg_text(self) -> None:
        source = (
            '<svg:svg xmlns:svg="http://www.w3.org/2000/svg">'
            '<svg:rect data-sema-entity="device-a" data-sema-rated-current-a="16"/>'
            '<svg:text id="derived" data-sema-type="core:label" data-sema-for="device-a" '
            'data-sema-x-label-template="{data-sema-rated-current-a}A">stale</svg:text>'
            "</svg:svg>"
        )
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "labels.svg"
            file.write_text(source, encoding="utf-8")

            result = materialize_labels(file)

            self.assertEqual(
                source.replace(">stale</svg:text>", ">16A</svg:text>"),
                file.read_text(encoding="utf-8"),
            )
        self.assertEqual([], result.issues)

    def test_materialization_rejects_self_closing_derived_label_without_writing(self) -> None:
        source = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<rect data-sema-entity="device-a" data-sema-rated-current-a="16"/>'
            '<text id="derived" data-sema-type="core:label" data-sema-for="device-a" '
            'data-sema-x-label-template="{data-sema-rated-current-a}A"/>'
            "</svg>"
        )
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "labels.svg"
            file.write_text(source, encoding="utf-8")

            result = materialize_labels(file)

            self.assertEqual(source, file.read_text(encoding="utf-8"))
        self.assertEqual(1, len(result.issues))
        self.assertIn("self-closing", result.issues[0].message)

    def test_materialization_rejects_a_missing_target_path_in_api_and_cli_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.svg"

            result = materialize_labels(missing)
            with patch.object(sys, "argv", ["semasvg", "materialize-labels", str(missing)]):
                with redirect_stdout(StringIO()):
                    materialize_status = main()
            with patch.object(sys, "argv", ["semasvg", "materialize-labels", str(missing), "--check"]):
                with redirect_stdout(StringIO()):
                    check_status = main()

        self.assertEqual(1, len(result.issues))
        self.assertIn("does not exist", result.issues[0].message)
        self.assertEqual(1, materialize_status)
        self.assertEqual(1, check_status)

    def test_materialization_rejects_invalid_templates_and_nested_content(self) -> None:
        source = """<svg xmlns=\"http://www.w3.org/2000/svg\"><rect data-sema-entity=\"device-a\"/><text id=\"bad-template\" data-sema-type=\"core:label\" data-sema-for=\"device-a\" data-sema-x-label-template=\"{missing\">stale</text><text id=\"nested\" data-sema-type=\"core:label\" data-sema-for=\"device-a\" data-sema-x-label-template=\"{data-sema-name}\"><tspan>stale</tspan></text></svg>"""
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "labels.svg"
            file.write_text(source, encoding="utf-8")
            result = materialize_labels(file)

        self.assertEqual(2, len(result.issues))
        self.assertIn("invalid", result.issues[0].message)
        self.assertIn("nested", result.issues[1].message)

    def test_reference_panel_labels_are_materialized(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"

        result = materialize_labels(project, check=True)

        self.assertEqual([], result.issues)
        self.assertEqual(0, result.stale_labels)

    def test_manifest_selects_only_declared_views_and_leaves_unlisted_files_untouched(self) -> None:
        stale = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect data-sema-entity="device-a" '
            'data-sema-name="Current"/><text id="derived" data-sema-type="core:label" '
            'data-sema-for="device-a" data-sema-x-label-template="{data-sema-name}">stale</text></svg>'
        )
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            declared = project / "declared.sema.svg"
            unlisted = project / "unlisted.sema.svg"
            declared.write_text(stale, encoding="utf-8")
            unlisted.write_text("<svg>", encoding="utf-8")
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: label-project\nprofiles: {}\nviews:\n"
                "  - id: declared\n    file: declared.sema.svg\n    kind: system-overview\n",
                encoding="utf-8",
            )

            result = materialize_labels(project)

            self.assertEqual([], result.issues)
            self.assertEqual(1, result.updated_files)
            self.assertIn(">Current</text>", declared.read_text(encoding="utf-8"))
            self.assertEqual("<svg>", unlisted.read_text(encoding="utf-8"))

    def test_manifestless_directory_remains_recursive_and_direct_manifest_matches_directory(self) -> None:
        stale = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect data-sema-entity="device-a" '
            'data-sema-name="Current"/><text id="derived" data-sema-type="core:label" '
            'data-sema-for="device-a" data-sema-x-label-template="{data-sema-name}">stale</text></svg>'
        )
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            first = project / "first.sema.svg"
            second = project / "nested" / "second.sema.svg"
            second.parent.mkdir()
            first.write_text(stale, encoding="utf-8")
            second.write_text(stale, encoding="utf-8")

            recursive = materialize_labels(project)

            self.assertEqual([], recursive.issues)
            self.assertEqual(2, recursive.updated_files)
            first.write_text(stale, encoding="utf-8")
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: label-project\nprofiles: {}\nviews:\n"
                "  - id: first\n    file: first.sema.svg\n    kind: system-overview\n",
                encoding="utf-8",
            )

            directory_result = materialize_labels(project, check=True)
            manifest_result = materialize_labels(project / "semasvg.project.yaml", check=True)

        self.assertEqual(1, directory_result.stale_labels)
        self.assertEqual(directory_result, manifest_result)

    def test_invalid_or_empty_manifest_never_partially_writes_labels(self) -> None:
        stale = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect data-sema-entity="device-a" '
            'data-sema-name="Current"/><text id="derived" data-sema-type="core:label" '
            'data-sema-for="device-a" data-sema-x-label-template="{data-sema-name}">stale</text></svg>'
        )
        manifests = (
            ("semasvg: [\n", "E401"),
            (
                "semasvg: 0.1.0\nproject: label-project\nprofiles: {}\nviews:\n  - id: declared\n"
                "    file: declared.sema.svg\n    kind: system-overview\n  - id: outside\n"
                "    file: ../outside.svg\n    kind: system-overview\n",
                "E404",
            ),
            ("semasvg: 0.1.0\nproject: label-project\nprofiles: {}\nviews: []\n", None),
        )
        for manifest, expected_code in manifests:
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                source = project / "declared.sema.svg"
                source.write_text(stale, encoding="utf-8")
                (project / "semasvg.project.yaml").write_text(manifest, encoding="utf-8")

                result = materialize_labels(project)

                self.assertNotEqual([], result.issues)
                if expected_code is not None:
                    self.assertIn(expected_code, {issue.code for issue in result.issues})
                self.assertEqual(stale, source.read_text(encoding="utf-8"))

    def test_symlinked_svg_targets_are_rejected_before_any_write(self) -> None:
        stale = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect data-sema-entity="device-a" '
            'data-sema-name="Current"/><text id="derived" data-sema-type="core:label" '
            'data-sema-for="device-a" data-sema-x-label-template="{data-sema-name}">stale</text></svg>'
        )
        for mode in ("direct", "direct-dangling", "manifest", "manifestless"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                regular = project / "regular.sema.svg"
                target = project / "target.sema.svg"
                selected = project / "linked.sema.svg"
                regular.write_text(stale, encoding="utf-8")
                if mode != "direct-dangling":
                    target.write_text(stale, encoding="utf-8")
                selected.symlink_to(target.name)

                if mode.startswith("direct"):
                    input_path = selected
                elif mode == "manifest":
                    (project / "semasvg.project.yaml").write_text(
                        "semasvg: 0.1.0\nproject: label-project\nprofiles: {}\nviews:\n"
                        "  - id: regular\n    file: regular.sema.svg\n    kind: system-overview\n"
                        "  - id: linked\n    file: linked.sema.svg\n    kind: system-overview\n",
                        encoding="utf-8",
                    )
                    input_path = project
                else:
                    input_path = project

                result = materialize_labels(input_path)
                cli_status: int | None = None
                if mode.startswith("direct"):
                    with patch.object(sys, "argv", ["semasvg", "materialize-labels", str(selected)]):
                        with redirect_stdout(StringIO()):
                            cli_status = main()

                self.assertNotEqual([], result.issues)
                self.assertTrue(any("symlink" in issue.message for issue in result.issues))
                self.assertEqual(0, result.updated_files)
                if cli_status is not None:
                    self.assertEqual(1, cli_status)
                self.assertEqual(stale, regular.read_text(encoding="utf-8"))
                if mode != "direct-dangling":
                    self.assertEqual(stale, target.read_text(encoding="utf-8"))

    def test_symlinked_manifest_does_not_fall_back_to_manifestless_selection(self) -> None:
        stale = (
            '<svg xmlns="http://www.w3.org/2000/svg"><rect data-sema-entity="device-a" '
            'data-sema-name="Current"/><text id="derived" data-sema-type="core:label" '
            'data-sema-for="device-a" data-sema-x-label-template="{data-sema-name}">stale</text></svg>'
        )
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "regular.sema.svg"
            source.write_text(stale, encoding="utf-8")
            (project / "semasvg.project.yaml").symlink_to("missing-manifest.yaml")

            result = materialize_labels(project)

            self.assertEqual(stale, source.read_text(encoding="utf-8"))

        self.assertTrue(any("symlink" in issue.message for issue in result.issues))
        self.assertEqual(0, result.updated_files)


class HouseProjectTemplateTest(unittest.TestCase):
    def test_qa_runner_reports_ordered_summary_after_sigint(self) -> None:
        runner = REPO / "templates" / "house-project" / "scripts" / "run_qa.py"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fake = project / "semasvg"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import os, subprocess, sys, time\n"
                "from pathlib import Path\n"
                "if sys.argv[1] == 'validate':\n"
                "    raise SystemExit(0)\n"
                "if sys.argv[1] == 'format':\n"
                "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                "    Path('child-pid').write_text(str(child.pid))\n"
                "    Path('active').write_text(str(os.getpid()))\n"
                "    while True:\n"
                "        time.sleep(0.1)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = subprocess.Popen(
                [sys.executable, str(runner), "--semasvg", str(fake), "--jobs", "1"],
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            def stop_runner() -> None:
                if result.poll() is None:
                    result.send_signal(signal.SIGINT)
                    try:
                        result.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        result.kill()
                        result.communicate()

            self.addCleanup(stop_runner)
            marker = project / "active"
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists(), "format command did not become active")
            result.send_signal(signal.SIGINT)
            stdout, stderr = result.communicate(timeout=5)

            self.assertEqual(130, result.returncode, stderr)
            self.assertLess(stdout.index("PASS validate"), stdout.index("FAIL format"))
            self.assertLess(stdout.index("FAIL format"), stdout.index("ERROR labels: QA run was interrupted"))
            self.assertLess(
                stdout.index("ERROR labels: QA run was interrupted"),
                stdout.index("ERROR graph: QA run was interrupted"),
            )
            child_pid = int((project / "child-pid").read_text(encoding="utf-8"))

            def child_is_running() -> bool:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    return False
                return True

            deadline = time.monotonic() + 5
            while child_is_running() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(child_is_running(), "interrupted child survived")

    def test_qa_runner_keeps_going_and_reports_failures_in_declared_order(self) -> None:
        runner = REPO / "templates" / "house-project" / "scripts" / "run_qa.py"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fake = project / "semasvg"
            fake.write_text(
                "#!/usr/bin/env python3\nimport sys\n"
                "for index in range(1, 131):\n    print(f'line {index}')\n"
                "raise SystemExit(1 if sys.argv[1] == 'validate' else 0)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = subprocess.run(
                [
                    sys.executable, str(runner), "--semasvg", str(fake), "--jobs", "2",
                ],
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertLess(result.stdout.index("FAIL validate"), result.stdout.index("PASS format"))
            self.assertLess(result.stdout.index("PASS format"), result.stdout.index("PASS labels"))
            self.assertLess(result.stdout.index("PASS labels"), result.stdout.index("PASS graph"))
            self.assertIn("line 1", result.stdout)
            self.assertIn("line 80", result.stdout)
            self.assertIn("10 line(s) omitted", result.stdout)
            self.assertIn("line 130", result.stdout)
            self.assertNotIn("line 81\n", result.stdout)
            for name in ("validate", "format", "labels", "graph"):
                self.assertTrue((project / f"var/qa/latest/{name}.log").exists())

            verbose = subprocess.run(
                [sys.executable, str(runner), "--semasvg", str(fake), "--verbose"],
                cwd=project, capture_output=True, text=True, check=False,
            )
            self.assertIn("line 81", verbose.stdout)
            self.assertNotIn("omitted", verbose.stdout)

    def test_qa_runner_prefers_error_exit_over_failure(self) -> None:
        runner = REPO / "templates" / "house-project" / "scripts" / "run_qa.py"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fake = project / "semasvg"
            fake.write_text(
                "#!/usr/bin/env python3\nimport os, sys\n"
                "os.unlink(sys.argv[0]) if sys.argv[1] == 'validate' else None\n"
                "raise SystemExit(1 if sys.argv[1] == 'validate' else 0)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(runner), "--semasvg", str(fake), "--jobs", "1"],
                cwd=project, capture_output=True, text=True, check=False,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("FAIL validate", result.stdout)
        self.assertIn("ERROR format", result.stdout)

    def test_qa_runner_prints_short_failure_without_omission_marker(self) -> None:
        runner = REPO / "templates" / "house-project" / "scripts" / "run_qa.py"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fake = project / "semasvg"
            fake.write_text(
                "#!/usr/bin/env python3\nimport sys\nprint('complete short failure')\nraise SystemExit(1)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = subprocess.run(
                [sys.executable, str(runner), "--semasvg", str(fake)], cwd=project,
                capture_output=True, text=True, check=False,
            )
        self.assertIn("complete short failure", result.stdout)
        self.assertNotIn("omitted", result.stdout)

    def test_qa_runner_rejects_symlinked_var_and_cleans_latest(self) -> None:
        runner = REPO / "templates" / "house-project" / "scripts" / "run_qa.py"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            target = project / "target"
            target.mkdir()
            (project / "var").symlink_to(target, target_is_directory=True)
            rejected = subprocess.run([sys.executable, str(runner), "--semasvg", "missing"], cwd=project,
                                      capture_output=True, text=True, check=False)
            self.assertEqual(2, rejected.returncode)
            self.assertEqual([], list(target.iterdir()))
            (project / "var").unlink()
            fake = project / "semasvg"
            fake.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            fake.chmod(0o755)
            latest = project / "var/qa/latest"
            latest.mkdir(parents=True)
            (latest / "stale.log").write_text("stale", encoding="utf-8")
            passed = subprocess.run([sys.executable, str(runner), "--semasvg", str(fake)], cwd=project,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(0, passed.returncode)
            self.assertFalse((latest / "stale.log").exists())

            lock_target = project / "lock-target"
            lock_target.write_text("preserve", encoding="utf-8")
            (project / "var/qa/.lock").unlink()
            (project / "var/qa/.lock").symlink_to(lock_target)
            locked = subprocess.run([sys.executable, str(runner), "--semasvg", str(fake)], cwd=project,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(2, locked.returncode)
            self.assertEqual("preserve", lock_target.read_text(encoding="utf-8"))

    def test_starter_model_passes_consumer_quality_commands(self) -> None:
        greenfield = REPO / "templates" / "house-project"
        additive = REPO / "templates" / "house-model"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "house-project"
            host = root / "established-repository"
            host.mkdir()
            (host / "Makefile").write_text("host:\n", encoding="utf-8")
            shutil.copytree(greenfield, project)
            shutil.copytree(additive, host / "house")

            for model in (project / "model", host / "house" / "model"):
                validation_issues = validate(model)
                formatting = format_path(model, check=True)
                labels = materialize_labels(model, check=True)
                graph = inspect_graph(model)

                self.assertEqual([], [issue for issue in validation_issues if issue.severity == "ERROR"])
                self.assertEqual([], formatting.issues)
                self.assertEqual(0, formatting.stale_files)
                self.assertEqual([], labels.issues)
                self.assertEqual(0, labels.stale_labels)
                self.assertEqual([], graph["entities"])
                self.assertEqual([], graph["edges"])

            self.assertEqual("host:\n", (host / "Makefile").read_text(encoding="utf-8"))
            self.assertFalse((host / "house" / "Makefile").exists())
            self.assertEqual({"AGENTS.md", "README.md", "model"}, {entry.name for entry in additive.iterdir()})
            for relative in ("README.md", "semasvg.project.yaml", "views/project-overview.sema.svg"):
                self.assertEqual(
                    (greenfield / "model" / relative).read_bytes(),
                    (additive / "model" / relative).read_bytes(),
                )


class ProjectManifestValidationTest(unittest.TestCase):
    def test_reference_floor_paints_device_faces_after_routes_without_duplicate_symbols(self) -> None:
        root = ET.parse(REPO / "examples/reference/renovation-demo/ground-floor.sema.svg").getroot()
        elements = list(root.iter())
        routes = [e for e in elements if e.get("data-sema-type") == "electrical:route-segment"]
        devices = [e for e in elements if e.get("data-sema-type") in {
            "electrical:panel", "electrical:socket", "electrical:light", "electrical:switch",
        }]
        crossings = next(e for e in elements if e.get("id") == "electrical-route-crossovers")

        self.assertTrue(routes)
        self.assertTrue(devices)
        self.assertLess(max(elements.index(e) for e in routes), elements.index(crossings))
        self.assertLess(elements.index(crossings), min(elements.index(e) for e in devices))
        self.assertEqual(len(devices), len({e.get("data-sema-entity") for e in devices}))
        device_ids = {"#" + e.get("id", "") for e in devices}
        self.assertFalse(any(e.get("href") in device_ids for e in elements))

    def test_reference_section_stair_opening_and_column_match_their_physical_context(self) -> None:
        root = ET.parse(REPO / "examples/reference/renovation-demo/building-section.sema.svg").getroot()
        entities = {e.get("data-sema-entity"): e for e in root.iter() if e.get("data-sema-entity")}
        column = entities["column-center"]
        roof_points = _parse_polyline_points(entities["roof-main"].get("points", ""))
        column_points = _parse_polyline_points(column.get("points", ""))
        tip = min(column_points, key=lambda point: point[1])
        ground = entities["level-ground"]
        zero_y = float(ground.get("y", "0")) + float(ground.get("height", "0"))
        self.assertIn(tip, roof_points)
        self.assertEqual(zero_y - tip[1], float(column.get("data-sema-z-max-mm", "0")))

        opening = entities["opening-stair-first"]
        slab = entities[opening.get("data-sema-host")]
        stair = entities["stair-main"]
        landing = _parse_polyline_points(stair.get("points", ""))[-1]
        self.assertEqual("building:opening", opening.get("data-sema-type"))
        self.assertEqual("passage", opening.get("data-sema-opening-kind"))
        self.assertEqual(stair.get("data-sema-connects-levels"), opening.get("data-sema-connects-levels"))
        self.assertEqual(float(slab.get("y", "0")), landing[1])
        self.assertEqual(float(opening.get("x", "0")) + float(opening.get("width", "0")), landing[0])
        for attribute in ("y", "height", "data-sema-z-min-mm", "data-sema-z-max-mm"):
            self.assertEqual(slab.get(attribute), opening.get(attribute))
        for element in (column, opening):
            self.assertEqual("estimated", element.get("data-sema-certainty"))
            self.assertEqual("synthetic-design", element.get("data-sema-source"))

    def test_reference_floor_cable_assemblies_are_complete_nonbranching_chains(self) -> None:
        floor = REPO / "examples" / "reference" / "renovation-demo" / "ground-floor.sema.svg"
        root = ET.parse(floor).getroot()
        cables = [
            element for element in root.iter()
            if element.get("data-sema-type") == "electrical:cable"
        ]
        self.assertEqual(
            {
                "cable-general-sockets", "cable-kitchen-sockets", "cable-office-sockets", "cable-hob",
                "cable-lighting-ground", "cable-general-sockets-corridor-trunk", "cable-general-sockets-bathroom",
                "cable-general-sockets-utility", "cable-general-sockets-living", "cable-general-sockets-terrace",
                "cable-general-sockets-service", "cable-lighting-bedroom", "cable-lighting-kitchen",
                "cable-lighting-living", "cable-lighting-office", "cable-lighting-bathroom", "cable-lighting-utility",
                "cable-lighting-terrace", "cable-lighting-entrance", "cable-lighting-service", "cable-lighting-west-facade",
            },
            {cable.get("data-sema-entity") for cable in cables},
        )
        for cable in cables:
            cable_id = cable.get("data-sema-entity", "")
            routes = [child for child in cable if child.get("data-sema-type") == "electrical:route-segment"]
            self.assertNotEqual([], routes, cable_id)
            self.assertTrue(all(route.get("data-sema-cable") == cable_id for route in routes), cable_id)
            self.assertTrue(all(route.get("data-sema-circuit") == cable.get("data-sema-circuit") for route in routes), cable_id)
            by_source = {route.get("data-sema-from"): route for route in routes}
            self.assertEqual(len(routes), len(by_source), cable_id)
            visited: list[ET.Element] = []
            endpoint = {
                "terminal-outgoing-c1": "panel-main",
                "terminal-outgoing-c2": "panel-main",
                "terminal-outgoing-c3": "panel-main",
                "terminal-outgoing-c4": "panel-main",
                "terminal-outgoing-c5": "panel-main",
            }.get(cable.get("data-sema-from"), cable.get("data-sema-from"))
            while endpoint in by_source:
                route = by_source[endpoint]
                self.assertNotIn(route, visited, cable_id)
                visited.append(route)
                endpoint = route.get("data-sema-to")
            self.assertEqual(len(routes), len(visited), cable_id)
            self.assertEqual(cable.get("data-sema-to"), endpoint, cable_id)

    def test_reference_floor_routes_reach_every_declared_load_from_the_panel(self) -> None:
        floor = REPO / "examples" / "reference" / "renovation-demo" / "ground-floor.sema.svg"
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(floor).getroot()
        layout_root = ET.parse(layout).getroot()
        entities = {
            element.get("data-sema-entity")
            for element in root.iter()
            if element.get("data-sema-entity") is not None
        }
        routes_by_circuit: dict[str, list[tuple[str, str]]] = {
            circuit: []
            for circuit in REFERENCE_PANEL_CIRCUITS
        }
        layout_cables = {
            element.get("data-sema-circuit"): element
            for element in layout_root.iter()
            if element.get("data-sema-type") == "electrical:cable"
            and element.get("data-sema-circuit") in REFERENCE_PANEL_CIRCUITS
        }
        self.assertEqual(set(REFERENCE_PANEL_CIRCUITS), set(layout_cables))
        for circuit, cable in layout_cables.items():
            self.assertEqual(REFERENCE_PANEL_CIRCUITS[circuit][1], cable.get("data-sema-from"))

        cable_elements = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:cable"
        }

        route_geometry_by_entity: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
        for element in root.iter():
            if element.get("data-sema-type") != "electrical:route-segment":
                continue
            circuit = element.get("data-sema-circuit")
            self.assertIn(circuit, routes_by_circuit)
            route_from = element.get("data-sema-from")
            route_to = element.get("data-sema-to")
            self.assertIn(route_from, entities)
            self.assertIn(route_to, entities)
            self.assertEqual("planned", element.get("data-sema-state"))
            self.assertEqual("estimated", element.get("data-sema-certainty"))
            self.assertEqual("synthetic-design", element.get("data-sema-source"))
            cable = element.get("data-sema-cable")
            self.assertIn(cable, cable_elements)
            self.assertEqual(circuit, cable_elements[cable].get("data-sema-circuit"))
            routes_by_circuit[circuit].append((route_from, route_to))
            route_geometry_by_entity[element.get("data-sema-entity", "")] = (
                _parse_orthogonal_path_endpoints(element.get("d", ""))
            )

        for circuit, routes in routes_by_circuit.items():
            self.assertNotEqual([], routes, circuit)
            reachable = {"panel-main"}
            while True:
                expanded = reachable | {
                    route_to
                    for route_from, route_to in routes
                    if route_from in reachable
                }
                if expanded == reachable:
                    break
                reachable = expanded

            loads = {
                element.get("data-sema-entity")
                for element in root.iter()
                if element.get("data-sema-circuit") == circuit
                and element.get("data-sema-type") in {
                    "electrical:appliance",
                    "electrical:light",
                    "electrical:socket",
                }
            }
            self.assertTrue(loads.issubset(reachable), (circuit, loads - reachable))

        # Each physical cable has one continuous nonbranching floor route graph.
        routes_by_cable: dict[str, list[tuple[str, str]]] = {}
        for element in root.iter():
            if element.get("data-sema-type") == "electrical:route-segment":
                routes_by_cable.setdefault(element.get("data-sema-cable", ""), []).append(
                    (element.get("data-sema-from", ""), element.get("data-sema-to", ""))
                )
        for cable, cable_routes in routes_by_cable.items():
            starts = [route[0] for route in cable_routes]
            ends = [route[1] for route in cable_routes]
            self.assertTrue(all(starts.count(endpoint) <= 1 for endpoint in starts), cable)
            self.assertTrue(all(ends.count(endpoint) <= 1 for endpoint in ends), cable)

        route_elements = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:route-segment"
        }
        incoming_by_endpoint: dict[str, list[str]] = {}
        outgoing_by_endpoint: dict[str, list[str]] = {}
        for entity, element in route_elements.items():
            incoming_by_endpoint.setdefault(element.get("data-sema-to", ""), []).append(entity)
            outgoing_by_endpoint.setdefault(element.get("data-sema-from", ""), []).append(entity)
        for endpoint in incoming_by_endpoint.keys() & outgoing_by_endpoint.keys():
            # The floor-plan panel is an intentional proxy for five separate outgoing terminals.
            if endpoint == "panel-main":
                continue
            endpoint_coordinates = {
                route_geometry_by_entity[entity][1]
                for entity in incoming_by_endpoint[endpoint]
            } | {
                route_geometry_by_entity[entity][0]
                for entity in outgoing_by_endpoint[endpoint]
            }
            self.assertEqual(1, len(endpoint_coordinates), endpoint)

    def test_reference_hosted_routes_stay_inside_shared_pathways(self) -> None:
        floor = REPO / "examples" / "reference" / "renovation-demo" / "ground-floor.sema.svg"
        root = ET.parse(floor).getroot()
        pathways = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:pathway"
        }
        expected_bounds = {
            "pathway-corridor": (720.0, 4060.0, 11100.0, 4490.0),
            "pathway-exterior-south": (4500.0, 7300.0, 8300.0, 7300.0),
            "pathway-exterior-east": (11600.0, 4000.0, 11600.0, 7400.0),
        }
        self.assertEqual(set(expected_bounds), set(pathways))

        routes_by_pathway: dict[str, list[ET.Element]] = {
            pathway: []
            for pathway in pathways
        }
        for route in root.iter():
            if route.get("data-sema-type") != "electrical:route-segment":
                continue
            host = route.get("data-sema-host")
            if host is None:
                continue
            self.assertIn(host, pathways, route.get("data-sema-entity"))
            routes_by_pathway[host].append(route)

        for pathway, routes in routes_by_pathway.items():
            self.assertNotEqual([], routes, pathway)
            self.assertGreaterEqual(
                len({route.get("data-sema-circuit") for route in routes}),
                2,
                pathway,
            )
            self.assertGreaterEqual(
                len({route.get("data-sema-cable") for route in routes}),
                2,
                pathway,
            )
            min_x, min_y, max_x, max_y = expected_bounds[pathway]
            for route in routes:
                for x, y in _parse_orthogonal_path_points(route.get("d", "")):
                    self.assertGreaterEqual(x, min_x, route.get("data-sema-entity"))
                    self.assertLessEqual(x, max_x, route.get("data-sema-entity"))
                    self.assertGreaterEqual(y, min_y, route.get("data-sema-entity"))
                    self.assertLessEqual(y, max_y, route.get("data-sema-entity"))

    def test_reference_floor_has_planned_general_sockets_in_bathroom_and_utility(self) -> None:
        floor = REPO / "examples" / "reference" / "renovation-demo" / "ground-floor.sema.svg"
        root = ET.parse(floor).getroot()
        sockets = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:socket"
        }
        expected_spaces = {
            "socket-bathroom-service": "room-bathroom",
            "socket-utility-service": "room-utility",
        }
        for entity, space in expected_spaces.items():
            socket = sockets[entity]
            self.assertEqual(space, socket.get("data-sema-space"))
            self.assertEqual("wall-bathroom-utility", socket.get("data-sema-host"))
            self.assertEqual("circuit-general-sockets", socket.get("data-sema-circuit"))
            self.assertEqual("planned", socket.get("data-sema-state"))
            self.assertEqual("estimated", socket.get("data-sema-certainty"))
            self.assertEqual("synthetic-design", socket.get("data-sema-source"))

    def test_reference_floor_routes_use_explicit_wall_penetrations(self) -> None:
        floor = REPO / "examples" / "reference" / "renovation-demo" / "ground-floor.sema.svg"
        root = ET.parse(floor).getroot()
        by_entity = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-entity") is not None
        }
        wall_entities = {
            entity
            for entity, element in by_entity.items()
            if element.get("data-sema-type") == "building:wall"
        }
        referenced_penetrations = {
            endpoint
            for route in root.iter()
            if route.get("data-sema-type") == "electrical:route-segment"
            for endpoint in (route.get("data-sema-from"), route.get("data-sema-to"))
            if endpoint is not None
            and by_entity[endpoint].get("data-sema-type") == "electrical:penetration"
        }

        self.assertNotEqual(set(), referenced_penetrations)
        for entity in referenced_penetrations:
            penetration = by_entity[entity]
            self.assertIn(penetration.get("data-sema-host"), wall_entities, entity)
            self.assertIn(penetration.get("data-sema-circuit"), REFERENCE_PANEL_CIRCUITS, entity)

    def test_reference_floor_switches_resolve_to_lights(self) -> None:
        floor = REPO / "examples" / "reference" / "renovation-demo" / "ground-floor.sema.svg"
        root = ET.parse(floor).getroot()
        by_entity = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-entity") is not None
        }
        switches = [
            element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:switch"
        ]

        self.assertNotEqual([], switches)
        for switch in switches:
            controlled = switch.get("data-sema-controls-entities", "").split()
            self.assertNotEqual([], controlled, switch.get("data-sema-entity"))
            for entity in controlled:
                self.assertEqual("electrical:light", by_entity[entity].get("data-sema-type"))
        self.assertEqual(
            "light-bathroom-main",
            by_entity["switch-bathroom-main"].get("data-sema-controls-entities"),
        )
        self.assertEqual(
            "light-utility-main",
            by_entity["switch-utility-main"].get("data-sema-controls-entities"),
        )

    def test_reference_covered_spaces_resolve_to_roofs(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        manifest = yaml.safe_load((project / "semasvg.project.yaml").read_text(encoding="utf-8"))
        representations: dict[str, list[ET.Element]] = {}
        covered_spaces: list[ET.Element] = []
        for view in manifest["views"]:
            root = ET.parse(project / view["file"]).getroot()
            for element in root.iter():
                entity = element.get("data-sema-entity")
                if entity is not None:
                    representations.setdefault(entity, []).append(element)
                if element.get("data-sema-x-covered-by") is not None:
                    covered_spaces.append(element)

        self.assertNotEqual([], covered_spaces)
        for space in covered_spaces:
            roof = space.get("data-sema-x-covered-by", "")
            self.assertTrue(
                any(element.get("data-sema-type") == "building:roof" for element in representations.get(roof, [])),
                space.get("data-sema-entity"),
            )

    def test_reference_site_reuses_floor_entities_with_local_translation(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        floor_root = ET.parse(project / "ground-floor.sema.svg").getroot()
        site_root = ET.parse(project / "site-plan.sema.svg").getroot()
        floor_entities = {
            element.get("data-sema-entity"): element
            for element in floor_root.iter()
            if element.get("data-sema-entity") is not None
        }
        site_entities = {
            element.get("data-sema-entity"): element
            for element in site_root.iter()
            if element.get("data-sema-entity") is not None
        }
        shared_entities = {
            "wall-exterior-north", "wall-exterior-south", "wall-exterior-west", "wall-exterior-east",
            "opening-entrance-east", "terrace-open", "terrace-covered", "space-service-covered",
            "space-service-court", "path-south-pedestrian", "path-east-pedestrian", "light-terrace-covered",
            "light-entrance-east", "light-service-covered", "light-west-facade",
        }
        self.assertTrue(shared_entities.issubset(floor_entities))
        self.assertTrue(shared_entities.issubset(site_entities))
        for entity in shared_entities:
            self.assertEqual(
                floor_entities[entity].get("data-sema-type"),
                site_entities[entity].get("data-sema-type"),
                entity,
            )

        translated_rectangles = {
            "wall-exterior-north", "wall-exterior-south", "wall-exterior-west", "wall-exterior-east",
            "opening-entrance-east", "terrace-open", "terrace-covered", "space-service-covered",
            "space-service-court",
        }
        for entity in translated_rectangles:
            floor_element = floor_entities[entity]
            floor_geometry = floor_element if floor_element.tag.endswith("rect") else next(
                child for child in floor_element if child.tag.endswith("rect")
            )
            site_geometry = site_entities[entity]
            self.assertEqual(float(floor_geometry.get("x", "nan")) + 5000, float(site_geometry.get("x", "nan")), entity)
            self.assertEqual(float(floor_geometry.get("y", "nan")) + 3000, float(site_geometry.get("y", "nan")), entity)
            self.assertEqual(floor_geometry.get("width"), site_geometry.get("width"), entity)
            self.assertEqual(floor_geometry.get("height"), site_geometry.get("height"), entity)

        for entity in ("path-south-pedestrian", "path-east-pedestrian"):
            floor_points = _parse_orthogonal_path_points(floor_entities[entity].get("d", ""))
            site_points = _parse_orthogonal_path_points(site_entities[entity].get("d", ""))
            self.assertEqual([(x + 5000, y + 3000) for x, y in floor_points], site_points, entity)

        south_path = _parse_orthogonal_path_points(site_entities["path-south-pedestrian"].get("d", ""))
        east_path = _parse_orthogonal_path_points(site_entities["path-east-pedestrian"].get("d", ""))
        gate = site_entities["gate-main"]
        entrance = site_entities["opening-entrance-east"]
        self.assertEqual(south_path[-1], east_path[0])
        self.assertEqual(
            (float(gate.get("x", "nan")) + float(gate.get("width", "nan")) / 2,
             float(gate.get("y", "nan")) + float(gate.get("height", "nan")) / 2),
            south_path[-1],
        )
        self.assertEqual(
            (float(entrance.get("x", "nan")) + float(entrance.get("width", "nan")),
             float(entrance.get("y", "nan")) + float(entrance.get("height", "nan")) / 2),
            east_path[-1],
        )

        for entity in ("light-terrace-covered", "light-entrance-east", "light-service-covered", "light-west-facade"):
            transform = floor_entities[entity].get("transform", "")
            match = re.fullmatch(r"translate\((-?(?:\d+(?:\.\d*)?|\.\d+)) (-?(?:\d+(?:\.\d*)?|\.\d+))\)", transform)
            self.assertIsNotNone(match, entity)
            assert match is not None
            floor_x, floor_y = (float(value) for value in match.groups())
            self.assertEqual(floor_x + 5000, float(site_entities[entity].get("cx", "nan")), entity)
            self.assertEqual(floor_y + 3000, float(site_entities[entity].get("cy", "nan")), entity)

        self.assertEqual("0 0 22000 15000", site_root.get("viewBox"))
        self.assertEqual("sliding", site_entities["gate-main"].get("data-sema-opening-operation"))

    def test_reference_panel_has_a_non_overlapping_24_module_physical_layout(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()

        self.assertEqual("physical", root.get("data-sema-coordinate-mode"))
        self.assertEqual("mm", root.get("data-sema-unit"))
        panel = next(
            element
            for element in root.iter()
            if element.get("data-sema-entity") == "panel-main"
        )
        self.assertEqual("24", panel.get("data-sema-module-capacity"))
        rails = [
            element.get("data-sema-entity")
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:din-rail"
        ]
        self.assertEqual(["din-rail-1", "din-rail-2"], rails)
        self.assertEqual(12, int(panel.get("data-sema-module-capacity", "0")) // len(rails))

        intervals_by_rail: dict[str, list[tuple[int, int]]] = {rail: [] for rail in rails}
        for element in root.iter():
            rail = element.get("data-sema-rail")
            if rail is None:
                continue
            start = int(element.get("data-sema-slot-start", "0"))
            modules = int(element.get("data-sema-module-count", "0"))
            self.assertIn(rail, intervals_by_rail)
            self.assertGreaterEqual(start, 1)
            self.assertLessEqual(start + modules - 1, 12)
            intervals_by_rail[rail].append((start, start + modules - 1))

        for intervals in intervals_by_rail.values():
            ordered = sorted(intervals)
            has_no_overlap = all(
                previous[1] < current[0]
                for previous, current in zip(ordered, ordered[1:])
            )
            self.assertTrue(has_no_overlap)

    def test_reference_panel_uses_the_18mm_module_grid_and_narrow_rails(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        rails = {
            element.get("data-sema-entity"): next(
                child
                for child in element
                if child.get("data-sema-role") == "geometry"
            )
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:din-rail"
        }
        self.assertEqual({"din-rail-1", "din-rail-2"}, set(rails))
        for geometry in rails.values():
            self.assertLessEqual(float(geometry.get("height", "inf")), 35)
            self.assertLessEqual(float(geometry.get("width", "inf")), 230)

        for element in root.iter():
            if element.get("data-sema-rail") not in rails:
                continue
            geometry = next(
                child
                for child in element
                if child.get("data-sema-role") == "geometry"
            )
            slot_start = int(element.get("data-sema-slot-start", "0"))
            module_count = int(element.get("data-sema-module-count", "0"))
            self.assertEqual(117 + (slot_start - 1) * 18, float(geometry.get("x", "nan")))
            self.assertEqual(module_count * 18, float(geometry.get("width", "nan")))
            rail_geometry = rails[element.get("data-sema-rail")]
            rail_x = float(rail_geometry.get("x", "nan"))
            rail_y = float(rail_geometry.get("y", "nan"))
            rail_width = float(rail_geometry.get("width", "nan"))
            rail_height = float(rail_geometry.get("height", "nan"))
            self.assertLessEqual(rail_x, float(geometry.get("x", "nan")))
            self.assertLessEqual(float(geometry.get("x", "nan")) + float(geometry.get("width", "nan")), rail_x + rail_width)
            self.assertLessEqual(float(geometry.get("y", "nan")), rail_y)
            self.assertGreaterEqual(float(geometry.get("y", "nan")) + float(geometry.get("height", "nan")), rail_y + rail_height)

    def test_reference_panel_device_terminals_are_vertical_edge_anchors(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        anchors = _reference_panel_terminal_anchors(root)
        device_geometry = {
            element.get("data-sema-entity"): next(
                child
                for child in element
                if child.get("data-sema-role") == "geometry"
            )
            for element in root.iter()
            if element.get("data-sema-type") in {"electrical:device", "electrical:protective-device"}
        }
        for terminal in root.iter():
            parent = terminal.get("data-sema-parent")
            entity = terminal.get("data-sema-entity")
            if parent not in device_geometry or entity is None:
                continue
            geometry = device_geometry[parent]
            x = float(geometry.get("x", "nan"))
            y = float(geometry.get("y", "nan"))
            width = float(geometry.get("width", "nan"))
            height = float(geometry.get("height", "nan"))
            anchor_x, anchor_y = anchors[entity]
            self.assertLessEqual(x, anchor_x, entity)
            self.assertLessEqual(anchor_x, x + width, entity)
            self.assertIn(anchor_y, {y, y + height}, entity)

    def test_reference_panel_meter_has_distinct_top_inputs_and_bottom_outputs(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        anchors = _reference_panel_terminal_anchors(root)
        meter = next(
            element
            for element in root.iter()
            if element.get("data-sema-entity") == "meter-main"
        )
        geometry = next(child for child in meter if child.get("data-sema-role") == "geometry")
        top = float(geometry.get("y", "nan"))
        bottom = top + float(geometry.get("height", "nan"))
        self.assertEqual((126.0, top), anchors["meter-main-l-in"])
        self.assertEqual((144.0, top), anchors["meter-main-n-in"])
        self.assertEqual((126.0, bottom), anchors["meter-main-l-out"])
        self.assertEqual((144.0, bottom), anchors["meter-main-n-out"])

    def test_reference_panel_uses_the_intended_single_rail_protection_layout(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        by_entity = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-entity") is not None
        }
        expected_rail_positions = {
            "meter-main": ("din-rail-1", "1", "2"),
            "main-isolator": ("din-rail-1", "3", "2"),
            "rcbo-hob": ("din-rail-1", "5", "2"),
            "rccb-general-circuits": ("din-rail-1", "7", "2"),
            "breaker-kitchen-sockets": ("din-rail-1", "9", "1"),
            "breaker-office-sockets": ("din-rail-1", "10", "1"),
            "breaker-general-sockets": ("din-rail-1", "11", "1"),
            "breaker-lighting-ground": ("din-rail-1", "12", "1"),
        }
        for entity, expected in expected_rail_positions.items():
            element = by_entity[entity]
            actual = (
                element.get("data-sema-rail"),
                element.get("data-sema-slot-start"),
                element.get("data-sema-module-count"),
            )
            self.assertEqual(expected, actual, entity)

        protective_kinds = [
            element.get("data-sema-device-kind")
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:protective-device"
        ]
        self.assertEqual(1, protective_kinds.count("rcbo"))
        self.assertEqual(1, protective_kinds.count("rcd"))
        self.assertEqual(4, protective_kinds.count("mcb"))
        self.assertTrue(all(
            element.get("data-sema-rail") != "din-rail-2"
            for element in root.iter()
            if element.get("data-sema-rail") is not None
        ))

        for entity in ("busbar-main-phase-distribution", "busbar-main-neutral-distribution"):
            self.assertIsNone(by_entity[entity].get("data-sema-rail"))
            self.assertIsNone(by_entity[entity].get("data-sema-slot-start"))
            self.assertIsNone(by_entity[entity].get("data-sema-module-count"))

    def test_reference_panel_field_terminals_are_not_mounted_protective_devices(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        outgoing_groups = [
            element
            for element in root.iter()
            if element.get("data-sema-terminal-kind") == "grouped-L-N-PE-outgoing"
        ]

        self.assertEqual(5, len(outgoing_groups))
        for terminal in outgoing_groups:
            self.assertEqual("electrical:terminal", terminal.get("data-sema-type"))
            self.assertIsNone(terminal.get("data-sema-rail"))
            self.assertIsNone(terminal.get("data-sema-slot-start"))
            self.assertIsNone(terminal.get("data-sema-module-count"))

    def test_reference_panel_distributes_isolator_outputs_through_dedicated_blocks(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        conductors = {
            element.get("data-sema-entity"): (
                element.get("data-sema-from"),
                element.get("data-sema-to"),
            )
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:conductor"
        }
        expected = {
            "conductor-main-phase-distribution": (
                "main-isolator-l-out",
                "busbar-main-phase-distribution-in",
            ),
            "conductor-main-neutral-distribution": (
                "main-isolator-n-out",
                "busbar-main-neutral-distribution-in",
            ),
            "conductor-hob-input": (
                "busbar-main-phase-distribution-tap-c4",
                "rcbo-hob-l-in",
            ),
            "conductor-rccb-input": (
                "busbar-main-phase-distribution-tap-rccb",
                "rccb-general-circuits-l-in",
            ),
            "conductor-hob-neutral-input": (
                "busbar-main-neutral-distribution-tap-c4",
                "rcbo-hob-n-in",
            ),
            "conductor-rccb-neutral-input": (
                "busbar-main-neutral-distribution-tap-rccb",
                "rccb-general-circuits-n-in",
            ),
        }
        for entity, endpoints in expected.items():
            self.assertEqual(endpoints, conductors[entity], entity)

        isolator_outputs = [
            endpoints
            for endpoints in conductors.values()
            if endpoints[0] in {"main-isolator-l-out", "main-isolator-n-out"}
        ]
        self.assertCountEqual(
            [
                ("main-isolator-l-out", "busbar-main-phase-distribution-in"),
                ("main-isolator-n-out", "busbar-main-neutral-distribution-in"),
            ],
            isolator_outputs,
        )

    def test_reference_panel_keeps_rcbo_neutral_separate_from_the_rccb_neutral_bar(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        anchors = _reference_panel_terminal_anchors(root)
        rccb_circuits = {
            element.get("data-sema-circuit")
            for element in root.iter()
            if element.get("data-sema-parent") == "busbar-neutral"
            and element.get("data-sema-terminal-kind") == "N-tap"
        }
        pe_circuits = {
            element.get("data-sema-circuit")
            for element in root.iter()
            if element.get("data-sema-parent") == "busbar-pe"
            and element.get("data-sema-terminal-kind") == "PE-tap"
        }
        self.assertEqual(
            {
                "circuit-kitchen-sockets",
                "circuit-office-sockets",
                "circuit-general-sockets",
                "circuit-lighting-ground",
            },
            rccb_circuits,
        )
        self.assertEqual(set(REFERENCE_PANEL_CIRCUITS), pe_circuits)
        self.assertEqual((356.0, 260.0), anchors["busbar-neutral-in"])
        self.assertEqual((60.0, 260.0), anchors["busbar-pe-in"])
        self.assertEqual(
            [(364.0, 272.0), (374.0, 272.0), (384.0, 272.0), (394.0, 272.0)],
            [
                anchors[f"busbar-neutral-tap-{code}"]
                for code in ("c2", "c3", "c1", "c5")
            ],
        )
        self.assertEqual(
            [(68.0, 272.0), (76.0, 272.0), (84.0, 272.0), (92.0, 272.0), (100.0, 272.0)],
            [
                anchors[f"busbar-pe-tap-{code}"]
                for code in ("c4", "c2", "c3", "c1", "c5")
            ],
        )
        self.assertGreater(anchors["busbar-neutral-in"][0], 333.0)
        self.assertLess(anchors["busbar-pe-in"][0], 117.0)

    def test_reference_panel_has_one_circuit_protective_device_per_origin_circuit(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        layout_root = ET.parse(project / "panel-main-layout.sema.svg").getroot()
        panel_circuits = {
            element.get("data-sema-entity")
            for element in layout_root.iter()
            if element.get("data-sema-type") == "electrical:circuit"
            and element.get("data-sema-origin") == "panel-main"
        }
        protection_by_circuit: dict[str, list[ET.Element]] = {
            circuit: []
            for circuit in panel_circuits
            if circuit is not None
        }
        for element in layout_root.iter():
            circuit = element.get("data-sema-circuit")
            if (
                element.get("data-sema-type") == "electrical:protective-device"
                and circuit in protection_by_circuit
            ):
                protection_by_circuit[circuit].append(element)

        self.assertEqual(5, len(panel_circuits))
        self.assertTrue(all(len(devices) == 1 for devices in protection_by_circuit.values()))
        rccb = next(
            element
            for element in layout_root.iter()
            if element.get("data-sema-entity") == "rccb-general-circuits"
        )
        self.assertIsNone(rccb.get("data-sema-circuit"))

    def test_reference_reuses_outgoing_cable_properties_across_views(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        layout_root = ET.parse(project / "panel-main-layout.sema.svg").getroot()
        floor_root = ET.parse(project / "ground-floor.sema.svg").getroot()
        cable_attributes = (
            "data-sema-type",
            "data-sema-system",
            "data-sema-from",
            "data-sema-to",
            "data-sema-circuit",
            "data-sema-core-count",
            "data-sema-core-cross-section-mm2",
            "data-sema-cable-description",
            "data-sema-state",
            "data-sema-certainty",
            "data-sema-source",
        )
        outgoing_cables = [
            element
            for element in layout_root.iter()
            if element.get("data-sema-type") == "electrical:cable"
            and element.get("data-sema-circuit") is not None
        ]

        self.assertEqual(5, len(outgoing_cables))
        for outgoing_cable in outgoing_cables:
            entity = outgoing_cable.get("data-sema-entity")
            repeated_cables = [
                element
                for element in floor_root.iter()
                if element.get("data-sema-entity") == entity
            ]
            self.assertEqual(1, len(repeated_cables), entity)
            repeated_cable = repeated_cables[0]
            for attribute in cable_attributes:
                self.assertEqual(outgoing_cable.get(attribute), repeated_cable.get(attribute), (entity, attribute))

    def test_reference_panel_layout_is_the_circuit_authority(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        manifest = yaml.safe_load((project / "semasvg.project.yaml").read_text(encoding="utf-8"))
        layout_root = ET.parse(project / "panel-main-layout.sema.svg").getroot()
        floor_root = ET.parse(project / "ground-floor.sema.svg").getroot()
        expected_codes = {
            circuit: code
            for circuit, (code, _) in REFERENCE_PANEL_CIRCUITS.items()
        }

        self.assertEqual(
            ["site-plan", "ground-floor", "building-section", "panel-main-layout"],
            [view["id"] for view in manifest["views"]],
        )
        self.assertFalse((project / "panel-main-schematic.sema.svg").exists())
        self.assertEqual(
            ["system-electrical"],
            [
                element.get("data-sema-entity")
                for element in layout_root.iter()
                if element.get("data-sema-type") == "electrical:system"
            ],
        )
        circuit_codes = {
            element.get("data-sema-entity"): element.get("data-sema-x-circuit-code")
            for element in layout_root.iter()
            if element.get("data-sema-type") == "electrical:circuit"
        }
        self.assertEqual(expected_codes, circuit_codes)

        semantic_context = next(child for child in layout_root if child.get("id") == "semantic-context")
        self.assertFalse(any(element.get("data-sema-role") == "geometry" for element in semantic_context.iter()))
        supplies = [
            element
            for element in semantic_context
            if element.get("data-sema-entity") == "supply-main"
        ]
        self.assertEqual(1, len(supplies))
        supply = supplies[0]
        self.assertEqual(
            {
                "data-sema-type": "electrical:supply",
                "data-sema-system": "system-electrical",
                "data-sema-supply-kind": "utility",
                "data-sema-voltage-v": "230",
                "data-sema-frequency-hz": "50",
                "data-sema-phases": "1",
                "data-sema-state": "existing",
            },
            {attribute: supply.get(attribute) for attribute in (
                "data-sema-type", "data-sema-system", "data-sema-supply-kind", "data-sema-voltage-v",
                "data-sema-frequency-hz", "data-sema-phases", "data-sema-state",
            )},
        )
        feeder = next(
            element
            for element in semantic_context
            if element.get("data-sema-entity") == "cable-panel-feeder"
        )
        self.assertEqual(
            {
                "data-sema-system": "system-electrical",
                "data-sema-from": "meter-main",
                "data-sema-to": "main-isolator",
                "data-sema-core-count": "2",
                "data-sema-core-cross-section-mm2": "10",
                "data-sema-cable-description": "2 x 10 mm2 panel feeder",
                "data-sema-state": "planned",
            },
            {attribute: feeder.get(attribute) for attribute in (
                "data-sema-system", "data-sema-from", "data-sema-to", "data-sema-core-count",
                "data-sema-core-cross-section-mm2", "data-sema-cable-description", "data-sema-state",
            )},
        )
        for entity in (
            "panel-main", "cable-service-entry", "meter-main", "main-isolator", "rcbo-hob", "rccb-general-circuits",
        ):
            representation = next(element for element in layout_root.iter() if element.get("data-sema-entity") == entity)
            self.assertEqual("system-electrical", representation.get("data-sema-system"), entity)

        for root in (layout_root, floor_root):
            labels_by_circuit: dict[str, set[str]] = {}
            for element in root.iter():
                circuit = element.get("data-sema-for")
                if circuit in expected_codes:
                    labels_by_circuit.setdefault(circuit, set()).add("".join(element.itertext()).strip())
            for circuit, code in expected_codes.items():
                labels = labels_by_circuit.get(circuit, set())
                self.assertTrue(
                    any(label == code or label.startswith(code + " ") for label in labels),
                    (root.get("data-sema-view"), circuit),
                )

    def test_reference_panel_outgoing_terminals_match_circuits_and_cables(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        root = ET.parse(project / "panel-main-layout.sema.svg").getroot()
        expected = {
            circuit: terminal
            for circuit, (_, terminal) in REFERENCE_PANEL_CIRCUITS.items()
        }
        terminals = {
            element.get("data-sema-circuit"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:terminal"
            and element.get("data-sema-terminal-kind") == "grouped-L-N-PE-outgoing"
        }
        cables = {
            element.get("data-sema-circuit"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:cable"
            and element.get("data-sema-circuit") in expected
        }

        self.assertEqual(set(expected), set(terminals))
        self.assertEqual(set(expected), set(cables))
        for circuit, terminal in terminals.items():
            self.assertEqual(expected[circuit], terminal.get("data-sema-entity"))
            self.assertEqual("panel-main", terminal.get("data-sema-parent"))
            self.assertEqual(expected[circuit], cables[circuit].get("data-sema-from"))


    def test_reference_panel_layout_has_complete_final_circuit_wiring(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        root = ET.parse(project / "panel-main-layout.sema.svg").getroot()
        circuits = set(REFERENCE_PANEL_CIRCUITS)
        conductor_kinds: dict[str, set[str]] = {circuit: set() for circuit in circuits}
        for element in root.iter():
            circuit = element.get("data-sema-circuit")
            if element.get("data-sema-type") == "electrical:conductor" and circuit in conductor_kinds:
                self.assertEqual("planned", element.get("data-sema-state"))
                self.assertEqual("estimated", element.get("data-sema-certainty"))
                self.assertEqual("synthetic-design", element.get("data-sema-source"))
                self.assertIsNotNone(element.get("data-sema-from"))
                self.assertIsNotNone(element.get("data-sema-to"))
                conductor_kinds[circuit].add(element.get("data-sema-conductor-kind", ""))

        self.assertEqual({circuit: {"L", "N", "PE"} for circuit in circuits}, conductor_kinds)
        entities = {
            element.get("data-sema-entity")
            for element in root.iter()
            if element.get("data-sema-entity") is not None
        }
        self.assertTrue(
            {"contactor-water-heater", "timer-water-heater", "power-supply-controls"}.isdisjoint(entities)
        )
        neutral_paths = {
            (element.get("data-sema-from"), element.get("data-sema-to"))
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:conductor"
            and element.get("data-sema-conductor-kind") == "N"
        }
        self.assertTrue(
            {
                ("main-isolator-n-out", "busbar-main-neutral-distribution-in"),
                ("busbar-main-neutral-distribution-tap-c4", "rcbo-hob-n-in"),
                ("busbar-main-neutral-distribution-tap-rccb", "rccb-general-circuits-n-in"),
                ("rccb-general-circuits-n-out", "busbar-neutral-in"),
            }.issubset(neutral_paths)
        )

    def test_reference_panel_uses_explicit_paint_layers_and_semantic_context(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        layout_root = ET.parse(project / "panel-main-layout.sema.svg").getroot()

        direct_children = list(layout_root)
        layer_indices = {
            element.get("id"): index
            for index, element in enumerate(direct_children)
            if element.get("id") in {
                "layer-panel-routes",
                "layer-device-bodies",
                "layer-terminal-ferrules",
                "layer-labels",
            }
        }
        self.assertEqual(
            ["layer-panel-routes", "layer-device-bodies", "layer-terminal-ferrules", "layer-labels"],
            sorted(layer_indices, key=layer_indices.get),
        )
        semantic_context = next(child for child in direct_children if child.get("id") == "semantic-context")
        self.assertLess(
            direct_children.index(next(child for child in direct_children if child.get("id") == "layer-terminal-ferrules")),
            direct_children.index(semantic_context),
        )
        self.assertLess(
            direct_children.index(semantic_context),
            direct_children.index(next(child for child in direct_children if child.get("id") == "layer-labels")),
        )
        label_layer = next(
            element
            for element in direct_children
            if element.get("id") == "layer-labels"
        )
        self.assertFalse(any(
            element.tag.rsplit("}", 1)[-1] == "rect"
            for element in label_layer.iter()
        ))

    def test_reference_panel_busbar_terminal_anchors_land_on_busbar_geometry(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        root = ET.parse(project / "panel-main-layout.sema.svg").getroot()
        anchors = _reference_panel_terminal_anchors(root)
        busbars = {
            element.get("data-sema-entity"): element
            for element in root.iter()
            if element.get("data-sema-type") == "electrical:busbar"
        }
        for terminal in root.iter():
            parent = terminal.get("data-sema-parent")
            entity = terminal.get("data-sema-entity")
            if parent not in busbars or entity is None:
                continue
            geometries = [child for child in busbars[parent] if child.get("data-sema-role") == "geometry"]
            self.assertEqual(1, len(geometries), parent)
            geometry = geometries[0]
            x, y = anchors[entity]
            geometry_tag = geometry.tag.rsplit("}", 1)[-1]
            if geometry_tag == "rect":
                x1 = float(geometry.get("x", "nan"))
                y1 = float(geometry.get("y", "nan"))
                x2 = x1 + float(geometry.get("width", "nan"))
                y2 = y1 + float(geometry.get("height", "nan"))
                self.assertTrue(x in {x1, x2} or y in {y1, y2}, entity)
            else:
                self.assertEqual("line", geometry_tag, parent)
                x1, y1, x2, y2 = (float(geometry.get(attribute, "nan")) for attribute in ("x1", "y1", "x2", "y2"))
                cross_product = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
                self.assertEqual(0, cross_product, entity)
            self.assertLessEqual(min(x1, x2), x, entity)
            self.assertLessEqual(x, max(x1, x2), entity)
            self.assertLessEqual(min(y1, y2), y, entity)
            self.assertLessEqual(y, max(y1, y2), entity)

    def test_reference_panel_layout_conductors_land_on_terminal_anchors(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        anchors = _reference_panel_terminal_anchors(root)
        for conductor in root.iter():
            if conductor.get("data-sema-type") != "electrical:conductor":
                continue
            geometry = next(
                child
                for child in conductor
                if child.get("data-sema-role") == "geometry"
            )
            self.assertEqual("polyline", geometry.tag.rsplit("}", 1)[-1], conductor.get("data-sema-entity"))
            points = _parse_polyline_points(geometry.get("points", ""))
            self.assertGreaterEqual(len(points), 2, conductor.get("data-sema-entity"))
            self.assertEqual(anchors[conductor.get("data-sema-from", "")], points[0])
            self.assertEqual(anchors[conductor.get("data-sema-to", "")], points[-1])
            for previous, current in zip(points, points[1:]):
                self.assertTrue(
                    previous[0] == current[0] or previous[1] == current[1],
                    (conductor.get("data-sema-entity"), previous, current),
                )

    def test_reference_panel_device_terminal_anchors_are_distinct_in_layout(self) -> None:
        layout = REPO / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        root = ET.parse(layout).getroot()
        anchors = _reference_panel_terminal_anchors(root)
        device_entities = {
            element.get("data-sema-entity")
            for element in root.iter()
            if element.get("data-sema-type") in {"electrical:device", "electrical:protective-device"}
        }
        anchors_by_parent: dict[str, list[tuple[float, float]]] = {}
        for terminal in root.iter():
            parent = terminal.get("data-sema-parent")
            entity = terminal.get("data-sema-entity")
            if parent in device_entities and entity is not None:
                anchors_by_parent.setdefault(parent, []).append(anchors[entity])

        for parent, device_anchors in anchors_by_parent.items():
            if len(device_anchors) > 1:
                self.assertEqual(len(device_anchors), len(set(device_anchors)), parent)

    def test_existing_project_and_manifest_are_valid(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"

        self.assertEqual([], validate(project))
        self.assertEqual([], validate(project / "semasvg.project.yaml"))

    def test_reference_project_exercises_all_official_types_except_connection_points(self) -> None:
        project = REPO / "examples" / "reference" / "renovation-demo"
        manifest = yaml.safe_load((project / "semasvg.project.yaml").read_text(encoding="utf-8"))
        view_files = [project / view["file"] for view in manifest["views"]]
        svg_text = "\n".join(file.read_text(encoding="utf-8") for file in view_files)
        used_types = set(re.findall(r'data-sema-type="([^"]+)"', svg_text))

        for profile in ("building", "electrical"):
            vocabulary = yaml.safe_load((REPO / "vocab" / "profiles" / f"{profile}.yaml").read_text(encoding="utf-8"))
            registered_types = {definition["qualified"] for definition in vocabulary["types"].values()}
            omitted_types = registered_types - used_types
            if profile == "building":
                self.assertEqual(set(), omitted_types, "reference demo misses building types")
            else:
                self.assertEqual({"electrical:connection-point"}, omitted_types)

    def test_empty_valid_manifest_has_no_usable_svg_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "semasvg.project.yaml"
            manifest.write_text("semasvg: 0.1.0\nproject: temporary\nprofiles: {}\nviews: []\n", encoding="utf-8")

            issues = validate(manifest)

        self.assertIn("E000", {issue.code for issue in issues})

    def test_manifest_schema_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "semasvg.project.yaml"
            manifest.write_text("semasvg: 0.1.0\nproject: Invalid Name\nviews: []\n", encoding="utf-8")
            (project / "invalid.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "invalid" / "unqualified-type.sema.svg").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            issues = validate(manifest)

        codes = {issue.code for issue in issues}
        self.assertIn("E402", codes)
        self.assertIn("E205", codes)

    def test_manifest_requires_profiles_map_and_accepts_core_only_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('data-sema-profiles="building@0.1.0"', 'data-sema-profiles=""')
                .replace('        data-sema-entity="room-a"\n', '')
                .replace('data-sema-type="building:space"', 'data-sema-type="core:annotation"'),
                encoding="utf-8",
            )
            missing = project / "semasvg.project.yaml"
            missing.write_text(
                "semasvg: 0.1.0\nproject: fixture-valid\nviews:\n  - id: main\n    file: view.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )
            missing_issues = validate(project)
            missing.write_text(
                "semasvg: 0.1.0\nproject: fixture-valid\nprofiles: {}\nviews:\n  - id: main\n    file: view.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )
            core_only_issues = validate(project)

        self.assertIn("E402", {issue.code for issue in missing_issues})
        self.assertEqual([], [issue for issue in core_only_issues if issue.severity == "ERROR"])

    def test_malformed_manifest_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "semasvg.project.yaml"
            manifest.write_text("views: [\n", encoding="utf-8")

            issues = validate(manifest)

        self.assertIn("E401", {issue.code for issue in issues})

    def test_missing_manifest_view_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "semasvg.project.yaml"
            manifest.write_text(
                "semasvg: 0.1.0\nproject: temporary\nprofiles: {}\nviews:\n  - id: main\n    file: missing.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(manifest)

        self.assertIn("E405", {issue.code for issue in issues})

    def test_unsafe_manifest_view_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "semasvg.project.yaml"
            manifest.write_text(
                "semasvg: 0.1.0\nproject: temporary\nprofiles: {}\nviews:\n"
                "  - id: absolute\n    file: /tmp/outside.sema.svg\n    kind: floor-plan\n"
                "  - id: traversal\n    file: ../outside.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(manifest)

        self.assertEqual({"E403", "E404"}, {issue.code for issue in issues if issue.code in {"E403", "E404"}})

    def test_valid_manifest_ignores_unlisted_invalid_svg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            declared = project / "declared.sema.svg"
            declared.write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "unlisted.sema.svg").write_text("<svg><script /></svg>", encoding="utf-8")
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: fixture-valid\nprofiles:\n  building: 0.1.0\nviews:\n"
                "  - id: main\n    file: declared.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertEqual([], [issue for issue in issues if issue.severity == "ERROR"])

    def test_manifest_rejects_non_svg_declared_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.txt").write_text("not an SVG", encoding="utf-8")
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: temporary\nprofiles: {}\nviews:\n"
                "  - id: main\n    file: view.txt\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertIn("E406", {issue.code for issue in issues})

    def test_manifest_metadata_must_match_declared_view(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: other-project\nprofiles: {}\nviews:\n"
                "  - id: other-view\n    file: view.sema.svg\n    kind: schematic\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertEqual({"E408", "E409", "E410"}, {issue.code for issue in issues if issue.code in {"E408", "E409", "E410"}})

    def test_svg_profiles_must_match_manifest_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: fixture-valid\nprofiles:\n  electrical: 0.1.0\nviews:\n"
                "  - id: main\n    file: view.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertIn("E412", {issue.code for issue in issues})

    def test_unsupported_official_manifest_profile_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: fixture-valid\nprofiles:\n  building: 0.2.0\nviews:\n"
                "  - id: main\n    file: view.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertIn("E411", {issue.code for issue in issues})

    def test_manifest_must_not_declare_core_as_a_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: fixture-valid\nprofiles:\n"
                "  core: 0.1.0\n  building: 0.1.0\nviews:\n"
                "  - id: main\n    file: view.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertIn("E420", {issue.code for issue in issues})

    def test_manifest_and_svg_versions_must_be_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "view.sema.svg").write_text(
                (REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg")
                .read_text(encoding="utf-8")
                .replace('data-sema-version="0.1.0"', 'data-sema-version="0.2.0"'),
                encoding="utf-8",
            )
            (project / "semasvg.project.yaml").write_text(
                "semasvg: 0.2.0\nproject: fixture-valid\nprofiles: {}\nviews:\n"
                "  - id: main\n    file: view.sema.svg\n    kind: floor-plan\n",
                encoding="utf-8",
            )

            issues = validate(project)

        self.assertEqual({"E103", "E407"}, {issue.code for issue in issues if issue.code in {"E103", "E407"}})

    def test_svg_read_failure_is_reported(self) -> None:
        file = REPO / "tests" / "fixtures" / "valid" / "minimal.sema.svg"
        with patch("semasvg_validator.validator.ET.parse", side_effect=OSError("permission denied")):
            document, issues = parse_svg(file)

        self.assertIsNone(document)
        self.assertIn("E003", {issue.code for issue in issues})


class VocabularyValidationTest(unittest.TestCase):
    def test_existing_vocabulary_directory_is_valid(self) -> None:
        self.assertEqual([], validate_vocabulary(REPO / "vocab"))

    def test_normative_specification_attributes_are_registered(self) -> None:
        normative_specs = (
            REPO / "spec" / "core.md",
            REPO / "spec" / "profile-authoring.md",
            REPO / "spec" / "profiles" / "building.md",
            REPO / "spec" / "profiles" / "electrical.md",
        )
        attribute_pattern = re.compile(r"\bdata-sema-[a-z][a-z0-9-]*")
        documented_attributes = {
            attribute
            for spec in normative_specs
            for attribute in attribute_pattern.findall(spec.read_text(encoding="utf-8"))
            if not attribute.startswith("data-sema-x-")
        }

        registered_attributes: set[str] = set()
        for vocabulary_file in (REPO / "vocab").rglob("*.yaml"):
            vocabulary = yaml.safe_load(vocabulary_file.read_text(encoding="utf-8"))
            registered_attributes.update(vocabulary.get("attributes", {}))

        self.assertEqual(set(), documented_attributes - registered_attributes)

    def test_vocabulary_schema_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text("id: invalid\nversion: 0.1.0\n", encoding="utf-8")

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E402", {issue.code for issue in issues})

    def test_vocabulary_schema_validates_registry_entry_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text(
                "id: invalid\nversion: 0.1.0\ntitle: Invalid\n"
                "attributes:\n  data-sema-test: {kind: unsupported}\n"
                "types:\n  test: {}\n",
                encoding="utf-8",
            )

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E402", {issue.code for issue in issues})

    def test_vocabulary_schema_validates_lexical_registry_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text(
                "id: invalid\nversion: release\ntitle: Invalid\ntype_prefix: Invalid Prefix\n"
                "types:\n  Invalid_Key: {qualified: invalid}\n",
                encoding="utf-8",
            )

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E402", {issue.code for issue in issues})

    def test_vocabulary_schema_requires_type_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text("id: sample\nversion: 1.2.3\ntitle: Sample\n", encoding="utf-8")

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E402", {issue.code for issue in issues})

    def test_vocabulary_schema_requires_boolean_entity_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text(
                "id: sample\nversion: 1.2.3\ntitle: Sample\ntype_prefix: sample\n"
                "types:\n  item: {qualified: sample:item, entity_required: 'false'}\n",
                encoding="utf-8",
            )

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E402", {issue.code for issue in issues})

    def test_vocabulary_schema_requires_semantic_attribute_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text(
                "id: sample\nversion: 1.2.3\ntitle: Sample\ntype_prefix: sample\n"
                "attributes:\n  invalid-key: {kind: token}\n",
                encoding="utf-8",
            )

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E402", {issue.code for issue in issues})

    def test_vocabulary_cross_field_registry_metadata_is_validated(self) -> None:
        valid = (
            "id: sample\nversion: 1.2.3\ntitle: Sample\ntype_prefix: sample\n"
            "enums:\n  mode: [one]\n"
            "attributes:\n  data-sema-mode: {kind: enum, enum: mode}\n"
            "types:\n  item: {qualified: sample:item}\n"
        )
        invalid = valid.replace("sample:item", "other:item").replace("enum: mode", "enum: missing")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid_file = root / "valid.yaml"
            invalid_file = root / "invalid.yaml"
            valid_file.write_text(valid, encoding="utf-8")
            invalid_file.write_text(invalid, encoding="utf-8")

            valid_issues = validate_vocabulary(valid_file)
            invalid_issues = validate_vocabulary(invalid_file)

        self.assertEqual([], [issue for issue in valid_issues if issue.severity == "ERROR"])
        self.assertEqual({"E413", "E414"}, {issue.code for issue in invalid_issues if issue.code in {"E413", "E414"}})

    def test_vocabulary_type_prefix_must_match_vocabulary_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text(
                "id: sample\nversion: 1.2.3\ntitle: Sample\ntype_prefix: other\n"
                "types:\n  item: {qualified: other:item}\n",
                encoding="utf-8",
            )

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E415", {issue.code for issue in issues})

    def test_vocabulary_directory_rejects_duplicate_id_and_type_prefix(self) -> None:
        vocabulary = "id: shared\nversion: 1.2.3\ntitle: Shared\ntype_prefix: shared\n"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.yaml").write_text(vocabulary, encoding="utf-8")
            (root / "second.yaml").write_text(vocabulary, encoding="utf-8")

            issues = validate_vocabulary(root)

        self.assertEqual({"E416", "E417"}, {issue.code for issue in issues if issue.code in {"E416", "E417"}})

    def test_vocabulary_directory_rejects_incompatible_attribute_and_enum_definitions(self) -> None:
        first = (
            "id: first\nversion: 1.2.3\ntitle: First\ntype_prefix: first\n"
            "enums:\n  mode: [one]\nattributes:\n  data-sema-mode: {kind: token}\n"
        )
        second = (
            "id: second\nversion: 1.2.3\ntitle: Second\ntype_prefix: second\n"
            "enums:\n  mode: [two]\nattributes:\n  data-sema-mode: {kind: string}\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.yaml").write_text(first, encoding="utf-8")
            (root / "second.yaml").write_text(second, encoding="utf-8")

            issues = validate_vocabulary(root)

        self.assertEqual({"E418", "E419"}, {issue.code for issue in issues if issue.code in {"E418", "E419"}})

    def test_vocabulary_directory_allows_identical_shared_definitions(self) -> None:
        vocabulary = (
            "version: 1.2.3\n"
            "enums:\n  mode: [one]\n"
            "attributes:\n  data-sema-shared: {kind: entity-ref}\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.yaml").write_text(
                "id: first\ntitle: First\ntype_prefix: first\n" + vocabulary,
                encoding="utf-8",
            )
            (root / "second.yaml").write_text(
                "id: second\ntitle: Second\ntype_prefix: second\n" + vocabulary,
                encoding="utf-8",
            )

            issues = validate_vocabulary(root)

        self.assertEqual([], [issue for issue in issues if issue.severity == "ERROR"])

    def test_malformed_vocabulary_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vocabulary = Path(directory) / "invalid.yaml"
            vocabulary.write_text("title: [\n", encoding="utf-8")

            issues = validate_vocabulary(vocabulary)

        self.assertIn("E401", {issue.code for issue in issues})

    def test_packaged_schemas_match_canonical_schemas(self) -> None:
        for name in ("project.schema.json", "vocabulary.schema.json"):
            packaged = files("semasvg_validator.schemas").joinpath(name).read_bytes()
            canonical = (REPO / "schemas" / name).read_bytes()
            self.assertEqual(canonical, packaged, name)

    def test_packaged_vocabularies_match_canonical_vocabularies(self) -> None:
        for name in ("core.yaml", "profiles/building.yaml", "profiles/electrical.yaml"):
            packaged = files("semasvg_validator.vocab").joinpath(name).read_bytes()
            canonical = (REPO / "vocab" / name).read_bytes()
            self.assertEqual(canonical, packaged, name)


class CliValidationTest(unittest.TestCase):
    def test_invalid_yaml_commands_render_errors_and_exit_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "semasvg.project.yaml"
            vocabulary = root / "invalid.yaml"
            manifest.write_text("views: [\n", encoding="utf-8")
            vocabulary.write_text("title: [\n", encoding="utf-8")

            for command, target in (("validate", manifest), ("validate-vocabulary", vocabulary)):
                output = StringIO()
                with patch.object(sys, "argv", ["semasvg", command, str(target)]), redirect_stdout(output):
                    result = main()

                self.assertEqual(1, result)
                self.assertIn("ERROR E401", output.getvalue())
                self.assertIn("error(s), 0 warning(s)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
