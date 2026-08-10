from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1] / "src"))

from semasvg_validator.cli import main
from semasvg_validator.formatter import format_path, format_svg
from semasvg_validator.labels import materialize_labels


class FormatterTest(unittest.TestCase):
    def test_preserves_native_titles_and_descriptions_at_their_authored_scope(self) -> None:
        view_note = b'<desc>View note.\n  Keep this spacing &amp; punctuation.</desc>'
        object_note = b'<desc>Check &lt;clearance&gt; before choosing a model.</desc>'
        source = (
            b'<svg xmlns="http://www.w3.org/2000/svg"><title>Plan</title>' + view_note
            + b'<rect id="repr-cabinet" data-sema-entity="cabinet" '
            b'data-sema-type="building:furniture" width="600" height="1700">'
            b'<title> Cabinet </title>' + object_note + b'</rect></svg>'
        )

        formatted = format_svg(source)

        self.assertIn(b'  <title>Plan</title>\n  ' + view_note + b'\n  <rect', formatted)
        self.assertIn(b'    <title> Cabinet </title>\n    ' + object_note + b'\n  </rect>', formatted)
        self.assertEqual(formatted, format_svg(formatted))

    def test_formats_semantic_root_and_is_idempotent(self) -> None:
        source = b'<svg xmlns="http://www.w3.org/2000/svg" data-sema-project="p" data-sema-x-vendor="x"><rect id="a" width="1" height="2"/></svg>'
        formatted = format_svg(source)
        self.assertIn(b'<svg xmlns="http://www.w3.org/2000/svg"\n     data-sema-project="p"\n     data-sema-x-vendor="x">', formatted)
        self.assertIn(b'\n  <rect id="a" width="1" height="2"/>\n</svg>', formatted)
        self.assertEqual(formatted, format_svg(formatted))

    def test_preserves_lexical_constructs_and_mixed_content(self) -> None:
        source = b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "X">]><svg xmlns="u"><!-- keep --><g a=\'&x;\'><![CDATA[a < b]]><?go x?><text> a <tspan>b</tspan> c </text></g></svg>'
        formatted = format_svg(source)
        expected = b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "X">]><svg xmlns="u">\n  <!-- keep -->\n  <g a=\'&x;\'><![CDATA[a < b]]><?go x?><text> a <tspan>b</tspan> c </text></g>\n</svg>\n'
        self.assertEqual(expected, formatted)
        self.assertEqual(formatted, format_svg(formatted))

    def test_preserved_boundaries_are_indented_without_changing_content(self) -> None:
        source = b'<svg><g><text> raw <tspan>value</tspan> </text><style> .a { fill: red; } </style><x>left <b/> right</x><g xml:space = "preserve"><rect/>  keep </g><g xml:space=\'preserve\'><rect/>  keep too </g></g></svg>'
        formatted = format_svg(source)
        self.assertEqual(
            b'<svg>\n  <g>\n    <text> raw <tspan>value</tspan> </text>\n    <style> .a { fill: red; } </style>\n    <x>left <b/> right</x>\n    <g xml:space = "preserve"><rect/>  keep </g>\n    <g xml:space=\'preserve\'><rect/>  keep too </g>\n  </g>\n</svg>\n',
            formatted,
        )
        self.assertEqual(formatted, format_svg(formatted))

    def test_multiline_plain_style_uses_structural_boundaries_and_preserves_css_layout(self) -> None:
        source = b'<svg><g><style>\n.a { color: red; }\n  /* keep comment */\n  .b {\n    fill: blue;\n  }\n</style></g></svg>'
        formatted = format_svg(source)
        self.assertEqual(
            b'<svg>\n  <g>\n    <style>\n      .a { color: red; }\n        /* keep comment */\n        .b {\n          fill: blue;\n        }\n    </style>\n  </g>\n</svg>\n',
            formatted,
        )
        self.assertEqual(formatted, format_svg(formatted))

    def test_opaque_style_content_remains_byte_preserved(self) -> None:
        source = b'<svg><g><style><![CDATA[.a { color: red; }]]></style><style>one line</style></g></svg>'
        formatted = format_svg(source)
        self.assertIn(b'<style><![CDATA[.a { color: red; }]]></style>', formatted)
        self.assertIn(b'<style>one line</style>', formatted)
        self.assertEqual(formatted, format_svg(formatted))

    def test_inherited_xml_space_preserve_keeps_multiline_style_bytes(self) -> None:
        source = b'<svg><g xml:space="preserve"><style>\n  .a { color: red; }\n</style></g></svg>'
        formatted = format_svg(source)
        self.assertIn(b'<g xml:space="preserve"><style>\n  .a { color: red; }\n</style></g>', formatted)
        self.assertEqual(formatted, format_svg(formatted))

    def test_comments_and_processing_instructions_are_standalone_siblings(self) -> None:
        self.assertEqual(
            b"<svg>\n  <!-- comment text -->\n  <?target value?>\n  <g/>\n</svg>\n",
            format_svg(b"<svg><!-- comment text --><?target value?><g/></svg>"),
        )

    def test_check_is_read_only_and_preflight_blocks_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / "valid.svg"
            broken = root / "broken.svg"
            valid.write_bytes(b'<svg><g><rect/></g></svg>')
            broken.write_bytes(b'<svg>')
            original = valid.read_bytes()
            result = format_path(root)
            self.assertTrue(result.issues)
            self.assertEqual(original, valid.read_bytes())
            check = format_path(valid, check=True)
            self.assertEqual(1, check.stale_files)
            self.assertEqual(original, valid.read_bytes())

    def test_atomic_write_preserves_mode_and_manifest_selects_declared_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declared = root / "declared.svg"
            ignored = root / "ignored.svg"
            declared.write_bytes(b'<svg><g><rect/></g></svg>')
            ignored.write_bytes(b'<svg><g><circle/></g></svg>')
            os.chmod(declared, 0o640)
            (root / "semasvg.project.yaml").write_text(
                "semasvg: 0.1.0\nproject: temporary\nprofiles: {}\nviews:\n  - id: view\n    kind: floor-plan\n    file: declared.svg\n",
                encoding="utf-8",
            )
            result = format_path(root)
            self.assertFalse(result.issues)
            self.assertEqual(1, result.updated_files)
            self.assertEqual(0o640, declared.stat().st_mode & 0o777)
            self.assertEqual(b'<svg><g><circle/></g></svg>', ignored.read_bytes())

    def test_rejects_non_svg_missing_and_symlink_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "note.txt"
            text.write_text("x", encoding="utf-8")
            self.assertTrue(format_path(root / "missing.svg").issues)
            self.assertTrue(format_path(text).issues)
            target = root / "target.svg"
            target.write_text("<svg/>", encoding="utf-8")
            link = root / "link.svg"
            link.symlink_to(target)
            self.assertTrue(format_path(link).issues)

    def test_cli_rejects_a_symlink_without_resolving_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.svg"
            link = root / "link.svg"
            target.write_text("<svg/>", encoding="utf-8")
            link.symlink_to(target)
            output = StringIO()
            with redirect_stdout(output), patch.object(sys, "argv", ["semasvg", "format", str(link)]):
                self.assertEqual(1, main())
            self.assertIn("symlinked targets are not allowed", output.getvalue())

    def test_cli_output_and_exit_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "view.svg"
            file.write_bytes(b'<svg><g><rect/></g></svg>')
            output = StringIO()
            with redirect_stdout(output), patch.object(sys, "argv", ["semasvg", "format", "--check", str(file)]):
                self.assertEqual(1, main())
            self.assertEqual("1 unformatted file(s)\n", output.getvalue())
            with redirect_stdout(output := StringIO()), patch.object(sys, "argv", ["semasvg", "format", str(file)]):
                self.assertEqual(0, main())
            self.assertEqual("OK: formatted 1 file(s)\n", output.getvalue())
            with redirect_stdout(output := StringIO()), patch.object(sys, "argv", ["semasvg", "format", "--check", str(file)]):
                self.assertEqual(0, main())
            self.assertEqual("OK: SVG formatting is current\n", output.getvalue())

    def test_lexical_120_column_packing_and_prefixed_root(self) -> None:
        oversized = b'a="' + b"x" * 130 + b'"'
        source = b'<svg:svg xmlns:svg="u"><node one="1" two="2" ' + oversized + b' /></svg:svg>'
        formatted = format_svg(source)
        self.assertEqual(
            b'<svg:svg xmlns:svg="u">\n  <node\n        one="1" two="2"\n        ' + oversized + b'/>\n</svg:svg>\n',
            formatted,
        )
        self.assertEqual(formatted, format_svg(formatted))

    def test_expanded_attribute_continuations_align_after_element_name(self) -> None:
        source = (
            b'<svg><g><rect id="geometry" data-sema-role="geometry" width="120" height="80" '
            b'fill="none" stroke="black"/></g><svg xmlns="urn:example" data-sema-project="demo"/></svg>'
        )
        formatted = format_svg(source)
        self.assertIn(
            b'    <rect id="geometry"\n'
            b'          data-sema-role="geometry"\n'
            b'          width="120" height="80" fill="none" stroke="black"/>',
            formatted,
        )
        self.assertIn(
            b'  <svg xmlns="urn:example"\n'
            b'       data-sema-project="demo"/>',
            formatted,
        )
        self.assertEqual(formatted, format_svg(formatted))

    def test_unicode_element_name_uses_character_column_alignment(self) -> None:
        source = b'<svg><\xc3\xa9lement data-sema-role="geometry" width="12"/></svg>'
        formatted = format_svg(source)
        self.assertEqual(
            b'<svg>\n  <\xc3\xa9lement\n           data-sema-role="geometry"\n           width="12"/>\n</svg>\n',
            formatted,
        )
        self.assertEqual(formatted, format_svg(formatted))

    def test_recursive_hidden_manifest_and_invalid_target_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / ".hidden").mkdir()
            visible = root / "nested" / "visible.svg"
            hidden = root / ".hidden" / "hidden.svg"
            visible.write_text("<svg><g/></svg>", encoding="utf-8")
            hidden.write_text("<svg><g/></svg>", encoding="utf-8")
            self.assertEqual(1, format_path(root).updated_files)
            self.assertEqual(b"<svg><g/></svg>", hidden.read_bytes())
            manifest = root / "semasvg.project.yaml"
            manifest.write_text("semasvg: 0.1.0\nproject: temporary\nviews: []\n", encoding="utf-8")
            self.assertTrue(format_path(manifest).issues)
            manifest.write_text("semasvg: 0.1.0\nproject: temporary\nviews:\n  - id: v\n    kind: floor-plan\n    file: ../outside.svg\n", encoding="utf-8")
            self.assertTrue(format_path(manifest).issues)

    def test_manifest_and_non_utf8_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "view.svg"
            target.write_bytes(b"\xff")
            self.assertTrue(format_path(target).issues)
            real = root / "real.svg"
            real.write_text("<svg/>", encoding="utf-8")
            link = root / "view-link.svg"
            link.symlink_to(real)
            manifest = root / "semasvg.project.yaml"
            manifest.write_text("semasvg: 0.1.0\nproject: temporary\nviews:\n  - id: v\n    kind: floor-plan\n    file: view-link.svg\n", encoding="utf-8")
            self.assertTrue(format_path(manifest).issues)

    def test_formatting_keeps_derived_label_text_materializable(self) -> None:
        fixture = HERE.parents[3] / "examples" / "reference" / "renovation-demo" / "panel-main-layout.sema.svg"
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "panel.svg"
            file.write_bytes(fixture.read_bytes())
            self.assertFalse(format_path(file).issues)
            source = file.read_text(encoding="utf-8")
            file.write_text(source.replace("2P 63A", "outdated label", 1), encoding="utf-8")
            result = materialize_labels(file)
            self.assertFalse(result.issues)
            self.assertGreater(result.stale_labels, 0)
