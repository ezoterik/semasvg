# House repositories

SemaSVG upstream owns specifications, official profiles, validator code, and public synthetic reference material. Real
property data, private plans, addresses, photos, and provenance stay outside this upstream repository. Plans, addresses,
and photos may be governed by an access-controlled storage policy. Credentials, tokens, private keys, and other secrets
are never repository knowledge and must never be committed. Consumer knowledge can live in either of two topologies:

- A dedicated whole-home repository, started from [`templates/house-project/`](../templates/house-project/), when the
  property model and its supporting knowledge need their own repository.
- An additive SemaSVG module in an established repository, started from
  [`templates/house-model/`](../templates/house-model/), for example under `house/`. This module does not take over the
  host root, its Makefile, `.gitignore`, dependency files, CI, or documentation structure.

Neither topology is universally required. A single house normally has one SemaSVG model project, whose manifest can
cover views from several profiles. An established repository may contain several independent models; each needs its own
directory and `semasvg.project.yaml`, and each must be checked separately.

## Current and target models

A model can describe the selected target state: move a cabinet in that model and use it to guide the intended physical
change. Use `planned` where a modeled change has not yet been implemented. A separate history or scenario mechanism is
not required for this workflow.

When both current and target states are useful, keep them as independent model directories:

```text
current/
  semasvg.project.yaml
  views/
target/
  semasvg.project.yaml
  views/
```

Each manifest selects only that model's views. Validate the two model roots separately:

```bash
semasvg validate current
semasvg validate target
```

Do not validate their common parent as one manifestless project: recursive discovery may combine files from both models.
The same known cabinet may retain its entity ID in both models, but this does not request automatic merging,
synchronization, or comparison. A changed target position is not a conflict with the separately validated current model.
This is a directory-based working convention, not a new Core state or cross-project identity mechanism.

## Dedicated whole-home repository

Use the complete starter for a standalone house knowledge repository with one model and its supporting private
knowledge. For copying, initialization, tool pinning, local overrides, and checks, follow the
[copied-project initialization instructions](../templates/house-project/README.md#initialize-a-copied-repository).

## Additive module in an established repository

Use the minimal module when SemaSVG belongs inside an established repository. The host retains its root, toolchain,
dependencies, CI, documentation structure, and ownership boundaries. Bootstrap the copied module through the host's
instruction routing and QA workflow, then follow the [additive-module instructions](../templates/house-model/README.md)
for the concise integration checklist.

## Ownership and identity convention

SemaSVG is the human-reviewable 2D semantic model and diagram layer in a broader house knowledge repository. It owns
represented geometry, topology, and model facts. An inventory owns serial numbers, warranty, cost, maintenance, and
other lifecycle facts. Authored documents own property, project, and maintenance narratives. Sources own evidence and
pointers. Home Assistant, openHAB-like systems, and other automation subsystems own runtime configuration and state
separately from the SemaSVG model. Ignored local folders are never canonical knowledge.

Use one-fact/one-owner: serial numbers, warranty, manuals, service intervals, work orders, and history are not generally
SemaSVG-owned. A derived copy must identify its canonical owner and be refreshed or removed when that owner changes.

This consumer convention is non-normative and is not validator-enforced. A stable house object ID may be reused as
`data-sema-entity` when the same object is represented. Home Assistant entity or device IDs, and IDs from other runtime
systems, are mutable aliases rather than physical identity. Markdown entity references and source-record references are
also conventions, not Core semantics or validator rules. Use searchable Markdown tokens such as `entity:room-kitchen`
and `source:original-plan-2024` when linking a claim to a stable entity and a source record. In particular,
`data-sema-source` is not a source-record pointer.

A source record can include: source ID; kind and location; capture or issue date; access class; checksum when useful;
affected stable IDs; certainty; and limitations. Mark unsupported facts as unknown or omit them instead of inferring a
plausible value.

When a persistent installation or functional slot and a replaceable physical device need separate identity or lifecycle,
they may be separate linked entities. This is optional: do not invent either entity merely to model a replacement
possibility. Stable IDs bridge the model, inventory, documents, and source records when the same subject is known across
those boundaries.

## Ecosystem position

SemaSVG composes with rather than replaces adjacent systems.

| System                                                                                            | Primary role                                                                                                         |
|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| SemaSVG                                                                                           | Ordinary human-reviewable 2D SVG views, stable cross-view identity, profiles, provenance, certainty, and validation. |
| [IFC and BIM](https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/) | Authoritative building-model exchange.                                                                               |
| [Brick](https://brickschema.org/) and [Haystack](https://project-haystack.org/)                   | Building-system ontology and metadata.                                                                               |
| [Home Assistant](https://www.home-assistant.io/) and [openHAB](https://www.openhab.org/)          | Live automation configuration and state.                                                                             |
| Inventory, documents, and sources                                                                 | Lifecycle facts, narratives, and evidence.                                                                           |

Annotating SVG is not itself novel. SemaSVG's value is a small, Git-friendly convention combining ordinary SVG, stable
cross-view identity, profiles, provenance and certainty, and validation. It is not CAD or BIM, an automation runtime, an
inventory database, a universal knowledge graph, or an authoring application.
