# Code signing policy

Current builds are unsigned. No certificate or signing integration is active.

Author, reviewer and release approver: [B1GM4NT1NGS](https://github.com/B1GM4NT1NGS).

Release signing must use artifacts built from this repository's reviewed source in GitHub Actions. A maintainer must approve each production signing request. Signing credentials must be stored in protected GitHub environments, never in source files. Maintainers must enable multi-factor authentication before signing is enabled.

Any future signing integration requires an approved signing provider and verified build configuration. Unsigned upstream runtime components are included as dependencies; the project does not request standalone signatures for upstream libraries.

This program does not transfer video or other user information to networked systems. The first-run source launcher downloads dependencies from PyPI; external support and donation links open only when requested. See [Privacy policy](PRIVACY.md).
