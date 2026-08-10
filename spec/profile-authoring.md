# Profile authoring

SemaSVG Core is intentionally small. New domain concepts should normally be added through profiles.

## When to create a profile

Create a profile when a domain has:

- recurring entity types;
- recurring properties;
- domain-specific relationships;
- validation rules;
- multiple real examples.

Do not add a Core concept merely because one profile needs it.

## Profile identifier

Official SemaSVG profiles use short stable identifiers:

```text
building
electrical
```

Third-party profiles SHOULD use collision-resistant identifiers.

Profile versions use Semantic Versioning independently of Core.

## Qualified types

A profile defines types as:

```text
<profile-id>:<local-type>
```

Example:

```text
electrical:panel
```

A view using this type declares:

```xml
data-sema-profiles="electrical@0.1.0"
```

## Overlapping classifications

When compatible profiles can describe the same modeled subject, choose one primary, more-specific type according to the
semantics consumers need. Do not put multiple types on one entity, change its type by view, or duplicate the subject
only to obtain another category. Combine compatible registered properties and relationships from the active profiles
instead.

Profiles that overlap SHOULD document their modeling fallback or precedence guidance, including when a broader profile
type remains appropriate. This is profile guidance, not a universal Core precedence mechanism. If two subjects are
genuinely distinct, such as a persistent installation and a replaceable device, a profile relation may link their
separate entities.

## Attributes

Use existing Core attributes when their semantics match.

Do not redefine them.

Official profile attributes use `data-sema-*`; the registry in `vocab/`
defines the attributes available to baseline validator conformance checks.
Every official `data-sema-*` attribute defined or used by a normative
specification MUST be registered by Core or at least one official profile.
When official profiles share an attribute name, their registry definitions
MUST be identical.

Experimental project-only properties use:

```text
data-sema-x-*
```

Third-party profile authors should choose collision-resistant property names.

The 0.1 validator loads its packaged official Core, Building, and Electrical
registries. It strictly validates known official versions, types, and
registered attribute values and references, but keeps unregistered
`data-sema-*` attributes and unknown third-party profiles/types open. It does
not yet enforce type-specific property applicability or domain rules.

## Required profile artifacts

A mature profile should contain:

1. normative Markdown specification;
2. machine-readable vocabulary YAML;
3. valid SVG examples;
4. invalid fixtures for important rules;
5. validator rules where practical.

## Core promotion test

A concept should move from a profile into Core only when at least two unrelated profiles need the same concept with materially identical semantics.

## Future PCB profile

PCB/electronics is a deliberately useful future test.

A PCB profile should be created from real source material rather than invented vocabulary.

Likely stress tests include:

- a component represented in schematic and board views;
- ports/pads;
- logical nets vs physical traces;
- board layers;
- physical and diagrammatic coordinate modes.

If PCB requires major Core changes, those changes should be justified by the cross-domain use case rather than by electronics terminology.
