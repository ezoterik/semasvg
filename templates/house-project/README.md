# House SemaSVG project

This is a complete, copyable synthetic starter for a dedicated whole-home repository. Keep real plans, source material,
and private provenance in your own access-controlled repository, not in SemaSVG upstream. For an additive module in an
existing repository, use the
[upstream additive template](https://github.com/ezoterik/semasvg/tree/v0.1.0/templates/house-model/) instead.

`model/` is the canonical SemaSVG source. Its `semasvg.project.yaml` lists the only views consumed by validation and
label materialization. Use one manifest for all Building, Electrical, and future profile views that belong to this one
SemaSVG model project, so a stable `data-sema-entity` can identify the same thing across representations; SVG `id`
values are local to one view. The manifest does not own the repository's other house knowledge.

Prerequisites are Python 3.11 or newer, Git, GNU Make, and network access for the normal pinned install; the documented
local source override remains available for upstream development.

## Initialize a copied repository

1. Copy the complete template, including dotfiles, into a new access-controlled repository. Its root `AGENTS.md` is the
   canonical agent entry point; a platform-specific equivalent should route to it instead of duplicating its rules.
2. Choose a lower-kebab-case project ID and replace `house-project` in both `model/semasvg.project.yaml` and every
   starter SVG. The manifest and SVG root values must remain identical.
3. Copy `requirements-semasvg.txt.example` to `requirements-semasvg.txt`, replace the placeholder with a full Git commit
   hash, and commit that file as the canonical SemaSVG tool revision. This does not fully lock transitive Python
   dependencies or verify a signed tag.
4. Review `inventory/README.md`, `docs/property.md`, and `sources/README.md` before adding private facts or source
   material.
5. Run `make ci` before adding real semantic views; it installs the pinned validator and runs all checks. Consumers may
   wire this platform-neutral entry point into their chosen CI later.

The manifest owns the model's SemaSVG format and active profile versions. The full-commit requirement pin owns the
validator tool revision. Keep these versioned concerns separate.

`make qa` runs validation, SVG formatting, label freshness, and graph checks with `QA_JOBS=2` by default. It replaces
only ignored `var/qa/latest`, retains per-check logs there, and uses `var/qa/.lock` to reject overlapping suites. It
completes independent checks after a failure and prints compact failed output; use `VERBOSE=1` to print complete logs.

```bash
mkdir my-house
cp -R templates/house-project/. my-house/
cd my-house
git init
cp requirements-semasvg.txt.example requirements-semasvg.txt
# Replace REPLACE_WITH_FULL_COMMIT_HASH in requirements-semasvg.txt before continuing.
make ci
```

During SemaSVG upstream development, override the committed pin with a local validator checkout without changing it:

```bash
make ci SEMASVG_SOURCE=../semasvg/tools/validator
```

See `docs/README.md` for canonical document owners. Before adding real semantic facts, follow the complete semantic
bootstrap in the local root `AGENTS.md`.

## Canonical ownership

`model/` owns represented geometry, topology, and model facts. `inventory/` owns lifecycle and commercial equipment
facts. `docs/` owns authored property, project, and maintenance material. `sources/` owns evidence and pointers.
Automation subsystems, including ones in this repository, own runtime state and configuration separately from the
SemaSVG model. Ignored local folders are not canonical knowledge.

Use one fact with one owner. Serial numbers, warranty, manuals, service intervals, work orders, and history normally
belong outside SemaSVG. A derived copy must name its canonical owner and be refreshed or removed when that owner
changes.
