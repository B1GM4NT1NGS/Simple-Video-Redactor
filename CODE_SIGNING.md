# Code signing policy

SignPath Foundation application preparation is in progress. The project has not yet been accepted, and current builds are unsigned. Once approved, the intended attribution is: Free code signing provided by SignPath.io, certificate by SignPath Foundation.

Author, reviewer and release approver: [B1GM4NT1NGS](https://github.com/B1GM4NT1NGS).

Release signing must use artifacts built from this repository's reviewed source in GitHub Actions. A maintainer must approve each production signing request. Signing credentials must be stored in protected GitHub environments, never in source files. Maintainers must enable multi-factor authentication before signing is enabled.

No signing integration is enabled until SignPath has approved the project and provided the required organization, project and policy configuration. Unsigned upstream runtime components are included as dependencies; the project does not request standalone signatures for upstream libraries.

This program does not transfer video or other user information to networked systems. The first-run source launcher downloads dependencies from PyPI; external support and donation links open only when requested. See [Privacy policy](PRIVACY.md).
