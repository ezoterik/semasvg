# SemaSVG validator

Prototype validator for SemaSVG 0.1.0.

Related material: [normative specifications](../../spec/README.md),
[machine-readable vocabulary](../../vocab/README.md), [manifest guide](../../docs/project-manifest.md), and
[SVG authoring guide](../../docs/svg-authoring.md).

Install from the monorepo with Python 3.11 or later. On Ubuntu, create and activate a virtual environment first:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./tools/validator
```

Validate the public reference project:

```bash
semasvg validate examples/reference/renovation-demo
```

`validate` accepts a standalone SVG file, a project directory, or a direct `semasvg.project.yaml` path.

## SVG formatting

Format authoring source without changing SemaSVG semantics:

```bash
semasvg format examples/reference/renovation-demo
semasvg format examples/reference/renovation-demo --check
semasvg format examples/reference/renovation-demo/semasvg.project.yaml --check
semasvg format examples/reference/renovation-demo/ground-floor.sema.svg --check
```

`format` accepts a direct regular non-symlink SVG, a direct `semasvg.project.yaml`, or a directory. With a manifest it
selects only the declared views; without one it recursively selects non-hidden `*.svg` files. It rejects missing,
non-SVG, empty or invalid-manifest, unsafe or symlinked, non-UTF-8, and malformed-XML targets.

Without `--check`, it parses every selected file before writing and atomically replaces only stale files, preserving
each file mode. A failure during a later replacement has no batch rollback guarantee. With `--check`, it is read-only:
stale files print `<count> unformatted file(s)` and exit nonzero; a current selection prints
`OK: SVG formatting is current`. Write mode prints `OK: formatted <count> file(s)`. Errors print per-file
`ERROR format ...` messages, an error count, and exit nonzero.

The formatter is XML-aware but source-preserving: it retains lexical attribute order, names, values, quotes, entity
spelling, namespace prefixes, XML declarations, DOCTYPEs, processing instructions, CDATA, self-closing form, and raw or
mixed content (including inherited `xml:space="preserve"`). It applies structural indentation and wrapping only;
expanded-tag continuations align under the first attribute column after the element name. It does not format CSS tokens,
paths, or text; sort or repair attributes; extract styles; change semantics; or perform semantic validation. For
multiline plain CSS in `<style>`, it normalizes only structural opening, closing, and leading indentation while
preserving CSS tokens, comments, relative indentation, rule/declaration order, CDATA, and opaque or single-line content.
See the [SVG authoring guide](../../docs/svg-authoring.md) for formatting examples and presentation guidance. Generic
IDE whole-file XML reformatting can alter raw content and is not equivalent to `semasvg format`.

Inspect the experimental, non-normative project graph as stable, versioned JSON for tools and AI consumers. Top-level
`schema_version` lets consumers detect future output-format changes:

```bash
semasvg inspect-graph examples/reference/renovation-demo --entity breaker-general-sockets --depth 3 \
  --attribute data-sema-circuit --attribute data-sema-space
