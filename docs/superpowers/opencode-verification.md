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
  The hosted [OpenCode check](https://github.com/Gajarthan/lk_dmc/actions/runs/34743883991)
  also failed at health with HTTP 520. It did not submit a prompt. Live inference
  remains unverified until the service accepts automated authenticated requests.

The integration stores service credentials only in process environment variables
or GitHub Actions secrets. No credentials are embedded in the repository. Source
data remains in GitHub data branches; OpenCode supplies generated analysis.

Repository configuration: OPENCODE_PASSWORD is stored as a GitHub Actions secret;
OPENCODE_BASE_URL and OPENCODE_USERNAME are configured as repository variables.
The server default model is used. Code and documentation were published to main.
