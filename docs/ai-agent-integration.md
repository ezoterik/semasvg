# AI agent integration guide

This practical, non-normative guide is for developers and AI systems that
consume or edit user SemaSVG projects. It complements the repository-local
[`AGENTS.md`](../AGENTS.md) and the normative [core specification](../spec/core.md);
it does not replace either.

For a real house, keep the model and private facts outside SemaSVG upstream. The model can live in a dedicated
user-owned repository or as an additive module in an established repository. The
[house repository guide](house-repositories.md) explains both layouts, their ownership boundaries, provenance records,
and validator installation.

## Prepare the project context

1. Find `semasvg.project.yaml` and use its declared views when it is present.
   See the [project manifest guide](project-manifest.md).
2. Run the [validator](../tools/validator/README.md) before making changes.
3. Read each SVG root's metadata and its active profile declarations. Consult
   the relevant [Building](../spec/profiles/building.md) and
   [Electrical](../spec/profiles/electrical.md) profile specifications.
4. Build one project-wide index of `data-sema-entity` values across the active
   views, then resolve registered relationships through that index.

For focused read-only traversal, use `semasvg inspect-graph` and restrict the
query to the entity and registered relationship attributes relevant to the
task. The [validator reference](../tools/validator/README.md) owns the complete
command, output, filtering, and error contract.

Treat graph edges as source-authored relationships, not inferred truth. For
example, an AI may derive possible room impact by traversing breaker-to-circuit
membership, circuit-to-load, and load-to-space relationships, but it should not
persist a redundant breaker-to-room fact. A topology-based protection group
also remains consumer inference rather than an explicit graph edge.

An SVG `id` identifies a representation in that document. A
`data-sema-entity` identifies the underlying entity across project views; do
not substitute one for the other or create a new entity merely for another
representation.

Unknown `data-sema-*` and `data-sema-x-*` attributes may carry information
from extensions. Preserve them unless the requested change explicitly concerns
them.

## Interpret and edit safely

Treat the declared coordinate mode as part of the context. In physical views,
geometry and declared units can convey measurements. In diagrammatic views,
layout is presentation and relationships or topology matter more than line
lengths. Do not infer unsupported physical facts from either mode.

Use a bounded edit loop:

```text
discover manifest and views -> validate -> inspect metadata and profiles
-> index entities and relationships -> edit only the requested representations
-> validate again -> report assumptions and unresolved conflicts
```

Use validator error codes to guide the next inspection or correction. The
error-code catalog remains experimental until the roadmap marks it stable.
Do not silently resolve uncertain identity, topology, profile, or measurement
conflicts: state the assumption or leave the conflict unresolved for the
project owner.

### Trace electrical systems end to end

After creating or changing a panel mounting, schematic, or floor-plan
electrical representation, perform an end-to-end coherence pass. Trace every
declared source, block, terminal, protective device, conductor or cable, route
segment, outgoing circuit, and load through its semantic endpoints, circuit
membership, space or host relationships, and panel ownership. Do not treat
visual adjacency, a line crossing, a label, or similar appearance as an
electrical connection.

On a house plan, continue each circuit from its declared panel or protective
device origin through any declared terminals, cables, and route segments to
its loads. Logical circuit topology and physical route geometry remain
separate: a circuit may be declared without drawing its complete cable route,
but every route that is declared must be spatially continuous and
semantically associated with the intended circuit or cable.

The pass must check that:

- every referenced endpoint resolves to a declared entity;
- every applicable panel block and device has an explicit semantic role and
  ownership;
- circuit-to-load references resolve, and loads identify their declared space
  and physical host where those relationships are applicable;
- incoming paths, protected branch paths, and outgoing paths can be traced
  without relying on visual-only assumptions;
- every declared cable and route segment has coherent endpoints and circuit or
  cable associations;
- no declared route is disconnected, ambiguous, or unintentionally bypasses a
  protective device;
- declared switch and control relationships resolve independently of power
  route appearance;
- shared pathways do not merge the identities of their circuits or cables;
- schematic topology, mounting-view identities, and floor-plan entities agree
  for facts represented in more than one view;
- physical routes are continuous and cross obstacles only through explicit
  transitions;
- unknown, estimated, conflicting, or unsupported facts remain marked and are
  reported as unresolved.

Report the result as structural, spatial, and topological coherence under the
stated facts and assumptions. This pass does not establish electrical-code
compliance, engineering suitability, conductor sizing, voltage drop,
protection selectivity, manufacturer approval, or installation safety. Those
conclusions require applicable rules, verified project facts, equipment
documentation, and qualified engineering review.

## Compact example

For a request to update a breaker symbol, first validate the project and read
the view's root metadata and active profiles. Locate the symbol by its
`data-sema-entity`, inspect registered references that point to it, and modify
only the requested representation. Preserve its entity identity and extension
attributes, validate the declared project views again, then report any missing
relationship target or uncertain physical detail rather than guessing it.
