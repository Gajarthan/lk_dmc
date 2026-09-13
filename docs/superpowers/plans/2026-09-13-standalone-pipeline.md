# Standalone Pipeline Implementation Plan

> Use test-driven development and review the completed integration before delivery.

**Goal:** Keep scheduled scraping and dataset publication with project-owned code.

**Architecture:** Explicit report configuration, HTTP client, parser, local storage,
PDF processing, summaries, optional publisher, and CLI. Preserve historical document
IDs and directories; separate extraction status from source metadata.

**Stack:** Python 3.11+, requests, Beautiful Soup, pdfplumber, huggingface-hub,
pytest, Ruff. Lock resolved versions. Use standard Python GitHub Actions runners.

This directory is a downloaded archive without `.git`; work directly in the
authorized workspace without commits or worktrees.

- [x] Add packaging, a locked environment, and parser/storage regression tests.
  Verify missing implementation fails before replacing imports. Preserve IDs:
  dates plus normalized num, shortened to 23 characters and an eight-character
  MD5 suffix when num has at least 32 characters. Preserve paths:
  `data/<label>/<decade>/<year>/<doc_id>/doc.json` and `doc.pdf`.
- [x] Implement `models.py`, `sources.py`, `parser.py`, `client.py`, and
  `storage.py`. Test missing attributes, URL variants, malformed tables, partial
  pages, duplicate IDs, atomic writes, and preservation of existing metadata.
- [x] Implement and test `processing.py` and `publishing.py` independently.
  `process_pdf(pdf_path: Path) -> dict` writes text, blocks, and table CSVs next
  to the PDF and returns extraction status, including pages without text.
  `publish_dataset(dataset_dir: Path, namespace: str, token: str) -> list[str]`
  exports metadata and text chunks to two dataset repositories, with explicit
  destinations, exceptions propagated, and no real uploads during tests.
- [x] Implement `pipeline.py`, `summaries.py`, and `cli.py`; replace old class
  inheritance with source configuration. Retain script entry points. Exercise
  resume and bounded scraping through injected HTTP fixtures and actual PDFs.
- [x] Replace both workflows, add test CI, and document local setup, runtime
  limits, data migration, publishing settings, and extraction differences.
- [x] Run `uv run pytest`, `uv run ruff check .`, CLI help, and a bounded live
  scrape into ignored local output. Verify all personal dependency/image names
  are absent from maintained project files. Review specification compliance and
  code quality; address discovered defects and repeat affected checks.

External publication is configured and tested with fakes; no upload, remote
branch write, or historical bulk download is part of this local implementation.
