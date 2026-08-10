# Project manifest

`semasvg.project.yaml` indexes the separate SVG files of a multi-view project. It is not a second source of geometry or
entity semantics.

```yaml
semasvg: 0.1.0
project: example-project
profiles: {}
views:
  - id: overview
    file: overview.sema.svg
    kind: system-overview
```

The `profiles` map is required; `{}` is the Core-only form. An SVG view declares a same-version subset of the manifest
map, while extra manifest entries remain permitted. Core owns this semantic rule, the
[project schema](../schemas/project.schema.json) owns the machine-readable shape, the
[validator README](../tools/validator/README.md) owns diagnostics and CLI behavior, and the
[renovation demo](../examples/reference/renovation-demo/README.md) owns a worked example.

Each view ID and resolved SVG file path must occur only once. Listing `overview.sema.svg` and `./overview.sema.svg`, or
a symlink to that same file, does not create separate views. The validator checks these uniqueness rules in addition to
the schema's structural checks.
