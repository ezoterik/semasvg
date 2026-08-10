# Consumer starter templates

`house-project/` is the complete synthetic starter for a dedicated whole-home repository. It includes its own Makefile,
dependency example, documentation routes, inventory owner, and source-record owner. It intentionally ships no
provider-specific CI workflow; consumers can wire its existing `make ci` entry point into their chosen CI.

`house-model/` is the minimal synthetic additive starter. Copy it into a selected subtree of an established repository;
it deliberately has no root tooling, dependency, CI, documentation, or source-archive files that could collide with the
host repository. The [house repository guide](../docs/house-repositories.md) explains when to use each topology.
