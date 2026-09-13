import hashlib
import json

import pytest

from dmc.parser import parse_page
from dmc.sources import SOURCES
from dmc.storage import Storage, write_json
from dmc.summaries import build_global_readme, build_summary
from tests.test_analysis import fake_client
from tests.test_core import page, row

LABEL = "lk_dmc_situation_reports"


def summary(**values):
    return {
        "doc_class_label": LABEL,
        "n_docs": 4,
        "n_docs_with_pdfs": 3,
        "n_docs_with_text": 2,
        "n_docs_with_analysis": 1,
        "n_docs_with_tabular": 1,
        "dataset_size": 2048,
        "time_updated": "2026-09-13T06:00:00+00:00",
        "date_str_max": "2026-09-13",
        **values,
    }


def test_dashboard_renders_coverage_links_and_preserves_shell(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("# Dashboard\n<!-- DATASETS:START -->old<!-- DATASETS:END -->\nSetup guide\n")
    build_global_readme(path, [summary()], repository="owner/repo")
    text = path.read_text(encoding="utf-8")
    assert "Coverage" in text
    assert "**4**" in text and "**3**" in text and "**2**" in text and "**1**" in text
    assert "2026-09-13 06:00 UTC" in text
    assert "https://github.com/owner/repo/tree/data_lk_dmc_situation_reports/data/" in text
    assert "Not available" in text  # Missing categories are not shown as zero/healthy.
    assert text.startswith("# Dashboard") and text.endswith("Setup guide\n")
    build_global_readme(path, [summary()], repository="owner/repo")
    assert path.read_text(encoding="utf-8") == text


def test_empty_dashboard_shows_collection_action_not_healthy_status(tmp_path):
    path = tmp_path / "README.md"
    data = [{"doc_class_label": label, "n_docs": 0} for label in SOURCES]
    build_global_readme(path, data, repository="owner/repo")
    text = path.read_text(encoding="utf-8")
    assert "No reports have been published yet" in text
    assert "actions/workflows/pipeline.yml" in text
    assert "Waiting for reports" in text
    assert "100%" not in text


def test_legacy_summary_does_not_invent_analysis_totals(tmp_path):
    path = tmp_path / "README.md"
    build_global_readme(path, [{"doc_class_label": LABEL, "n_docs": 12}])
    text = path.read_text(encoding="utf-8")
    assert "Not reported" in text
    assert "12" in text


@pytest.mark.parametrize(
    "data",
    [
        [summary(n_docs=-1)],
        [summary(n_docs="4")],
        [summary(n_docs=True)],
        [summary(), summary()],
        [summary(doc_class_label="unknown")],
        [None],
    ],
)
def test_invalid_summary_preserves_existing_readme(tmp_path, data):
    path = tmp_path / "README.md"
    path.write_text("Keep dashboard")
    with pytest.raises(ValueError):
        build_global_readme(path, data)
    assert path.read_text() == "Keep dashboard"


@pytest.mark.parametrize(
    "content",
    [
        "<!-- DATASETS:START -->unfinished",
        "<!-- DATASETS:END -->wrong<!-- DATASETS:START -->",
        "<!-- DATASETS:START --><!-- DATASETS:START --><!-- DATASETS:END -->",
    ],
)
def test_malformed_markers_preserve_existing_readme(tmp_path, content):
    path = tmp_path / "README.md"
    path.write_text(content)
    with pytest.raises(ValueError, match="markers"):
        build_global_readme(path, [summary()])
    assert path.read_text() == content


def test_recent_reports_escape_titles_and_reject_unsafe_links(tmp_path):
    path = tmp_path / "README.md"
    data = summary(
        latest_reports=[
            {
                "date_str": "2026-09-13",
                "description": "Flood | [bad](link)\n<script>",
                "url_pdf": "javascript:alert(1)",
                "doc_id": "a",
            },
            {
                "date_str": "2026-09-12",
                "description": "Rain",
                "doc_id": "b",
                "url_pdf": "https://www.dmc.gov.lk/report.pdf",
            },
        ]
    )
    build_global_readme(path, [data])
    text = path.read_text(encoding="utf-8")
    assert "javascript:" not in text and "<script>" not in text
    assert "Flood \\|" in text
    assert "https://www.dmc.gov.lk/report.pdf" in text


def test_summary_counts_only_current_validated_analysis_and_latest_run(tmp_path):
    source = SOURCES[LABEL]
    store = Storage(tmp_path, LABEL)
    reports = parse_page(
        page(row(), row("/b.pdf", date="2026-09-12")), "https://www.dmc.gov.lk", source
    )
    for report in reports.reports:
        path = store.save(report)
        path.with_name("doc.txt").write_text("Flood warning", encoding="utf-8")
        write_json(
            path.with_name("analysis.json"),
            {
                "status": "complete",
                "text_sha256": hashlib.sha256(b"Flood warning").hexdigest(),
                "result": fake_client().analyze.return_value["result"],
            },
        )
    next(store.directory.rglob("doc.txt")).write_text("Changed source", encoding="utf-8")
    write_json(store.directory / "run.json", {"errors": ["offline"], "limited": False})
    value = build_summary(store, source)
    assert value["n_docs_with_analysis"] == 1
    assert value["collection_status"] == "Needs attention"
    assert value["latest_reports"][0]["date_str"] == "2026-09-13"
    assert len(value["latest_reports"]) == 2


def test_export_refreshes_existing_summary_analysis_counts(tmp_path):
    from dmc.cli import main

    source = SOURCES[LABEL]
    store = Storage(tmp_path, LABEL)
    report = parse_page(page(row()), "https://www.dmc.gov.lk", source).reports[0]
    path = store.save(report)
    path.with_name("doc.txt").write_text("Report", encoding="utf-8")
    build_summary(store, source)
    write_json(
        path.with_name("analysis.json"),
        {
            "status": "complete",
            "text_sha256": hashlib.sha256(b"Report").hexdigest(),
            "result": fake_client().analyze.return_value["result"],
        },
    )
    assert main(["export", LABEL, "--data-dir", str(tmp_path)]) == 0
    value = json.loads((store.directory / "summary.json").read_text())
    assert value["n_docs_with_analysis"] == 1


def test_incomplete_run_status_is_unknown_and_recent_reports_are_not_truncated(tmp_path):
    source = SOURCES[LABEL]
    store = Storage(tmp_path, LABEL)
    reports = parse_page(
        page(*(row(f"/{day}.pdf", date=f"2026-09-{day:02}") for day in range(1, 10))),
        "https://www.dmc.gov.lk",
        source,
    )
    for report in reports.reports:
        store.save(report)
    write_json(store.directory / "run.json", {})
    value = build_summary(store, source)
    assert value["collection_status"] == "Not reported"
    assert [r["date_str"] for r in value["latest_reports"]] == [
        f"2026-09-{day:02}" for day in range(9, 1, -1)
    ]
