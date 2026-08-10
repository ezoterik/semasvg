# SemaSVG Core Specification

Status: project specification

Version: 0.1.0
Project name: SemaSVG

## 1. Purpose

SemaSVG Core is a lightweight semantic convention layered on ordinary SVG.

It allows one or more SVG files to represent real or logical entities while preserving the properties that make SVG useful:

- visual rendering in browsers;
- manual editing in tools such as Inkscape;
- XML readability;
- reviewable Git diffs;
- simple parsing without an editor-specific API.

SemaSVG Core is domain-neutral. It does not define what a wall, circuit breaker, water pipe or gate is. Domain profiles define those concepts.

## 2. Non-goals

SemaSVG Core is not intended to:

- replace IFC, BIM, CAD, GIS or electrical engineering standards;
- define every possible engineering property;
- guarantee regulatory compliance;
- require a database or a parallel JSON model;
- make SVG a full 3D scene format.

The design goal is a small semantic substrate that remains easy to inspect and edit.

## 3. Normative language

The terms MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative.

- MUST means required for conformance.
- SHOULD means strongly recommended unless there is a concrete reason to deviate.
- MAY means optional.

## Readability and formatting (non-normative)

Whitespace, attribute order, line wrapping, and comments do not carry SemaSVG
semantics and are not conformance requirements. Authors are encouraged to keep
XML readable and reviewable, but formatter output is neither required for
conformance nor a stable canonical SemaSVG representation. See the practical
[SVG authoring and formatting guide](../docs/svg-authoring.md).

## 4. Core model

SemaSVG separates five concepts that MUST NOT be conflated.

### 4.1 Project

A project is the collection of SVG views representing one subject or system.

Example:

```text
house-renovation-reference
```

Every semantic SVG document MUST declare:

```xml
data-sema-project="house-renovation-reference"
```

### 4.2 Entity

An entity is a stable semantic identity in the project.

Examples:

```text
building-main
room-kitchen
panel-main
circuit-hob
rcbo-hob
```

Entity IDs are project-wide semantic identifiers.

An entity may appear in multiple SVG files and in different kinds of views.

An entity normally models one subject that users need to identify. Do not create another entity merely to give the same
subject another category or to show it in another view. Two linked entities are appropriate only when they are genuinely
different subjects with separate identity or lifecycle, for example a persistent installation or functional slot and a
replaceable physical device. This split is optional: profiles should define the relationship when it is useful, and
authors MUST NOT invent either subject when the source does not establish it.

### 4.3 Representation

A representation is how an entity appears in a particular SVG view.

Example: `panel-main` can have:

```text
floor-plan representation
physical equipment-layout representation
schematic representation
```

The SVG `id` identifies the representation element inside that document.

`data-sema-entity` identifies the real or logical entity across the project.

Example:

```xml
<rect
    id="repr-panel-main-floor"
    data-sema-entity="panel-main"
    data-sema-type="electrical:panel"
/>
```

Another file may contain:

```xml
<g
    id="repr-panel-main-layout"
    data-sema-entity="panel-main"
    data-sema-type="electrical:panel"
>
    ...
</g>
```

Both are representations of the same entity.

`data-sema-type` classifies the modeled entity, not its view or representation. Every representation of one entity MUST
use the same stable qualified type. Different SVG `id` values, geometry, transforms, and presentation or style are
representation-local. A view kind does not choose an entity's type. A type used in a view MUST be defined by Core or a
profile active for that SVG: for example, an `electrical:appliance` may appear on a floor-plan SVG that declares
`electrical@0.1.0`, whether or not the Building profile is also active. An omitted entity fact in another representation
is not a conflict. When the same fact is repeated with different values, the cross-view conflict and authority rules
apply; a profile MAY explicitly define a property as representation-scoped.

### 4.4 View

A view is one SVG document.

Examples:

```text
site-plan
floor-plan
equipment-layout
schematic
detail
elevation
```

Each SVG document represents exactly one view. A multi-view project uses separate SVG files listed by its manifest;
separate files are particularly useful when views have different coordinate systems, scales or purposes.

### 4.5 Profile

A profile defines domain-specific semantic vocabulary and rules.

Examples in this package:

```text
building@0.1.0
electrical@0.1.0
```

