# Roadmap

This roadmap is directional, not a promise of release dates. Completed release work is recorded in the
[changelog](CHANGELOG.md).

## 0.1.x - Stabilize the core vocabulary

- test SemaSVG against more real SVG editors;
- improve validator diagnostics;
- extend property-conflict warnings when additional entity-level property contracts are established;
- add more geometry consistency checks;
- stable canonicalization and editor integration remain future work.

## 0.2.x - Authoring and tooling

- generated vocabulary reference from YAML;
- editor integration experiments;
- stable error-code catalog;
- explore deterministic one-way, non-canonical graph exports from validated `inspect-graph` output, with Mermaid and
  Graphviz DOT as candidate formats; define concrete formats and compatibility in a later design or RFC when active;
- richer profile conformance levels, including type-specific property applicability and domain rules.
- consider independent distribution of the house starters and a future PyPI packaging decision; neither distribution
  path is active yet.

### Minimal authoring UI experiment

Explore this only after practical Inkscape editing identifies recurring friction. An initial tool could be a property
panel alongside an SVG editor, or a small standalone editor with a deliberately limited set of editable shapes.

The useful initial scope is adding simple shapes or symbols, selecting, moving and resizing them, editing SemaSVG
properties and relationships, and saving ordinary SVG. The panel could also expose native SVG `<title>` and `<desc>`
text. A complete general-purpose SVG editor is not a prerequisite.

Preserve unsupported SVG content, unknown attributes, unrelated geometry, and source/certainty annotations. Distinguish
creating a new entity from adding another representation of an existing entity. Keep stable IDs and references intact;
operate within the view's coordinate mode and keep saved project files passive. The editor's interactive behavior
belongs in the application, not embedded scripts in canonical SVG files.

This is a retained design direction, not an implemented editor or an active delivery commitment. Define a concrete
supported editing subset and preservation checks before starting implementation.

### Reference symbol and template libraries

- Explore a non-normative authoring aid grouped by profile and view kind, with room for regional or professional
  conventions.
- Keep entity classification semantic: `data-sema-type` and profile attributes, not appearance, determine entity type.

## 0.3.x - Third independent domain

Create a real third profile, preferably electronics/PCB, from an actual use case.

The purpose is not feature count. The purpose is to test whether the Core remains genuinely domain-neutral.

Likely concepts to test:

- board;
- component;
- pad/port;
- net;
- trace/route;
- schematic representation vs physical board representation;
- multiple views of the same entity.

## Future domain profiles

Building and Electrical should remain focused rather than becoming containers for every building-service discipline. New
official profiles should be driven by real projects and recurring domain rules. Likely candidates include:

- Plumbing and drainage: pipes, valves, manifolds, fixtures and waste routes;
- HVAC and heating: equipment, ducts, emitters, zones and control relationships;
- Structural: beams, foundations, materials, sections, reinforcement and calculation-oriented properties beyond
  Building's lightweight columns, slabs and roofs;
- Fire and security: detectors, alarm loops, cameras and safety zones;
- Data and networking: outlets, racks, links and network topology.

These profiles may reference Building spaces and hosts or Electrical supplies without redefining those entities.

## Toward 1.0

Do not release SemaSVG 1.0 until:

- Core has survived at least three substantially different domains;
- a validator exists and is used by examples;
- entity/view/profile semantics have stopped changing materially;
- extension rules are clear enough for third-party profiles;
- at least one external user has attempted implementation.
- a supported-editor and version round-trip compatibility matrix and smoke-test process have been defined from tested
  editor workflows.

Consider Brick, Haystack, PROV, and other ecosystem mappings only after concrete interoperability demand establishes a
useful contract.
