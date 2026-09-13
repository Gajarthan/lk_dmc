import json
from datetime import datetime, timedelta, timezone

import pytest

from dmc.models import Report
from dmc.parser import ParseError, parse_page
from dmc.sources import SOURCES
from dmc.storage import Storage

SOURCE = SOURCES["lk_dmc_situation_reports"]
URL = "https://www.dmc.gov.lk/index.php"


def row(href="/reports/a.pdf", description="Situation report", date="2026-09-13"):
    return (
        f"<tr><td>{description}</td><td>{date}</td><td>10:30</td>"
        f'<td><a href="{href}">Download</a></td></tr>'
    )


def page(*rows):
    return (
        '<table class="mtable"><tr class="mhead"><th>Reports</th></tr>' + "".join(rows) + "</table>"
    )


def test_rows_without_class_and_pdf_url_variants():
    result = parse_page(page(row("https://www.dmc.gov.lk/reports/A.PDF?download=1")), URL, SOURCE)
    assert not result.errors
    report = result.reports[0]
    assert report.url_pdf == "https://www.dmc.gov.lk/reports/A.PDF?download=1"
    assert report.lang == "und"
    expected = datetime(2026, 9, 13, 10, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert report.ut == int(expected.timestamp())


def test_skipped_images_do_not_make_a_page_empty():
    result = parse_page(page(row("/report.jpg")), URL, SOURCE)
    assert result.row_count == 1
    assert result.reports == []
    assert result.errors == []


def test_bad_row_is_reported_without_losing_valid_row():
    result = parse_page(page(row(date="not-a-date"), row()), URL, SOURCE)
    assert len(result.errors) == 1
    assert len(result.reports) == 1


def test_missing_link_is_skipped_and_missing_href_is_reported():
    html = page(row().replace('href="/reports/a.pdf"', ""))
    assert parse_page(html, URL, SOURCE).errors


def test_missing_table_is_a_failure():
    with pytest.raises(ParseError, match="table"):
        parse_page("<html>Unavailable</html>", URL, SOURCE)


def test_empty_table_ends_pagination():
    assert parse_page(page(), URL, SOURCE).row_count == 0


def test_legacy_document_id_and_directory_are_preserved(tmp_path):
    report = parse_page(page(row(description="Flood")), URL, SOURCE).reports[0]
    assert report.doc_id == "2026-09-13-10-30-flood"
    store = Storage(tmp_path, SOURCE.label)
    path = store.save(report)
    assert path.relative_to(tmp_path).as_posix() == (
        f"{SOURCE.label}/2020s/2026/2026-09-13-10-30-flood/doc.json"
    )
    assert json.loads(path.read_text()) == report.to_dict()


def test_long_legacy_ids_are_stable():
    import hashlib

    report = parse_page(page(row(description="A" * 50)), URL, SOURCE).reports[0]
    digest = hashlib.md5(report.num.encode()).hexdigest()[:8]
    assert report.doc_id == f"2026-09-13-{report.num[:23]}-{digest}"


def test_nested_markup_keeps_legacy_slug():
    report = parse_page(page(row(description="Heavy<b>Rain</b>")), URL, SOURCE).reports[0]
    assert report.num == "10-30-heavyrain"


def test_existing_metadata_is_preserved_on_resume(tmp_path):
    store = Storage(tmp_path, SOURCE.label)
    report = parse_page(page(row()), URL, SOURCE).reports[0]
    path = store.save(report)
    old = report.to_dict() | {"lang": "en", "custom": "preserve"}
    path.write_text(json.dumps(old))
    assert store.save(report) == path
    assert json.loads(path.read_text()) == old


def test_same_title_time_different_pdf_does_not_overwrite(tmp_path):
    store = Storage(tmp_path, SOURCE.label)
    first, second = parse_page(page(row(), row("/reports/b.pdf")), URL, SOURCE).reports
    a, b = store.save(first), store.save(second)
    assert a != b
    assert store.save(second) == b
    assert len(list(store.documents())) == 2


def test_invalid_metadata_fails_loudly(tmp_path):
    store = Storage(tmp_path, SOURCE.label)
    folder = store.directory / "2020s" / "2026" / "bad"
    folder.mkdir(parents=True)
    (folder / "doc.json").write_text("{}")
    with pytest.raises(ValueError, match="metadata"):
        list(store.documents())


def test_report_rejects_path_components():
    with pytest.raises(ValueError):
        Report("../escape", "x", "2026-09-13", "x", URL, "/x.pdf", "10:30", 1)