One view may use multiple profiles.

## 5. Root metadata

A semantic SVG view MUST declare:

```xml
<svg
    xmlns="http://www.w3.org/2000/svg"
    data-sema-version="0.1.0"
    data-sema-project="example-project"
    data-sema-view="ground-floor"
    data-sema-view-kind="floor-plan"
    data-sema-coordinate-mode="physical"
    data-sema-unit="mm"
    data-sema-profiles="building@0.1.0 electrical@0.1.0"
>
```

Required core attributes:

```text
data-sema-version
data-sema-project
data-sema-view
data-sema-view-kind
data-sema-coordinate-mode
data-sema-profiles
```

`data-sema-profiles` is a whitespace-separated list of non-Core
`profile@version` declarations. The attribute remains required when the list is
empty; a Core-only view uses `data-sema-profiles=""`. Core is always active and
is not listed as a profile.

`data-sema-unit` is required for physical-coordinate views. SemaSVG 0.1.0
supports exactly:

```xml
data-sema-unit="mm"
```

Optional root attributes include:

```text
data-sema-scope
data-sema-revision
data-sema-north-deg
```

`data-sema-revision` is an opaque project revision identifier. It does not
replace SemaSVG or profile versions.

`data-sema-north-deg` records the clockwise angle from the upward SVG direction
to project north in the root user-coordinate system. Values SHOULD be
normalized to the range from 0 inclusive to 360 exclusive.

## 6. Coordinate modes

### 6.1 Physical

A physical view uses real-world scale.

Example:

```xml
data-sema-coordinate-mode="physical"
data-sema-unit="mm"
```

In SemaSVG 0.1.0, one unit in the root SVG user-coordinate system equals one
millimeter. Consumers determine semantic geometry after applying normal
inherited SVG transforms. The root `viewBox` maps that coordinate system to the
rendered viewport; it does not change the semantic millimeter scale.

Physical geometry is authoritative for distances within the accuracy of the source data.

### 6.2 Diagrammatic

A diagrammatic view represents topology, grouping or logic rather than physical distance.

Example:

```xml
data-sema-coordinate-mode="diagrammatic"
```

In a diagrammatic view:

- relative positions do not imply real-world distances;
- visual spacing is presentation;
- logical relationships are authoritative.

Diagrammatic views SHOULD omit `data-sema-unit` because their coordinates do
not express physical measurements.

Electrical schematics are a typical diagrammatic view.

## 7. SVG coordinate convention

Normal SVG coordinates are used:

- X increases to the right.
- Y increases downward.

Consumers MUST honor normal SVG transforms.

Producers SHOULD avoid unnecessary transforms on semantic geometry because raw world coordinates are easier to inspect and validate.

Non-uniform scaling and skewing of semantic geometry SHOULD be avoided.

## 8. Semantic roots

Every represented semantic entity MUST have a semantic root element with at least:

```text
id
data-sema-entity
data-sema-type
```

Example:

```xml
<rect
    id="repr-room-kitchen"
    data-sema-entity="room-kitchen"
    data-sema-type="building:space"
    ...
/>
```

`id` MUST be unique within the SVG document.

`data-sema-entity` MUST be stable across all views that represent the same entity.

### 8.1 Simple geometry

For simple entities, the semantic root can be the geometric element itself:

```xml
<rect ... />
<polygon ... />
<circle ... />
<polyline ... />
```

### 8.2 Composite representation

For visually complex entities, a `<g>` MAY be the semantic root:

```xml
<g
    id="repr-socket-kitchen-01"
    data-sema-entity="socket-kitchen-01"
    data-sema-type="electrical:socket"
>
    <circle data-sema-role="geometry" ... />
    <path data-sema-role="decoration" ... />
</g>
```

Recommended `data-sema-role` values:

```text
geometry
decoration
label
hit-area
guide
```

A consumer MUST NOT treat decoration as an independent semantic object unless it also has its own `data-sema-entity` and `data-sema-type`.

### 8.3 Physical geometry of a composite representation

In a physical view, a simple geometric semantic root describes its own physical geometry. For a composite `<g>` root,
only geometric elements explicitly marked `data-sema-role="geometry"` contribute to that representation's physical
shape. This role does not automatically propagate to unmarked descendants. Consumers MUST apply the inherited SVG
transforms to the selected geometry as described in sections 6 and 7.

