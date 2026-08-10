# Changelog

All notable changes to SemaSVG are documented here.

The project follows Semantic Versioning once interfaces become stable. Versions before 1.0.0 are experimental.

## Unreleased

## 0.1.0 - 2026-09-06

First public experimental pre-1.0 release.

### Added

- Core semantics: `data-sema-*`, stable project entity identity separate from SVG representation identity, and physical
  and diagrammatic views.
- Building and Electrical profiles with versioned machine-readable schemas and vocabularies.
- Project manifests for multi-view projects and profile declarations, with unique view IDs and resolved file paths.
- Single-target entity-reference validation, rejecting empty and multiple-target values.
- Explicit physical-geometry selection for composite representations, excluding labels, decoration, and nested entities.
- Optional local certainty and source annotations without implicit inheritance between elements or representations.
- Optional native SVG titles and descriptions scoped to representations or whole views, with preservation requirements.
- Nonblocking property-conflict warnings for repeated entity current ratings, voltages, poles, manufacturers, and
  models.
- Prototype validator and public CLI commands: `validate`, `validate-vocabulary`, `format`, `inspect-graph`, and
  `materialize-labels`, which rejects all selected SVG symlinks before any source write.
- Synthetic public reference project and reusable house-repository starter templates.
- Authoring and integration documentation and AI-agent editing guidance.
