# Model source

`semasvg.project.yaml` is the canonical view index. Add only declared SVG views to the model and preserve stable
project-wide entity IDs. This starter intentionally contains only a diagrammatic Core annotation: it makes no claim
about a real property, layout, dimension, or installation.

`data-sema-type` classifies the modeled entity rather than its view. Keep one type across all representations of that
entity. Split entities only for truly distinct modeled subjects with separate identity or lifecycle, not to obtain
another category.

As a non-normative consumer convention, a stable house object ID may be reused as `data-sema-entity` when the same
object is represented. Home Assistant entity and device IDs, and other system IDs, are mutable aliases rather than
physical identity. Use non-validated Markdown tokens such as `entity:room-kitchen` and `source:original-plan-2024` for
entity and source-record references; in particular, `data-sema-source` is not a source-record pointer.