Subtrees marked `decoration`, `label`, `hit-area`, or `guide` do not contribute to physical geometry. Geometry inside a
nested entity's semantic root belongs to that nested representation, not automatically to its enclosing entity.
Consumers MUST NOT use the entire rendered group's bounding box as physical dimensions when it includes such content.

Without explicit physical geometry, a composite representation's physical dimensions are unspecified, not zero. An
enlarged symbol used for readability MUST NOT be marked as physical geometry unless its dimensions represent physical
facts. A profile or documented project convention may separately identify a symbol's placement point without asserting
its physical size; Core 0.1.0 does not introduce a general anchor attribute.

These rules identify which authored geometry carries physical meaning. They do not require baseline 0.1 tooling to
calculate dimensions, areas, or collisions. Diagrammatic geometry remains presentation regardless of its role.

## 9. Entity ID rules

Entity IDs SHOULD be human-readable, stable, lower-kebab-case identifiers.

Recommended pattern:

```text
[a-z][a-z0-9]*(?:-[a-z0-9]+)*
```

Examples:

```text
site-main
building-main
level-ground
room-bedroom
wall-bedroom-east
panel-main
circuit-hob
rcbo-hob
terminal-rcbo-hob-l-out
```

An entity ID MUST NOT change merely because the entity moves, is restyled or appears in another view.

## 10. Representation IDs

Representation IDs are SVG-document-local.

Recommended form:

```text
repr-<entity>-<view-purpose>
```

Example:

```text
repr-panel-main-floor
repr-panel-main-layout
repr-panel-main-schematic
```

For a simple project where an entity appears only once, a producer MAY use the same value for `id` and `data-sema-entity`, but consumers MUST treat `data-sema-entity` as semantic identity when present.

## 11. Relationships

Relationships between semantic objects SHOULD reference entity IDs, not SVG representation IDs.

Example:

```xml
data-sema-space="room-kitchen"
data-sema-host="wall-kitchen-east"
```

Do not point semantic relationships at `repr-*` IDs unless a profile explicitly defines a representation-level relationship.

Lists of entity IDs are whitespace-separated:

```xml
data-sema-connects="room-bedroom space-corridor"
```

Commas SHOULD NOT be used for entity-ID lists.

An attribute registered as `entity-ref` MUST contain exactly one entity ID when present. Surrounding whitespace is
permitted; empty or whitespace-only values are invalid. Omit an optional relationship when its target is unknown. An
`entity-ref-list` attribute permits multiple whitespace-separated entity IDs.

## 12. Universal relationship attributes

The following generic relationships are defined by the core.

### 12.1 Parent entity

```xml
data-sema-parent="panel-main"
```

This expresses semantic containment or ownership.

It is intentionally separate from SVG DOM grouping.

The DOM may be reorganized for editing without changing semantic ownership.

### 12.2 Scope entity

A view may declare its primary subject:

```xml
data-sema-scope="panel-main"
```

### 12.3 Generic source and target

Profiles MAY use:

```text
data-sema-from
data-sema-to
```

for directed relationships.

Profiles SHOULD define the exact meaning.

### 12.4 Qualified type names

`data-sema-type` values MUST be qualified by a profile identifier:

```text
<profile>:<local-type>
```

Examples:

```xml
data-sema-type="building:space"
data-sema-type="building:wall"
data-sema-type="electrical:panel"
data-sema-type="electrical:circuit"
data-sema-type="core:label"
```

The `core` prefix is reserved for SemaSVG Core.

Official profile identifiers are short stable names such as:

```text
building
electrical
```

Third-party profiles SHOULD use a collision-resistant identifier, for example a reverse-domain-style name.

A type prefix other than `core` MUST correspond to a profile declared by the view.

### 12.5 SemaSVG attribute namespace

SemaSVG reserves:

```text
data-sema-*
```

Semantic attributes defined by SemaSVG Core or an active profile use this prefix.

Applications MUST preserve unknown `data-sema-*` attributes.

Project-specific experimental attributes SHOULD use:

```text
data-sema-x-*
```

Example:

```xml
data-sema-x-review="verify on site"
```

