# README dashboard plan

**Goal:** Make the GitHub README the project's data and automation dashboard.

**Design:** A compact blue survey-board banner, native workflow badges, generated
coverage totals, four dataset rows, recent source reports, and useful action links.
Use GitHub-compatible Markdown and SVG, no scripts or embedded web app. Unknown
metrics remain unknown; empty published archives show zero and a collection action.
Move setup, API, architecture and migration detail into docs/guide.md. Preserve the
existing DATASETS marker contract so automated refreshes retain the static layout.

- [x] Build README shell, SVG banner and linked setup guide.
- [x] Add summary fields for validated current analysis and eight recent reports.
  Refresh summary after analysis/export and write run status before summary.
- [x] Build dashboard rendering with totals, dataset coverage, update timestamps,
  branch links and recent source reports; validate inputs and escape source text.
- [x] Refresh the README after pipeline completion, retaining scheduled/manual
  updates and safe serialized ordinary Git pushes.
- [x] Test unknown/empty/legacy data, current analysis hashes, safe links, input
  failure preservation, and marker idempotence. Run regressions, Ruff, actionlint.
- [ ] Render the actual published summaries, review GitHub display, commit and
  publish the authorized repository update. Verify hosted refresh and CI.
