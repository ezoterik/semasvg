# RFC 0001: Core, profiles, entities and views

Status: Accepted for 0.1.0

This RFC records the decision rationale. The normative rules are incorporated
into the [Core specification](../spec/core.md) and applicable profile
specifications.

## Decision

SemaSVG separates:

```text
Core
Profiles
Entities
Representations
Views
```

A semantic entity has a project-wide identity.

An SVG element is a representation of that entity in one view.

Domain-specific concepts belong in profiles.

## Motivation

The design originated in a building-floor-plan use case.

A detailed electrical-panel use case exposed a fundamental limitation: the same real panel needed to exist simultaneously as:

- a small physical object on a floor plan;
- a detailed equipment layout;
- an electrical schematic.

Treating each drawing object as a different semantic object would destroy cross-view identity.

The same pattern is expected in unrelated domains such as PCB/electronics:

- schematic symbol;
- PCB footprint;
- assembly representation.

Therefore `entity != representation` is a Core principle.

## Consequence

Core remains domain-neutral.

Building and Electrical terminology lives in profiles.

A future PCB profile should test this architecture rather than adding electronics concepts to Core.
