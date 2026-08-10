# Agent instructions

This repository is designed to be edited by humans and coding/AI agents.

## Project communication and delivery

- Use the user's language for user-facing agent communication.
- Write all repository artifacts in English, including specifications, documentation, authored code comments, commit
  messages, PR titles and descriptions, issue text, and release text.

## Changelog scope

`CHANGELOG.md` is release-facing. Record externally visible changes to versioned semantics/specifications,
schemas/vocabularies, manifests, validator acceptance/public errors, packaged CLI, compatibility, or security. Make
breaking changes explicit.

Do not record internal refactors, tests, formatting-only work, purely editorial documentation rearrangement, file
inventories/counts, or unpublished prototype history. An empty `Unreleased` section is valid until a qualifying change
exists. Keep detailed truth in canonical owners rather than duplicating it in `CHANGELOG.md`.

## Canonical resources

- `spec/` owns normative SemaSVG semantics. Before 1.0, its Markdown specifications win if prose and a machine-readable
  resource disagree.
- `schemas/` and `vocab/` are the canonical repository sources for machine-readable resources. Matching resources under
  `tools/validator/src/semasvg_validator/` are package mirrors: update them together and keep them byte-identical.
- Use `docs/README.md` to route documentation changes to their primary owner.

## Validator scope and public contracts

- Official Core, Building, and Electrical validation is registry-driven. Unknown third-party profiles and types, and
  unknown `data-sema-*` attributes, remain accepted unless a versioned specification changes that policy.
- Do not add type-specific property, geometry, or engineering validation without an applicable specification and a
  roadmap update.
- Changes to semantics, vocabulary or schemas, validator acceptance, manifests, public error codes, or the packaged CLI
  require tests and documentation. Breaking changes also require an explicit versioning decision.

## Passive-document security

- Reject scripts, inline event handlers, executable containers, and executable URI schemes. Preserve ordinary relative,
  fragment, and HTTPS links unless a specification changes that policy.

## Public examples

- Publish only synthetic or explicitly publishable examples. Never add private plans, addresses, customer data, or other
  identifying metadata, and never invent physical facts.

Before changing SemaSVG semantics:

1. Read `spec/core.md`.
2. Read every profile affected by the change.
3. Read `spec/profile-authoring.md` for profile changes.
4. Run the validator and tests after modifications.

When creating or changing an electrical panel, floor-plan circuit, or physical route representation, complete the
end-to-end electrical-system coherence pass in `docs/ai-agent-integration.md` and report unresolved paths or assumptions
without presenting the result as engineering or installation approval.

## Hard rules

An agent MUST NOT:

- infer unknown physical geometry and silently encode it as fact;
- move unrelated geometry to make a route or diagram easier to draw;
- change a stable `data-sema-entity` identifier merely because a representation changes;
- confuse a representation `id` with project-wide entity identity;
- treat diagrammatic coordinates as physical measurements;
- treat physical coordinates as schematic topology;
- remove unknown `data-sema-*` or `data-sema-x-*` attributes without an explicit reason;
- remove provenance or certainty metadata to make a file appear cleaner;
- use style, color, CSS class or visible text as the only source of semantic type;
- make a breaking core/profile change without updating fixtures and documentation.

## Unknown means unknown

If the source does not establish a fact:

```xml
data-sema-certainty="unknown"
```

or omit the unsupported property.

Do not invent a plausible value.

## Editing SVG

Preserve:

- semantic IDs;
- project-wide entity IDs;
- unrelated geometry;
- profile declarations;
- root coordinate mode;
- unit semantics;
- relationships.

Prefer small, reviewable diffs.

For source layout, comments, and presentation, follow `docs/svg-authoring.md`. Use `semasvg format PATH --check` when
checking SVG formatting, while preserving semantic IDs, unknown attributes, and raw or mixed text content. Formatting is
not semantic validation.

## Validation

Run:

```bash
python3 -m unittest discover -s tools/validator/tests
```

and:

```bash
python3 tools/validator/src/semasvg_validator/cli.py validate examples/reference/renovation-demo
python3 tools/validator/src/semasvg_validator/cli.py validate-vocabulary vocab
```

before considering a semantic change complete.
