# Verification: standalone pipeline

Completed 2026-09-13 in the local Windows workspace.

- Python 3.13: 51 tests passed.
- Python 3.11 isolated environment: 51 tests passed.
- Ruff lint and formatting checks passed.
- Source distribution and wheel built successfully with `uv build`.
- All three GitHub Actions workflow files passed actionlint 1.7.12.
- CLI and legacy workflow-script help commands succeeded.
- Live bounded collection retrieved ten metadata records from each of the four
  DMC report categories, with no reported parsing errors.
- One live situation-report PDF was downloaded and processed: three pages,
  6,297 extracted text characters, four tables, and no pages without text.
- Global README generation successfully rendered statistics from the smoke data.
- Named original-project author references and the old package/container imports
  are absent from maintained code, configuration, documentation, and lockfile.
- Independent reviews of core collection/storage/workflows and PDF/publication
  modules found no remaining material issues after regression fixes.

## Execution boundaries

No Hugging Face upload, remote Git push, or bulk historical download was performed.
Publication tests use a fake Hub API. Real publication requires the repository
branches and account configuration described in the project README. GitHub Actions
was validated locally, not executed on hosted Windows or Linux runners.

The downloaded source contains no historical data branches, so migration behavior
was verified against local records matching the inspected historical schema, not
against the entire published archive. Legacy document IDs, metadata, PDF names,
and directory layout are preserved; extracted blocks and Hugging Face output
serialization change as documented in README. PDF extraction does not include OCR.

Live-check output is retained in ignored `smoke-data/`. Build artifacts are in
ignored `dist/`. The source directory is not a Git checkout, so no commits were made.
