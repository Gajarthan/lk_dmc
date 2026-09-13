# Standalone report pipeline proposal

Status: implemented and locally verified. See ../verification.md for evidence and limits.

## Objective

Remove the remaining author-specific Python packages and container dependency,
and move the report pipeline into independently testable local modules.
Retain collection of the existing four report categories and scheduled dataset
publication. Repository ownership and publishing destinations come from
configuration, with no hardcoded personal account.

## Alternatives

1. Replace only the external helpers while keeping the inherited document
   classes. This minimizes interface changes but leaves document parsing,
   storage, and publishing coupled together.
2. Use a modular Python pipeline with explicit inputs and outputs. Recommended:
   it fits the existing scheduled workload and makes failures easier to test.
3. Add an API or dashboard around the pipeline. This introduces a service,
   deployment, and interface requirements beyond the current batch workflow.

## Proposed layout

```text
src/dmc/
  models.py       Report metadata and collection results
  sources.py      Configuration for the four report categories
  client.py       HTTP requests, timeouts, retries, and download limits
  parser.py       HTML rows, PDF links, dates, and pagination information
  storage.py      Metadata and document files, atomic writes, resume support
  processing.py   PDF text/table extraction and processing status
  summaries.py    Dataset statistics and neutral Markdown generation
  publishing.py   Optional Hugging Face publication
  pipeline.py     Orchestration, time budget, and failure reporting
  cli.py          Command-line options and validation
tests/
  fixtures/       HTML and small PDF fixtures for offline verification
```

The flow is collection -> validated metadata -> local storage -> PDF processing
-> summaries -> optional publication. Use standard-library logging and date/time
handling. Declare and pin direct third-party dependencies for HTML parsing, PDF
processing, and optional publication instead of relying on a prebuilt runtime.

## Behavior and compatibility

- Keep the four existing dataset labels and report-source query parameters.
- Retain the metadata fields visible in the current code: num, date_str,
  description, url_metadata, lang, url_pdf, time_str, and ut.
- Document timestamp timezone handling and avoid claiming a document language
  solely from the website's navigation language.
- Keep existing workflow script entry points as thin CLI adapters.
- Make output directories explicit and support existing data branch checkouts.
- Validate representative existing output records before claiming storage-format
  compatibility; the downloaded project contains no dataset files.
- Preserve existing data during migration. Do not delete or overwrite records
  merely because an upstream page or document cannot be fetched.
- Generate statistics from stored records. Generated documentation must not
  restore personal attribution, personal-account links, or citation badges.
- Separate collection from publication so local runs do not require credentials.

## Failure handling

Normalize relative and absolute PDF URLs and validate their parsed paths.
Handle missing HTML attributes explicitly. Distinguish the end of pagination
from a page whose rows were skipped or failed parsing. Detect repeated pages
and impose configurable request/page limits. Missing tables and failed requests
produce actionable failures, rather than a successful empty dataset.

Write files atomically and record processing errors for retry. Surface partial
failures in the command result. Publishing requires an explicit destination and
credentials; Git updates use ordinary pushes and stop when rebasing fails.

## Automation

Replace the custom container with a standard Python setup and explicit dependency
installation. Retain the two-hour collection schedule and the four-category
matrix. Serialize overlapping writes to the same branch. Run offline tests on
pull requests and before publication. Keep README generation independent from
collection, with project-controlled templates.

## Acceptance checks

- No remaining author-specific package, image, or account references in source,
  requirements, generated documentation, or workflow configuration.
- A clean environment can install the project and run CLI help and offline tests.
- Fixture tests cover malformed rows, PDF URL variants, pagination skips,
  repeated pages, and missing tables.
- An offline integration run writes metadata, processes a small PDF, generates
  summaries, and resumes without duplicating existing records.
- Tests exercise failed downloads and failed publication without real uploads.
- A bounded live collection smoke test verifies source integration when network
  access permits; publication and bulk historical scraping are separate actions.

## Review boundary

The user selected the scheduled dataset pipeline. API/dashboard work is outside
this implementation.
Historical PDF extraction parity, including OCR, must be characterized from
representative inputs during implementation; any unsupported capability must
be documented explicitly rather than silently omitted.