An experimental attribute MUST NOT silently acquire standardized meaning without a documented migration.

### 12.6 Profile property registry

Core and official profiles maintain a property registry in `vocab/`.

The registry prevents two official properties from accidentally assigning incompatible meanings to the same `data-sema-*` attribute.

Third-party profiles SHOULD prefix profile-specific extension properties when collision risk exists.

## 13. State

`data-sema-state` describes lifecycle or design state.

Recommended vocabulary:

```text
existing
planned
proposed
to-remove
removed
unknown
```

Examples:

```xml
data-sema-state="existing"
data-sema-state="planned"
```

`planned` means part of the current intended design.

`proposed` means an option or candidate not yet accepted as the current design.

State does not express measurement confidence.

## 14. Certainty

`data-sema-certainty` is an optional, local summary of confidence in the annotated representation or element's geometry
or semantic data. It is not an entity-wide fact. When absent locally, its value MUST NOT be inferred from a DOM ancestor
or another representation. Different representations of one entity may have different certainty annotations without
an entity-property conflict.

Recommended vocabulary:

```text
verified
measured
traced
documented
estimated
unknown
```

Examples:

```xml
data-sema-certainty="traced"
data-sema-certainty="unknown"
```

Missing certainty MUST NOT be interpreted as `verified`.

Missing certainty means that no confidence claim has been made. Core 0.1.0 does not require confidence percentages or
per-property confidence records. A summary annotation does not independently certify every property. When data has
mixed sources or confidence, authors SHOULD explain the distinction in `<desc>` or accompanying project documentation
instead of presenting an unsupported uniform confidence claim.

## 15. Source

`data-sema-source` optionally describes how the annotated representation or element's information was obtained. Like
certainty, it is local rather than an entity-wide fact. When absent locally, its value MUST NOT be inferred from a DOM
ancestor or another representation. Missing source means that no source has been stated.

Recommended vocabulary:

```text
survey
manual-measurement
original-plan
annotated-plan
photo
project-discussion
product-documentation
derived
assumption
```

Example:

```xml
data-sema-source="original-plan"
```

This attribute is a short source category, not a source-record identifier. Detailed source descriptions and links
SHOULD use `<desc>` or accompanying project documentation.

Optional positional accuracy can be recorded:

```xml
data-sema-accuracy-mm="20"
```

Do not invent an accuracy value unless it is known.

## 16. Geometry versus metadata

Geometry is the primary source of spatial truth in physical views.

Metadata may add information geometry cannot express, such as:

- ownership;
- connectivity;
- state;
- certainty;
- product model;
- circuit membership.

If geometric facts and redundant metadata disagree, a validator SHOULD report the conflict instead of silently correcting it.

## 17. Derived values

Derived values MAY be cached for human readability or tooling convenience.

Examples:

```xml
data-sema-area-m2="12.01"
data-sema-route-length-mm="8420"
```

Derived values MUST be treated as non-authoritative if they can be recomputed from geometry.

A validator SHOULD warn when a cached value differs materially from a computed value.

## 18. Labels and annotations

Visible labels are presentation, not semantic identity.

This:

```xml
<text>Kitchen</text>
```

is not enough to define a kitchen entity.

A label SHOULD reference its target entity:

```xml
<text
    id="label-room-kitchen"
    data-sema-type="core:label"
    data-sema-for="room-kitchen"
>
    Kitchen
</text>
```

Long human notes SHOULD use `<desc>` or dedicated annotation objects rather than very large `data-*` values.

### 18.1 Native titles and descriptions

