# House project agent guide

Use this root bootstrap before changing the copied project:

1. Read `README.md` first.
2. Before changing documentation, read `docs/README.md`; before changing the model, read `model/README.md`.
3. Before changing model semantics, read the normative SemaSVG 0.1.0 documents at their versioned upstream locations:
   [Core](https://github.com/ezoterik/semasvg/blob/v0.1.0/spec/core.md),
   [Building](https://github.com/ezoterik/semasvg/blob/v0.1.0/spec/profiles/building.md), and
   [Electrical](https://github.com/ezoterik/semasvg/blob/v0.1.0/spec/profiles/electrical.md). Also read the practical,
   non-normative [AI integration guide](https://github.com/ezoterik/semasvg/blob/v0.1.0/docs/ai-agent-integration.md).

`model/semasvg.project.yaml` determines which profiles are active. Read every declared profile; this starter currently
declares Building and Electrical 0.1.0. Validator success does not replace normative semantics. When manifest format or
profile versions change, update these versioned specification links deliberately to match. If the referenced
specifications are unavailable, do not invent or change model semantics.

Run `make validate` before and after model edits and `make qa` before completion. Preserve stable `data-sema-entity`
values and never invent physical facts or geometry. Record source, privacy, certainty, and unresolved assumptions
through the owners in `sources/README.md`.

For equipment or inventory changes, read `inventory/README.md` and keep lifecycle and commercial facts in inventory.

When a change adds a durable decision, source record, or model convention, update its canonical document in the same
change. Keep generated output out of `exports/` source control. Credentials, tokens, private keys, and other secrets are
never repository knowledge and must never be committed; use approved secret storage outside the repository.
