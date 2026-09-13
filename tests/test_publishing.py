import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def write_doc(dataset, doc_id, text, **metadata):
    directory = dataset / "2026-09-13" / doc_id
    directory.mkdir(parents=True)
    (directory / "doc.json").write_text(
        json.dumps({"doc_id": doc_id, **metadata}), encoding="utf-8"
    )
    if text is not None:
        (directory / "doc.txt").write_text(text, encoding="utf-8")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_publish_exports_metadata_and_overlapping_unicode_chunks(tmp_path, monkeypatch):
    from dmc import publishing

    dataset = tmp_path / "lk_dmc_situation_reports"
    text = "සිංහල " + "abcdef" * 740
    write_doc(dataset, "report-a", text, doc_type="SituationReport", lang="si", ut=123)
    write_doc(dataset, "report-empty", "  \n")
    write_doc(dataset, "report-missing", None)
    api = MagicMock()
    constructor = MagicMock(return_value=api)
    monkeypatch.setattr(publishing, "HfApi", constructor)

    repos = publishing.publish_dataset(dataset, "example-team", "fake-token")

    assert repos == [
        "example-team/lk-dmc-situation-reports-docs",
        "example-team/lk-dmc-situation-reports-chunks",
    ]
    output = dataset / "hugging_face_data"
    docs = read_jsonl(output / "docs.jsonl")
    chunks = read_jsonl(output / "chunks.jsonl")
    assert len(docs) == 3
    assert docs[0]["doc_id"] == "report-a"
    assert docs[0]["doc_type"] == "SituationReport"
    assert docs[0]["ut"] == 123
    assert docs[0]["text"] == text
    assert docs[1]["text"] == "  \n"
    assert docs[2]["text"] == ""
    assert len(chunks) == 3
    assert chunks[0]["chunk_text"][-200:] == chunks[1]["chunk_text"][:200]
    assert chunks[0]["chunk_text"] + "".join(c["chunk_text"][200:] for c in chunks[1:]) == text
    for i, chunk in enumerate(chunks):
        assert 0 < len(chunk["chunk_text"]) <= 2000
        assert chunk["chunk_id"] == f"report-a-{i:04d}"
        assert chunk["chunk_index"] == i
        assert chunk["language"] == "si"
        assert chunk["chunk_size_bytes"] == len(chunk["chunk_text"].encode("utf-8"))
        assert chunk["md5"] == hashlib.md5(chunk["chunk_text"].encode("utf-8")).hexdigest()
    constructor.assert_called_once_with(token="fake-token")
    assert api.create_repo.call_count == 2
    assert api.upload_file.call_count == 4
    for repo in repos:
        api.create_repo.assert_any_call(repo_id=repo, repo_type="dataset", exist_ok=True)
        uploads = [c.kwargs for c in api.upload_file.call_args_list if c.kwargs["repo_id"] == repo]
        kind = repo.rsplit("-", 1)[1]
        assert {u["path_in_repo"] for u in uploads} == {f"{kind}.jsonl", "README.md"}
        card = next(u for u in uploads if u["path_in_repo"] == "README.md")
        content = card["path_or_fileobj"]
        if not isinstance(content, bytes):
            content = open(content, "rb").read()
        assert b"split: train" in content
        assert f"path: {kind}.jsonl".encode() in content


@pytest.mark.parametrize("namespace,token", [("", "x"), ("  ", "x"), ("team", ""), ("team", " ")])
def test_publish_requires_namespace_and_token_before_upload(
    tmp_path, monkeypatch, namespace, token
):
    from dmc import publishing

    api = MagicMock()
    monkeypatch.setattr(publishing, "HfApi", api)
    with pytest.raises(ValueError):
        publishing.publish_dataset(tmp_path, namespace, token)
    api.assert_not_called()


def test_publish_propagates_upload_failure_and_keeps_local_export(tmp_path, monkeypatch):
    from dmc import publishing

    dataset = tmp_path / "reports"
    write_doc(dataset, "a", "A report")
    api = MagicMock()
    api.upload_file.side_effect = RuntimeError("upload failed")
    monkeypatch.setattr(publishing, "HfApi", MagicMock(return_value=api))
    with pytest.raises(RuntimeError, match="upload failed"):
        publishing.publish_dataset(dataset, "team", "fake-token")
    assert read_jsonl(dataset / "hugging_face_data" / "docs.jsonl")[0]["doc_id"] == "a"


