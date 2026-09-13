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
- The initial [hosted check](https://github.com/Gajarthan/lk_dmc/actions/runs/34743883991)
  failed at health with HTTP 520. VPS inspection later confirmed an Nginx bot map
  rejects python-requests and returns 444, which Cloudflare exposes as 520.
- Controlled User-Agent swaps between curl and Python made failure follow the
  header. With DMC-Report-Collector/3.0, authenticated health returned 200 and
  healthy=true/version=1.18.30; without credentials it returned 401. The client
  now sends that truthful application identity. No VPS configuration was changed.
- The configured default opencode/big-pickle model returned StructuredOutputError
  with native json_schema output. A controlled prompt requesting plain JSON with
  the same schema succeeded and passed local validation. The client now uses this
  tool-free output approach and retains strict validation and all permission denials.
- All 97 tests pass after both fixes, including regression checks for request
  identity and the output schema in the prompt. Independent review found no
  material issues. A hosted recheck is recorded separately when complete.

The integration stores service credentials only in process environment variables
or GitHub Actions secrets. No credentials are embedded in the repository. Source
data remains in GitHub data branches; OpenCode supplies generated analysis.

Repository configuration: OPENCODE_PASSWORD is stored as a GitHub Actions secret;
OPENCODE_BASE_URL and OPENCODE_USERNAME are configured as repository variables.
The server default model is used. Code and documentation were published to main.
