# Contributing

SemaSVG is experimental. Design feedback and counterexamples are more valuable than adding vocabulary casually.

## Before proposing a core change

Ask whether the concept is truly domain-neutral.

A concept belongs in Core only when multiple unrelated domains require essentially the same semantics.

Examples that belong in profiles rather than Core:

```text
wall
room
circuit breaker
socket
PCB pad
water valve
```

## Profile changes

A profile change should include:

1. a concrete use case;
2. semantic definition;
3. SVG example;
4. machine-readable vocabulary change;
5. validator/test fixture where applicable.

## Breaking changes

Before 1.0, breaking changes are allowed but must:

- be intentional;
- be described in `CHANGELOG.md`;
- update examples;
- update fixtures;
- update vocabulary files;
- update validator behavior when relevant.

## Release checklist

- Choose and update the release version.
- Align the root README release status, CHANGELOG version and date, and CITATION version and date.
- Update validator/package and normative machine-readable version owners when applicable.
- Verify the public example inventory, manifests, and documentation.
- Run `make qa`.
- As a publication step, create the matching `vX.Y.Z` tag.

## RFCs

Substantial Core changes should start as an RFC under `rfcs/`.

Start with the [RFC index](rfcs/README.md), then use [RFC 0000](rfcs/0000-template.md) as the template.

After acceptance, incorporate applicable rules into `spec/`, schemas, vocabularies, tests, and documentation.

## Style

- normative specifications are written in English;
- use MUST/SHOULD/MAY carefully;
- examples should prefer readable XML over compressed SVG;
- do not optimize SVG examples with tools that destroy semantic structure;
- prefer lower-kebab-case IDs.

For source layout, comments, reusable presentation, editor-specific inspection settings, and the experimental formatter,
follow the [SVG authoring and formatting guide](docs/svg-authoring.md). Use the formatter only as a source-review aid;
it is not semantic validation.

## Tests

Use the Make facade first:

```bash
make setup
make qa
```

If Make is unavailable, run the raw commands below as an explicit fallback:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./tools/validator
python -m unittest discover -s tools/validator/tests
semasvg validate examples/reference/renovation-demo
semasvg validate-vocabulary vocab
```