SemaSVG uses the native SVG `<title>` for a short human-readable title and `<desc>` for a longer description or note.
Each is independently optional: a representation or view MAY have only a title, only a description, both, or neither.
No additional `data-sema-*` property is required. Their native SVG meaning is defined by the
[SVG specification](https://www.w3.org/TR/SVG2/struct.html#DescriptionAndTitleElements).

To describe a representation, authors SHOULD place these elements directly inside its semantic root, including when that
root is a simple shape such as `<rect>`. Direct children of the document's root `<svg>` describe the whole view.
Descriptions on other SVG elements retain their ordinary SVG scope.

These texts are representation-local. Different representations of one entity MAY have different titles and descriptions
without an entity-property conflict. Consumers MUST NOT infer a representation's own title or description from an
ancestor, a nested entity, or another view. This rule does not change native SVG accessibility behavior.

Titles and descriptions MUST NOT replace entity identity, type, relationships, or machine-readable properties. A
profile-defined entity name, such as Building's `data-sema-name`, remains a separate presentation-independent property;
authors need not duplicate it into a title. Visible labels continue to use `<text>`.

Editors SHOULD make an authored title and description available when a representation is selected, and MAY also show
them on hover or keyboard focus. Native tooltip behavior varies by viewer; consumers MUST NOT assume that `<desc>` is
displayed automatically. Interactive UI belongs in the editor, while saved SVG remains passive. Editors and formatters
MUST preserve these elements and their text unless intentionally editing them.

## 19. Styling

Style MUST NOT carry semantic meaning.

Consumers MUST NOT determine semantic type solely from:

- fill color;
- stroke color;
- line width;
- CSS class;
- opacity.

Semantics come from explicit attributes and geometry.

## 20. Editor-specific metadata

Editor-specific namespaces such as:

```text
inkscape:*
sodipodi:*
```

MAY be present.

Consumers SHOULD ignore them unless explicitly needed.

Editors and formatters MUST preserve unknown `data-*` attributes.

## 21. Passive-document requirement

Canonical SemaSVG project files MUST be passive documents.

They MUST NOT contain:

- `<script>`;
- inline JavaScript event handlers;
- executable containers such as `<iframe>`, `<object>` or `<embed>`;
- executable URI schemes such as `javascript:` in `href` or `xlink:href`;
- network-loaded executable content.

Ordinary relative links, fragment links and HTTPS links are permitted. A
consumer MUST still treat linked content according to its own security policy.

`<foreignObject>` SHOULD NOT be used as the only storage location for semantic data.

External resources SHOULD be avoided when practical.

## 22. Multiple views of one entity

Multiple views are a core feature, not an edge case.

Example:

```text
entity: panel-main

house-ground-floor.svg
    repr-panel-main-floor

panel-main-layout.svg
    repr-panel-main-layout

panel-main-schematic.svg
    repr-panel-main-schematic
```

All representations use:

```xml
data-sema-entity="panel-main"
```

No view is automatically more authoritative for every property.

A physical layout may be authoritative for enclosure positions, while a schematic is authoritative for logical terminal connections.

Profiles SHOULD define which properties are expected in which view kinds.

## 23. Cross-view conflicts

If two representations of the same entity contain the same entity fact or property with different values, tooling SHOULD
report the conflict, unless the applicable specification or profile defines that property as representation-scoped.

It MUST NOT silently choose one based on file order.

A project-specific document may declare which view is authoritative for a property class.

This Core rule does not require a particular validator to detect every cross-view conflict.

The packaged 0.1 validator warns about differing values for a limited set of stable entity properties documented in
the [validator's diagnostic contract](../tools/validator/README.md#property-conflict-warnings). Missing properties are
not conflicts. These warnings do not establish an authoritative value or make an otherwise valid project invalid.

## 24. Profile declaration

Profiles are declared on the root:

```xml
data-sema-profiles="building@0.1.0 electrical@0.1.0"
```

Each declaration uses the exact `<profile>@<semantic-version>` form. Core is
implicit and MUST NOT be included in this list or in a project manifest's
`profiles` map. A view that uses only Core types declares an empty value.

A consumer that does not understand a profile MAY still parse the core semantics and preserve unknown attributes.

The 0.1 validator provides baseline conformance for the packaged official
Core, Building, and Electrical vocabularies. It requires exact
`profile@version` declarations, supported official profile versions, and
registered official types. Registered entity types require
`data-sema-entity`; the explicit non-entity Core types do not. It validates
registered finite-number, integer, boolean, enum, and entity-reference
attributes. Unknown third-party profiles and types, and unknown
`data-sema-*` attributes, remain permitted and unvalidated. It does not yet
decide whether a property applies to a particular type or validate geometry or
domain rules.

## 25. Extensibility

Profile-defined attributes SHOULD use readable `data-sema-*` names.

Project-specific experimental attributes SHOULD use:

```text
data-sema-x-*
```

Example:

```xml
data-sema-x-renovation-note="verify masonry before drilling"
```

Unknown attributes MUST be preserved.

## 26. Core validation

A core validator SHOULD check at least:

- root format declaration;
- supported format version;
- unique SVG `id` values;
- required `data-sema-entity` and `data-sema-type` on semantic roots;
- valid entity-ID syntax;
- project consistency;
- valid referenced entity IDs where resolvable;
- coordinate-mode requirements;
- `data-sema-unit="mm"` for physical views;
- exact profile declaration syntax and supported official profile versions;
- prohibited executable content;
- malformed SVG/XML.

## 27. Conformance

A document conforms to SemaSVG Core 0.1.0 when it satisfies every applicable
Core MUST and MUST NOT requirement. It conforms to an official profile when it
also declares the exact supported profile version and satisfies that profile's
normative requirements.

A producer conforms when every SemaSVG document it emits is conformant. A
consumer that rewrites a document also acts as a producer and MUST preserve
stable entity identity and unknown semantic attributes as required by this
specification.

The packaged 0.1 validator provides three cumulative validation layers:

1. Core structural validation of SVG/root metadata, identity, registered
   references, coordinate mode, the physical millimeter unit and passive
   document rules.
2. Official registry validation of declared profile versions, registered types,
   entity requirements and registered scalar/reference values.
3. Manifest validation, when a manifest exists, of project membership, safe
   view paths and matching project/view/profile metadata.

Conformance does not imply geometric, engineering or regulatory correctness.
Type-specific property applicability, geometric calculations, route and
collision analysis, derived-value recomputation and domain engineering rules
are outside baseline 0.1 validator conformance.

## 28. Editing rules for humans and AI agents

An editor or agent modifying an SemaSVG view MUST:

1. Preserve unrelated geometry.
2. Preserve stable entity identities.
3. Preserve unknown semantic attributes.
4. Preserve state, certainty and source unless intentionally changing them.
5. Avoid flattening semantic objects into raster images.
6. Avoid merging independent semantic entities merely for visual simplification.
7. Avoid inventing precise geometry to make the drawing look cleaner.
8. Report contradictions or uncertainty instead of silently rewriting uncertain source data.
9. Keep proposed work distinguishable from existing work.
10. Prefer minimal, reviewable diffs.

## 29. AI reasoning rule

An AI agent SHOULD treat a semantic SVG as structured data first and an image second.

Recommended order:

1. Parse root metadata and profiles.
2. Parse semantic entities and relationships.
3. Validate references and geometry.
4. Identify uncertain data.
5. Only then reason about routes, placement or modifications.

Visual appearance MUST NOT override explicit semantic identity.

## 30. Git recommendations

SemaSVG is intended to work well with version control.

Recommended practices:

- use stable IDs;
- avoid tools that rewrite the entire XML tree unnecessarily;
- keep coordinates readable;
- use integer physical coordinates where reasonable;
- separate large cosmetic restyling from semantic changes;
- inspect diffs after saving with a new editor version.

## 31. Final design rule

A semantic addition belongs in the core only if it is useful across multiple domains.

Building-specific and electrical-specific concepts belong in profiles.

The core should remain deliberately small.

## 32. Project manifests

A standalone SemaSVG file does not require a separate manifest.

Multi-view projects SHOULD provide `semasvg.project.yaml` that lists their separate SVG view files.

The manifest is an index, not a second source of geometric truth.

Example:

```yaml
semasvg: 0.1.0
project: house-renovation-reference

profiles:
  building: 0.1.0
  electrical: 0.1.0

views:
  - id: ground-floor
    file: ground-floor.sema.svg
    kind: floor-plan
  - id: panel-main-schematic
    file: panel-main-schematic.sema.svg
    kind: schematic
```

Geometry and entity semantics remain in SVG files.

The manifest makes project discovery, validation and tooling easier.

Every manifest view `id` MUST be unique within the project. Every declared view file MUST have a distinct resolved path;
alternative relative path spellings or symlinks to an already declared file MUST NOT introduce another view.

The manifest `profiles` map is required. It may be empty for a Core-only project. Every profile declared by an SVG view
MUST be a same-version subset of that map; the map MAY contain additional profiles used by other views or reserved for
project work.

See `docs/project-manifest.md`.
