import json

import pytest

from dmc.pipeline import run_pipeline
from dmc.sources import SOURCES
from tests.test_core import page, row

SOURCE = SOURCES["lk_dmc_situation_reports"]


class FixtureClient:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.visited = []

    def get_text(self, url):
        self.visited.append(url)
        value = next(self.pages)
        if isinstance(value, Exception):
            raise value
        return value


def test_pagination_continues_after_image_only_page(tmp_path):
    client = FixtureClient([page(row()), page(row("/image.jpg")), page(row("/second.pdf")), page()])
    result = run_pipeline(SOURCE, tmp_path, client=client, metadata_only=True)
    assert result.errors == []
    assert len(client.visited) == 4
    assert len(list(tmp_path.rglob("doc.json"))) == 2
    summary = json.loads((tmp_path / SOURCE.label / "summary.json").read_text())
    assert summary["n_docs"] == 2
    assert summary["n_docs_with_pdfs"] == 0


def test_repeated_page_is_reported_and_terminates(tmp_path):
    client = FixtureClient([page(row()), page(row())])
    result = run_pipeline(SOURCE, tmp_path, client=client, metadata_only=True)
    assert any("Repeated" in error for error in result.errors)
    assert len(client.visited) == 2


def test_failure_preserves_old_records_and_reports_error(tmp_path):
    run_pipeline(SOURCE, tmp_path, client=FixtureClient([page(row()), page()]), metadata_only=True)
    result = run_pipeline(
        SOURCE, tmp_path, client=FixtureClient([OSError("offline")]), metadata_only=True
    )
    assert result.errors and "offline" in result.errors[0]
    assert len(list(tmp_path.rglob("doc.json"))) == 1


def test_max_pages_limits_collection(tmp_path):
    result = run_pipeline(
        SOURCE, tmp_path, client=FixtureClient([page(row())]), max_pages=1, metadata_only=True
    )
    assert result.limited
    assert result.pages == 1


def test_stage_deadline_is_a_normal_limit_not_a_failed_collection(tmp_path):
    from dmc.client import DeadlineExceeded

    result = run_pipeline(
        SOURCE,
        tmp_path,
        client=FixtureClient([DeadlineExceeded("budget reached")]),
        metadata_only=True,
    )
    assert result.limited
    assert result.errors == []


def test_zero_limits_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_pipeline(SOURCE, tmp_path, max_pages=0)


def test_malformed_rows_are_not_a_successful_run(tmp_path):
    result = run_pipeline(
        SOURCE,
        tmp_path,
        client=FixtureClient([page(row(date="bad"), row()), page()]),
        metadata_only=True,
    )
    assert len(result.errors) == 1
    assert len(list(tmp_path.rglob("doc.json"))) == 1


def test_failed_download_attempts_count_toward_document_limit(tmp_path):
    class FailingClient(FixtureClient):
        attempts = 0

        def download_pdf(self, url, destination):
            self.attempts += 1
            raise OSError("offline")

    client = FailingClient([page(row(), row("/b.pdf"), row("/c.pdf")), page()])
    result = run_pipeline(SOURCE, tmp_path, client=client, max_documents=1)
    assert client.attempts == 1
    assert result.limited


def test_corrupt_processing_status_recovers_and_resume_skips_finished_pdf(tmp_path):
    from tests.test_processing import make_pdf

    class PDFClient(FixtureClient):
        downloads = 0

        def download_pdf(self, url, destination):
            self.downloads += 1
            make_pdf(destination)

    first = PDFClient([page(row()), page()])
    result = run_pipeline(SOURCE, tmp_path, client=first)
    assert result.processed == 1
    assert first.downloads == 1
    status = next(tmp_path.rglob("processing.json"))
    status.write_text("{broken")
    second = PDFClient([page(row()), page()])
    result = run_pipeline(SOURCE, tmp_path, client=second)
    assert result.processed == 1
    assert result.errors == []
    assert second.downloads == 0
    third = PDFClient([page(row()), page()])
    result = run_pipeline(SOURCE, tmp_path, client=third)
    assert result.processed == 0
    assert third.downloads == 0