```

Without `--entity`, `inspect-graph` emits the complete graph. With `--entity`, it emits the bidirectional incoming and
outgoing neighborhood to `--depth` (default `1`; non-negative only). It accepts the same standalone SVG, project
directory, and direct manifest paths as `validate`, refuses output when ordinary validation has errors, and uses only
manifest-declared views when a valid manifest is present.

Repeat `--attribute` to restrict graph edges and entity-query traversal to specific registered active-vocabulary
entity-reference attributes. The command rejects unknown or inactive attributes instead of silently returning an empty
graph. This is useful for focused consumer queries: the example follows circuit membership and load-to-space references
without expanding through unrelated panel or system membership.

Graph entities preserve each representation's relative file, SVG `id`, view, and `data-sema-*` attributes, with their
validator-confirmed consistent type also exposed as a compact top-level field. Edges are only registered
active-vocabulary `entity-ref` or `entity-ref-list` attributes authored on an entity representation; unknown extension
attributes, text, styles, and geometry are not interpreted. The graph does not infer topology, protection groups,
service scope, or any other relationship.

Materialize direct-text derived labels before publishing an SVG project:

```bash
semasvg materialize-labels examples/reference/renovation-demo
```

Check label freshness in CI without changing files:

```bash
semasvg materialize-labels examples/reference/renovation-demo --check
```

Derived labels are literal SVG `<text>` elements typed `core:label`, linked to one target entity with `data-sema-for`,
and given an experimental `data-sema-x-label-template`. Templates interpolate target attributes; for example,
`{data-sema-breaker-curve}{data-sema-rated-current-a}` produces `C16`. Only direct text labels are supported; nested
markup and self-closing labels are rejected.

Without `--check`, the command updates only stale direct label text after every SVG in the supplied path has been
scanned successfully. It preserves all other source bytes and writes nothing if a template or source error is found.
With `--check`, it is read-only and exits nonzero for stale labels, invalid templates, missing target entities or
attributes, unsupported nested or self-closing derived labels, unreadable XML, or a nonexistent path. SVG files without
templates are unchanged. This command is separate from `semasvg validate`; ordinary validation acceptance is unchanged.

`materialize-labels` accepts a standalone SVG, a direct `semasvg.project.yaml`, or a directory. For a valid manifest it
selects only declared views, so unlisted SVG files are not read or changed. Without a manifest it retains recursive
non-hidden SVG selection. Manifest errors retain the validator error code and prevent all writes; an empty valid
manifest reports `no SVG files selected`. Direct targets, manifest-declared views, and manifestless-discovered SVG
symlinks are rejected before any write; materialization never follows a selected SVG symlink.

Validate one vocabulary YAML file or a directory of vocabulary files:

```bash
semasvg validate-vocabulary vocab
```

Current checks include:

- SVG/XML, root metadata, supported versions, physical-view units, and profile declarations.
- Registered entity, type, attribute, value, and reference checks.
- Project-wide identity, type, and relationship consistency.
- Manifest schema, authoritative membership, path, and root metadata checks.
- Vocabulary schema, registry, and collision checks.
- Passive-document security, including executable content and URI restrictions.

For a schema-valid project manifest, only its declared views are validated. Declared views must be relative, remain
inside the project directory after symlink resolution, and name existing regular SVG files. Without a manifest,
directory validation recursively collects SVG files and requires one project ID. The validator loads the official
vocabularies packaged with the installed distribution, not vocabulary files adjacent to the target SVG project.

Single `entity-ref` attributes must contain exactly one entity ID; empty, whitespace-only, or multiple-target values
produce `E214`. Surrounding whitespace is permitted. Omit an optional reference when its target is unknown. Manifest
view IDs must be unique (`E421`), and the same resolved SVG file cannot be listed more than once (`E422`), including
through alternative relative path spellings or symlinks. These errors also prevent `inspect-graph` output;
duplicate-manifest errors prevent formatting and label materialization from writing selected files.

Unknown third-party profiles and types, and unknown `data-sema-*` attributes, are accepted and are not
profile-validated. Registered `token` and `string` attribute values remain open. This is intentionally baseline
conformance only: it does not validate type-specific property applicability, geometry, or engineering/domain rules.

## Property-conflict warnings

`validate` emits `WARNING W220` when representations of the same entity in the same selected project disagree on:

- `data-sema-rated-current-a`;
- `data-sema-voltage-v`;
- `data-sema-poles`;
- `data-sema-manufacturer`;
- `data-sema-model`.

Only properties registered by an active official vocabulary participate. Numeric values compare by exact decimal value,
so `16`, `16.0`, and `1.6e1` agree; token and string values compare exactly, including case and whitespace. Invalid
numeric values retain their scalar errors and do not generate secondary conflict warnings. Missing properties,
certainty/source annotations, geometry, derived values, and properties outside this list are not compared.

Each differing occurrence is reported against the first comparable occurrence, with the entity, attribute, original
values, and both representation locations. That first occurrence is only a diagnostic reference, not an authoritative
value. The check also covers repeated representations in one SVG and never compares separately validated models.

Warnings alone leave the `validate` exit status at zero and never rewrite source data. `inspect-graph` remains available
and preserves every representation's authored values; it does not emit these warnings or choose a merged property value.
Run `validate` to see the diagnostics before consuming the graph.
