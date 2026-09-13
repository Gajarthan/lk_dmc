# OpenCode analysis and GitHub dataset publishing

The approved migration removes the previous external dataset hub integration.
OpenCode enriches extracted report text; GitHub data branches remain the public
archive and publication destination. The scraper, PDF extraction, historical
metadata, and four dataset labels remain compatible.

Use the existing requests dependency for an HTTPS Basic Auth client. Configuration
comes from OPENCODE_BASE_URL, OPENCODE_USERNAME (default opencode), and
OPENCODE_PASSWORD. An optional OPENCODE_MODEL uses provider/model syntax; otherwise
the server chooses its configured default. Do not embed credentials in code,
URLs, logs, or exported data. Inspect /global/health for diagnostics.

For each nonempty extracted document, create an isolated /session with all tool
permissions denied and submit text to /session/{id}/message. Request raw JSON
text with the output schema in the system prompt and validate it locally; this
avoids depending on the server's native structured-output tool.
Extract a summary, disaster types, locations, report date, impacts, and warnings.
Missing facts are null or empty arrays. Source text is untrusted data, not agent
instructions. Validate the returned structured data locally. No shell, file,
network tools or MCP actions are needed for analysis. Do not retry POST requests
automatically after ambiguous transport failures.

Save atomic analysis.json beside each report, recording source SHA-256, model,
schema version, status, and validated result. Resume matching successful results;
retry errors and changed text/configuration. Preserve original source artifacts.
Bound analysis attempts, input size, request timeout, and per-run time. Oversized
reports fail explicitly rather than silently truncating text. Empty text is skipped.

Commands: analyze for existing text, scrape --analyze for collection plus analysis,
export for neutral docs/chunks JSONL, and scrape --export for exports after scraping.
Remove the old publish command and provider-specific flags. Export available
analysis only when it matches the current text. GitHub Actions collects, optionally
analyzes when configured, exports, then commits all successful progress. Any stage
error is visible and fails the job after progress is saved. Analysis has conservative
default limits and remains optional when no service credentials are configured.

Tests cover API request contracts, denied tools, credentials and redirect handling,
malformed/error responses, structured output, resume/invalidation, limits, partial
failures, exports, CLI ordering, and regression of existing collection. A live
single-report smoke test is attempted using credentials only in process memory.