def test_publish_rejects_metadata_without_document_id(tmp_path, monkeypatch):
    from dmc import publishing

    write_doc(tmp_path, "a", "A report")
    next(tmp_path.rglob("doc.json")).write_text("{}", encoding="utf-8")
    api = MagicMock()
    monkeypatch.setattr(publishing, "HfApi", api)
    with pytest.raises(ValueError, match="doc_id"):
        publishing.publish_dataset(tmp_path, "team", "fake-token")
    api.assert_not_called()


def test_metadata_only_archive_publishes_all_documents(tmp_path, monkeypatch):
    from dmc import publishing

    write_doc(tmp_path, "a", None, description="Awaiting extraction")
    write_doc(tmp_path, "b", "", description="Scanned report")
    api = MagicMock()
    monkeypatch.setattr(publishing, "HfApi", MagicMock(return_value=api))

    publishing.publish_dataset(tmp_path, "team", "fake-token")

    docs = read_jsonl(tmp_path / "hugging_face_data" / "docs.jsonl")
    assert [doc["doc_id"] for doc in docs] == ["a", "b"]
    assert all(doc["text"] == "" for doc in docs)
    assert docs[0]["description"] == "Awaiting extraction"
    assert read_jsonl(tmp_path / "hugging_face_data" / "chunks.jsonl") == []
    doc_upload = next(
        call.kwargs
        for call in api.upload_file.call_args_list
        if call.kwargs["path_in_repo"] == "docs.jsonl"
    )
    assert len(read_jsonl(Path(doc_upload["path_or_fileobj"]))) == 2


@pytest.mark.parametrize("malformed", [False, True])
def test_bad_archive_preserves_prior_exports_and_does_not_upload(tmp_path, monkeypatch, malformed):
    from dmc import publishing

    output = tmp_path / "hugging_face_data"
    output.mkdir()
    for name in ("docs.jsonl", "chunks.jsonl"):
        (output / name).write_text("prior export", encoding="utf-8")
    if malformed:
        write_doc(tmp_path, "a", "Valid first report")
        write_doc(tmp_path, "z", None)
        (tmp_path / "2026-09-13" / "z" / "doc.json").write_text("{}", encoding="utf-8")
    api = MagicMock()
    monkeypatch.setattr(publishing, "HfApi", api)

    with pytest.raises(ValueError, match="doc_id|No metadata"):
        publishing.publish_dataset(tmp_path, "team", "fake-token")

    assert (output / "docs.jsonl").read_text(encoding="utf-8") == "prior export"
    assert (output / "chunks.jsonl").read_text(encoding="utf-8") == "prior export"
    assert sorted(path.name for path in output.iterdir()) == ["chunks.jsonl", "docs.jsonl"]
    api.assert_not_called()


@pytest.mark.parametrize(
    "namespace", ["team/repo", "https://huggingface.co/team", "../team", "two teams"]
)
def test_publish_rejects_invalid_namespace(tmp_path, monkeypatch, namespace):
    from dmc import publishing

    write_doc(tmp_path, "a", "Report")
    api = MagicMock()
    monkeypatch.setattr(publishing, "HfApi", api)
    with pytest.raises(ValueError, match="namespace"):
        publishing.publish_dataset(tmp_path, namespace, "fake-token")
    api.assert_not_called()
    assert not (tmp_path / "hugging_face_data").exists()


def test_publish_requires_existing_dataset_directory(tmp_path, monkeypatch):
    from dmc import publishing

    api = MagicMock()
    monkeypatch.setattr(publishing, "HfApi", api)
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="directory"):
        publishing.publish_dataset(missing, "team", "fake-token")
    api.assert_not_called()
    assert not missing.exists()


def test_publish_skips_whitespace_windows_and_preserves_original_chunk_indexes(
    tmp_path, monkeypatch
):
    from dmc import publishing

    write_doc(tmp_path, "trailing", "real report" + " " * 4000)
    write_doc(tmp_path, "middle", "real report" + " " * 4000 + "another report")
    monkeypatch.setattr(publishing, "HfApi", MagicMock())

    publishing.publish_dataset(tmp_path, "team", "fake-token")

    chunks = read_jsonl(tmp_path / "hugging_face_data" / "chunks.jsonl")
    assert all(chunk["chunk_text"].strip() for chunk in chunks)
    assert [chunk["chunk_id"] for chunk in chunks if chunk["doc_id"] == "trailing"] == [
        "trailing-0000"
    ]
    middle = [chunk for chunk in chunks if chunk["doc_id"] == "middle"]
    assert [chunk["chunk_index"] for chunk in middle] == [0, 2]
    assert [chunk["chunk_id"] for chunk in middle] == ["middle-0000", "middle-0002"]
