# Additive house model agent guide

Use this bootstrap path before changing the copied model:

1. Read the host repository instructions first, including its root `AGENTS.md` and any instructions that apply to the
   chosen subtree.
2. Read this `README.md`, then `model/README.md`.
3. Read the normative SemaSVG 0.1.0 documents at their versioned upstream locations:
   [Core](https://github.com/ezoterik/semasvg/blob/v0.1.0/spec/core.md),
   [Building](https://github.com/ezoterik/semasvg/blob/v0.1.0/spec/profiles/building.md), and
   [Electrical](https://github.com/ezoterik/semasvg/blob/v0.1.0/spec/profiles/electrical.md). Also read the practical,
   non-normative [AI integration guide](https://github.com/ezoterik/semasvg/blob/v0.1.0/docs/ai-agent-integration.md).

The copied `model/semasvg.project.yaml` determines which profiles are active. Read every profile declared there; the
starter currently declares Building and Electrical 0.1.0. Validator success does not replace reading the normative
semantics. When manifest format or profile versions change, update these versioned specification links deliberately to
match. If the referenced versioned specifications are unavailable, do not invent or change model semantics.

Preserve stable `data-sema-entity` values, never invent physical facts or geometry, and use the host toolchain to
validate the module before and after edits through the host-defined validation entry points. The normative specification
owns semantics. Keep inventory, documentation, source evidence, and automation configuration with their host-defined
owners. Credentials, tokens, private keys, and other secrets are never repository knowledge and must never be committed.
