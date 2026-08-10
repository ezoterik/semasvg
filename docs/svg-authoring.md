# SVG authoring

This practical, non-normative guide keeps SemaSVG source readable without changing its semantics. The
[Core specification](../spec/core.md) owns conformance requirements, while the
[validator README](../tools/validator/README.md) owns the exact formatter inputs, output, safety guarantees, and exit
codes.

## Safe workflow

```bash
semasvg format examples/reference/renovation-demo
semasvg format examples/reference/renovation-demo --check
semasvg validate examples/reference/renovation-demo
```

Format before review, use `--check` for read-only automation, and validate separately because formatting is not semantic
validation. Prefer `semasvg format` over generic whole-file XML formatting when source-preservation boundaries matter.

## Human editability and editor round trips

A SemaSVG file should remain useful as ordinary SVG if its `data-sema-*` attributes are stripped: the drawing, geometry,
labels, and presentation still communicate the view. Use a generic SVG editor for geometry and visible text, and use an
XML editor, text editor, or AI-assisted editing for semantic attributes. SemaSVG requires no custom authoring
application or editor UI.

No editor or editor version is certified until its round trip has been tested for the files in question. Exported,
optimized, or otherwise rewritten SVG is unverified until checked. To manually test an editor round trip:

1. Copy the source SVG and retain the original unchanged.
2. Open the copy in the selected editor, move one non-semantic item, and save without exporting or optimizing.
3. Inspect the Git diff and confirm that stable SVG IDs, `data-sema-*` attributes, and unknown attributes remain present
   and that unrelated semantics did not change.
4. Run `semasvg validate PATH` on the saved copy. Validation together with the attribute and diff inspection establishes
   semantic preservation for this manual check.
5. Run `semasvg format PATH --check`. A failure here can be source-layout drift rather than a semantic failure. If it
   reports drift, format the copy, inspect the normalized diff, and treat unexplained broad reserialization as a poor
   Git authoring workflow.

This checklist is a manual project practice. It does not imply validator enforcement or editor certification;
formatter-current output alone does not certify an editor.

### Physical shape and readable symbols

For composite objects in physical views, mark the actual shape explicitly and keep its label out of that shape:

```xml
<g id="repr-cabinet-plan" data-sema-entity="cabinet-main" data-sema-type="building:furniture">
  <rect data-sema-role="geometry" x="0" y="0" width="600" height="800"/>
  <text data-sema-role="label" x="900" y="400">Cabinet</text>
</g>
```

In this synthetic, untransformed millimeter example, the footprint is 600 by 800 mm. Moving the label further right does
not widen the cabinet. A nested entity keeps its own physical geometry. A group with no explicit physical geometry has
unspecified dimensions; do not measure a readable socket symbol as if it were the device's footprint. See
[Core's composite-geometry rules](../spec/core.md#83-physical-geometry-of-a-composite-representation). The baseline
validator does not calculate these dimensions.

Paint plan routes before their non-connecting crossover marks, and paint white-filled device symbols after both. The
device circle then hides the route's interior portion while the authored route still ends at its original connection
point. Keep light crosses consistently oriented; the incoming route communicates approach direction. Prefer moving the
original semantic symbol to a later paint layer over adding a second visible `<use>` copy. Labels and callouts can be
painted last without relocating the physical objects they describe.

Certainty and source are optional local annotations. Omit them when no claim is being made; a parent group's annotation
does not populate its children or another view. Explain mixed confidence or detailed source references in `<desc>` or
project documentation rather than adding confidence records for every property.

### Titles and human notes

Use optional native `<title>` and `<desc>` children for a short title and a longer note. Put them directly inside the
semantic root they describe, or inside the document's root `<svg>` for a view-wide description.

Use either element on its own when that is enough; they are not a required pair. For object-level examples, the
renovation floor plan gives the bedroom bed only a title, the dishwasher only a description, and the wardrobe both.

For example, both elements can describe a simple shape directly:

```xml
<rect id="repr-wardrobe-plan"
      data-sema-entity="wardrobe-main"
      data-sema-type="building:furniture"
      x="0" y="0" width="600" height="1700">
  <title>Wardrobe beside the bedroom wall</title>
  <desc>Check access to the existing socket before choosing the wardrobe. Vertical extent is not specified.</desc>
</rect>
```

This is a synthetic footprint example. A shape can contain descriptive elements without an extra `<g>` or a change to
its geometry. For a composite representation, put the text inside the semantic `<g>`, before its drawing elements.
Prefer plain text, put `<title>` first when present, and escape XML characters such as `&amp;` and `&lt;` normally.

The texts belong to this representation and may differ in another view. They do not supply missing semantic attributes
or another object's description. Keep visible labels in `<text>`; neither native descriptive element draws a label. An
editor should expose these texts on selection, with hover or focus as an additional convenience. Do not depend on a
browser to display the long note automatically, and do not add scripts to the saved SVG to implement a tooltip.

Preserve titles and descriptions during editor round trips. See the
[Core contract](../spec/core.md#181-native-titles-and-descriptions), the
[two-view example](../examples/minimal/two-views/README.md), and the wardrobe note in the
[renovation floor plan](../examples/reference/renovation-demo/ground-floor.sema.svg). The current `inspect-graph` output
contains semantic attributes and relationships, not native SVG descriptive text; read that text from the SVG.

### JetBrains XML inspections

Keep `xmlns="http://www.w3.org/2000/svg"` on SemaSVG roots. In PhpStorm and other JetBrains IDEs, the red
`Attribute data-sema-* is not allowed here` message comes from the built-in SVG schema. Create a project/custom
inspection scope for `*.sema.svg` and set the XML highlighting or invalid-attribute diagnostic to `No highlighting`;
continue using the SemaSVG CLI validator. Do not change the namespace, add SVG suppression comments, or map the SVG
namespace to a permissive custom XSD, as that weakens normal SVG validation. These settings are IDE-local because
`.idea` is ignored.

## Source layout

- use two-space structural indentation;
- keep semantic elements expanded and their `data-sema-*` attributes easy to scan;
- keep comments as standalone siblings near the geometry or ordering choice they explain;
- preserve stable SVG IDs, semantic entity IDs, relationships, unknown attributes, raw text, and mixed content;
- keep reusable presentation in one document-local top-level `<style>` when practical.

```xml
<!-- Draw the route after walls so its crossing remains visible. -->
<path id="repr-route-main"
      data-sema-entity="route-main"
      data-sema-type="electrical:route-segment"
      class="route"
      d="M40 80 H160"/>
```

Comments, visible text, color, and CSS classes are presentation aids, never the only semantic source. Keep geometry,
transforms, and unique presentation local when that makes a self-contained SVG clearer.
