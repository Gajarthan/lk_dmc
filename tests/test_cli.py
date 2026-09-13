import pytest

from dmc.cli import main
from dmc.summaries import build_global_readme


def test_cli_help_without_credentials(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "scrape" in capsys.readouterr().out


def test_publish_requires_credentials_before_collecting(monkeypatch):
    monkeypatch.delenv("HUGGING_FACE_TOKEN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["scrape", "lk_dmc_situation_reports", "--publish", "--hf-namespace", "team"])
    assert exc.value.code == 2


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
