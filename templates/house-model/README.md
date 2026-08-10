# Additive house SemaSVG module

Copy this directory into a chosen subtree of an established repository, for example `house/`. It is intentionally only a
model module: it does not provide a root Makefile, `.gitignore`, requirements file, CI workflow, general documentation
tree, or source archive.

The example `cp -R templates/house-model house` assumes `house/` does not exist. If it already exists, merge the listed
module files deliberately under host policy; do not silently create `house/house-model` or overwrite host material.

## Integrate with the host repository

1. Add a root-agent routing rule in the host's `AGENTS.md` or the platform-specific equivalent, adapting `house/` to the
   chosen subtree: `For changes under house/, read house/AGENTS.md first.`

2. Choose a lower-kebab-case project ID and replace `house-project` in the copied `model/semasvg.project.yaml` and every
   starter SVG. Keep the manifest and SVG root declarations identical.

3. Install the validator through the host's existing dependency mechanism. The host owns dependency installation and the
   committed tool pin. For example, a PEP 508 requirement can be:

   ```text
   semasvg-validator @ git+https://github.com/ezoterik/semasvg.git@REPLACE_WITH_FULL_40_CHARACTER_COMMIT_HASH#subdirectory=tools/validator
   ```

   Replace the placeholder with a full 40-character Git commit hash. This immutable tool revision does not fully lock
   transitive Python dependencies or verify a signed tag.

4. Add equivalent read-only checks to the host's existing QA commands without overwriting host files. Adapt `house/` to
   the chosen subtree:

   ```bash
   semasvg validate house/model
   semasvg format house/model --check
   semasvg materialize-labels house/model --check
   semasvg inspect-graph house/model > /dev/null
   ```

The manifest declares the SemaSVG format and active profile versions for the model. The validator pin selects the tool
revision that implements checks. Keep these separate: do not add repository URLs to `semasvg.project.yaml`, and do not
copy the complete upstream specification into the host repository. Follow the versioned upstream links in `AGENTS.md`
when changing model semantics.

`model/` owns represented geometry, topology, and model facts only. Keep inventory, authored documentation, source
records, and automation runtime/configuration in the host repository's existing owners. Ignored local folders are not
canonical knowledge.
