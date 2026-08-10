# SemaSVG

SemaSVG is an experimental semantic convention for ordinary SVG, created as an open reference for editable plans and
diagrams. It keeps SVG readable and reviewable while making semantics explicit: `entity != representation`, so one
stable project entity can appear in a floor plan, site plan, panel layout, and schematic without becoming unrelated
objects.

```xml

<rect id="repr-room-bedroom-floor" data-sema-entity="room-bedroom" data-sema-type="building:space"
      data-sema-space-kind="room" data-sema-purpose="bedroom" data-sema-state="existing"/>
```

Core, Building, and Electrical are experimental pre-1.0 `0.1.0` baselines. SemaSVG is not CAD, BIM, GIS, or engineering
approval; profile data and synthetic examples do not establish installation suitability or regulatory compliance.

Start with [one room, two views](examples/minimal/two-views/README.md) to see how one entity keeps its identity across a
physical plan and a diagrammatic card.

For a broader house knowledge repository, SemaSVG is the human-reviewable 2D model and diagram layer. It complements,
rather than replaces, BIM or IFC, automation platforms, inventory records, and Markdown or source archives.

## Quick start

```bash
# Requires Python 3.11 or later.
make setup

# Validate the public reference project with the installed local CLI.
./.venv/bin/semasvg validate examples/reference/renovation-demo

# Run the complete contributor check.
make qa
```

| Owner                      | Start here                                                                                        |
|----------------------------|---------------------------------------------------------------------------------------------------|
| Normative semantics        | [Specifications](spec/README.md)                                                                  |
| Machine-readable resources | [Vocabulary](vocab/README.md) and [project schema](schemas/project.schema.json)                   |
| CLI contract               | [Validator](tools/validator/README.md)                                                            |
| Public synthetic example   | [Renovation demo](examples/reference/renovation-demo/README.md)                                   |
| Consumer house integration | [House repository guide](docs/house-repositories.md) and [starter templates](templates/README.md) |
| Practical documentation    | [Documentation router](docs/README.md)                                                            |

![Ground-floor reference preview](examples/reference/renovation-demo/ground-floor.sema.svg)

![Site-plan reference preview](examples/reference/renovation-demo/site-plan.sema.svg)

![Panel-layout reference preview](examples/reference/renovation-demo/panel-main-layout.sema.svg)

![Building-section reference preview](examples/reference/renovation-demo/building-section.sema.svg)

Use lower-kebab-case semantic entity IDs; SVG `id` values remain document-local representation IDs. SemaSVG originated
as a public design experiment by Oleg and is distributed under the repository [license](LICENSE).
