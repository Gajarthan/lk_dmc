import pytest

from dmc.cli import main
from dmc.summaries import build_global_readme


def test_cli_help_without_credentials(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "scrape" in capsys.readouterr().out


def test_analysis_requires_credentials_before_collecting(monkeypatch):
    from unittest.mock import MagicMock

    from dmc import cli

    monkeypatch.delenv("OPENCODE_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCODE_PASSWORD", raising=False)
    pipeline = MagicMock()
    monkeypatch.setattr(cli, "run_pipeline", pipeline)
    with pytest.raises(SystemExit) as exc:
        main(["scrape", "lk_dmc_situation_reports", "--analyze"])
    assert exc.value.code == 2
    pipeline.assert_not_called()


def test_export_needs_no_service_credentials(tmp_path, monkeypatch):
    import json

    monkeypatch.delenv("OPENCODE_PASSWORD", raising=False)
    dataset = tmp_path / "lk_dmc_situation_reports"
    dataset.mkdir()
    (dataset / "doc.json").write_text(json.dumps({"doc_id": "a"}))
    assert main(["export", dataset.name, "--data-dir", str(tmp_path)]) == 0
    assert (dataset / "exports" / "docs.jsonl").is_file()


def test_collection_failure_skips_analysis_but_exports_progress(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from dmc import cli
    from dmc.pipeline import RunResult

    monkeypatch.setenv("OPENCODE_BASE_URL", "https://example.org")
    monkeypatch.setenv("OPENCODE_PASSWORD", "secret")
    monkeypatch.setattr(cli, "run_pipeline", lambda *a, **k: RunResult(errors=["failure"]))
    analyze = MagicMock()
    export = MagicMock(return_value=[])
    monkeypatch.setattr(cli, "analyze_dataset", analyze)
    monkeypatch.setattr(cli, "export_dataset", export)
    assert (
        main(
            [
                "scrape",
                "lk_dmc_situation_reports",
                "--analyze",
                "--export",
                "--data-dir",
                str(tmp_path),
            ]
        )
        == 1
    )
    analyze.assert_not_called()
    export.assert_called_once()


def test_analysis_failure_returns_nonzero_and_exports_progress(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from dmc import cli
    from dmc.analysis import AnalysisResult

    monkeypatch.setenv("OPENCODE_BASE_URL", "https://example.org")
    monkeypatch.setenv("OPENCODE_PASSWORD", "secret")
    monkeypatch.setattr(cli, "OpenCodeClient", MagicMock())
    analyze = MagicMock(return_value=AnalysisResult(errors=["HTTP 520"]))
    export = MagicMock(return_value=[])
    monkeypatch.setattr(cli, "analyze_dataset", analyze)
    monkeypatch.setattr(cli, "export_dataset", export)
    assert (
        main(
            [
                "analyze",
                "lk_dmc_situation_reports",
                "--max-documents",
                "2",
                "--export",
                "--data-dir",
                str(tmp_path),
            ]
        )
        == 1
    )
    assert analyze.call_args.kwargs["max_documents"] == 2
    export.assert_called_once()


def test_invalid_dataset_fails_helpfully():
    with pytest.raises(SystemExit) as exc:
        main(["scrape", "missing"])
    assert exc.value.code == 2


def test_readme_keeps_setup_content(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("# Project\n\nInstall with uv.\n")
    summary = {"doc_class_label": "lk_dmc_situation_reports", "n_docs": 2}
    build_global_readme(path, [summary])
    build_global_readme(path, [summary | {"n_docs": 3}])
    text = path.read_text(encoding="utf-8")
    assert "Install with uv." in text
    assert text.count("<!-- DATASETS:START -->") == 1
    assert "| Situation reports | 3 |" in text


def test_no_summaries_cannot_replace_readme(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("existing")
    with pytest.raises(ValueError):
        build_global_readme(path, [])
    assert path.read_text() == "existing"


def test_private_repository_readme_uses_authenticated_contents_api(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from dmc import cli
    from dmc.sources import SOURCES

    client = MagicMock()
    client.session.headers = {}
    client.__enter__.return_value = client
    client.get_json.side_effect = [{"doc_class_label": label, "n_docs": 0} for label in SOURCES]
    monkeypatch.setattr(cli, "Client", lambda: client)
    monkeypatch.setenv("GITHUB_TOKEN", "test-access-token")
    output = tmp_path / "README.md"
    assert main(["readme", "--repository", "owner/project", "--output", str(output)]) == 0
    assert client.session.headers["Authorization"] == "Bearer test-access-token"
    assert client.session.headers["Accept"] == "application/vnd.github.raw+json"
    for call, label in zip(client.get_json.call_args_list, SOURCES, strict=True):
        assert call.args[0] == (
            f"https://api.github.com/repos/owner/project/contents/data/{label}/summary.json"
            f"?ref=data_{label}"
        )
