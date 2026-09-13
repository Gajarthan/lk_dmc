# OpenCode migration verification

Verified locally on 2026-09-13:

- 97 offline tests passed on Python 3.13 and isolated Python 3.11.
- Ruff lint and format checks passed.
- All four GitHub Actions workflows passed actionlint.
- Source distribution and wheel built successfully for version 3.0.0.
- Review findings were reproduced with failing tests, fixed, and independently
  re-reviewed: fair retry ordering, elapsed streaming deadlines, and validation
  of cached analysis before export.
- The live server specification was inspected through the authenticated browser:
  session creation, permissions, model selection, structured prompts and responses.
- Direct authenticated health requests from the local process failed to connect.
  Live inference is therefore not claimed by the local test results. The manual
  OpenCode check workflow can validate health and a synthetic prompt from GitHub.

The integration stores service credentials only in process environment variables
or GitHub Actions secrets. No credentials are embedded in the repository. Source
data remains in GitHub data branches; OpenCode supplies generated analysis.
