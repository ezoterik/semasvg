# Sources, privacy, and certainty

This directory owns provenance for project facts. A source record should include a source ID, kind and location, capture
or issue date, access class, checksum when useful, affected stable IDs, certainty, and limitations. Use non-validated
Markdown tokens such as `source:original-plan-2024` and `entity:room-kitchen` to make source-to-entity links searchable.
Private plans, addresses, and photos may be governed by an access-controlled storage policy. Credentials, tokens,
private keys, and other secrets are never repository knowledge and must never be committed. When a source does not
establish a fact, mark it unknown in the model or omit the unsupported property; do not infer a plausible value.
