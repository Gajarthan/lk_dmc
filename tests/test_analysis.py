import json
from unittest.mock import MagicMock

import pytest


def setup_report(root, doc_id="report1", text="Flood in Colombo"):
    path = root / "2020s" / "2026" / doc_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "doc.json").write_text(json.dumps({"doc_id": doc_id}), encoding="utf-8")
    if text is not None:
        (path / "doc.txt").write_text(text, encoding="utf-8")
    return path


def fake_client():
    from dmc.opencode import OpenCodeConfig

    client = MagicMock()
    client.config = OpenCodeConfig("https://example.org", "opencode", "secret")
    client.analyze.return_value = {
        "session_id": "ses_test",
        "result": {
            "summary": "Flood in Colombo",
            "locations": ["Colombo"],
            "disaster_types": ["flood"],
            "report_date": None,
            "impacts": [],
            "warnings": [],
        },
    }
    return client


def test_analysis_is_persisted_resumed_and_invalidated_by_changed_text(tmp_path):
    from dmc.analysis import analyze_dataset

    path = setup_report(tmp_path)
    client = fake_client()
    result = analyze_dataset(tmp_path, client=client)
    assert result.analyzed == 1
    saved = json.loads((path / "analysis.json").read_text())
    assert saved["status"] == "complete"
    assert len(saved["text_sha256"]) == 64
    assert "secret" not in (path / "analysis.json").read_text()
    assert analyze_dataset(tmp_path, client=client).skipped == 1
    assert client.analyze.call_count == 1
    (path / "doc.txt").write_text("Changed warning")
    assert analyze_dataset(tmp_path, client=client).analyzed == 1
    assert client.analyze.call_count == 2


def test_model_change_and_corrupt_cache_trigger_reanalysis(tmp_path):
    from dmc.analysis import analyze_dataset
    from dmc.opencode import OpenCodeConfig

    path = setup_report(tmp_path)
    client = fake_client()
    analyze_dataset(tmp_path, client=client)
    client.config = OpenCodeConfig("https://example.org", "opencode", "secret", model="p/m")
    assert analyze_dataset(tmp_path, client=client).analyzed == 1
    (path / "analysis.json").write_text("broken")
    assert analyze_dataset(tmp_path, client=client).analyzed == 1


def test_empty_and_missing_text_are_skipped_without_api_calls(tmp_path):
    from dmc.analysis import analyze_dataset

    setup_report(tmp_path, "empty", " \n")
    setup_report(tmp_path, "missing", None)
    client = fake_client()
    result = analyze_dataset(tmp_path, client=client)
    assert result.skipped == 2
    client.analyze.assert_not_called()


def test_failure_is_recorded_and_retried_without_losing_source(tmp_path):
    from dmc.analysis import analyze_dataset

    path = setup_report(tmp_path)
    client = fake_client()
    client.analyze.side_effect = ValueError("OpenCode returned HTTP 520")
    result = analyze_dataset(tmp_path, client=client)
    assert result.errors
    assert json.loads((path / "analysis.json").read_text())["status"] == "error"
    assert (path / "doc.txt").read_text() == "Flood in Colombo"
    client.analyze.side_effect = None
    assert analyze_dataset(tmp_path, client=client).analyzed == 1


def test_analysis_limits_attempts_and_never_silently_truncates(tmp_path):
    from dmc.analysis import analyze_dataset

    setup_report(tmp_path, "a", "x" * 201)
    setup_report(tmp_path, "b", "valid")
    client = fake_client()
    result = analyze_dataset(tmp_path, client=client, max_characters=200, max_documents=1)
    assert result.attempted == 1
    assert result.limited
    assert result.errors
    client.analyze.assert_not_called()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_documents": 0},
        {"max_seconds": -1},
        {"max_seconds": float("nan")},
        {"max_characters": 0},
    ],
)
def test_limits_are_validated_before_api_calls(tmp_path, kwargs):
    from dmc.analysis import analyze_dataset

    client = fake_client()
    with pytest.raises(ValueError):
        analyze_dataset(tmp_path, client=client, **kwargs)
    client.analyze.assert_not_called()


def test_permanent_failure_does_not_starve_later_reports_or_retries(tmp_path):
    from dmc.analysis import analyze_dataset

    setup_report(tmp_path, "a", "x" * 201)
    setup_report(tmp_path, "b", "valid b")
    setup_report(tmp_path, "c", "valid c")
    client = fake_client()
    client.analyze.side_effect = ValueError("OpenCode returned HTTP 520")
    for _ in range(3):
        analyze_dataset(tmp_path, client=client, max_documents=1, max_characters=200)
    assert [call.args[1] for call in client.analyze.call_args_list] == ["b", "c"]
    client.analyze.side_effect = None
    for _ in range(3):
        analyze_dataset(tmp_path, client=client, max_documents=1, max_characters=200)
    for doc in ("b", "c"):
        saved = json.loads((tmp_path / "2020s" / "2026" / doc / "analysis.json").read_text())
        assert saved["status"] == "complete"
