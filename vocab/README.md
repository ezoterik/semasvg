# Vocabulary

These YAML files are the machine-readable companion to the normative Markdown specifications.

They are intended to support:

- validators;
- IDE completion;
- documentation generation;
- AI context generation;
- future schema tooling.

Before 1.0.0, the normative Markdown specification wins if prose and YAML disagree.

The [vocabulary schema](../schemas/vocabulary.schema.json) describes the basic YAML shape, while [specifications](../spec/README.md) own normative semantics.

Validate the bundled vocabularies with:

```bash
semasvg validate-vocabulary vocab
```
