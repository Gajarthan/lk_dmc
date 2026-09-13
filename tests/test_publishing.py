import hashlib
import json
from pathlib import Path

import pytest

from dmc import publishing


def write_doc(dataset, doc_id, text, **metadata):
    directory = dataset / "2026-09-13" / doc_id
    directory.mkdir(parents=True)
    (directory / "doc.json").write_text(
        json.dumps({"doc_id": doc_id, **metadata}), encoding="utf-8"
    )
    if text is not None:
        (directory / "doc.txt").write_text(text, encoding="utf-8")
    return directory


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_export_metadata_and_overlapping_unicode_chunks(tmp_path):
    dataset = tmp_path / "lk_dmc_situation_reports"
    text = "සිංහල " + "abcdef" * 740
    directory = write_doc(dataset, "report-a", text, doc_type="SituationReport", lang="si", ut=123)
    original_metadata = (directory / "doc.json").read_bytes()
    write_doc(dataset, "report-empty", "  \n")
    write_doc(dataset, "report-missing", None)

    paths = publishing.export_dataset(dataset)

    output = dataset / "exports"
    assert paths == [output / "docs.jsonl", output / "chunks.jsonl"]
    assert all(isinstance(path, Path) and path.is_file() for path in paths)
    docs, chunks = [read_jsonl(path) for path in paths]
    assert len(docs) == 3
    assert docs[0]["doc_id"] == "report-a"
    assert docs[0]["doc_type"] == "SituationReport"
    assert docs[0]["ut"] == 123
    assert docs[0]["text"] == text
    assert docs[1]["text"] == "  \n"
    assert docs[2]["text"] == ""
    assert docs[2]["doc_type"] == dataset.name
    assert docs[2]["language"] == "und"
    assert all(doc["analysis"] is None for doc in docs)
    assert "සිංහල" in paths[0].read_text(encoding="utf-8")
    assert (directory / "doc.json").read_bytes() == original_metadata
    assert len(chunks) == 3
    assert chunks[0]["chunk_text"][-200:] == chunks[1]["chunk_text"][:200]
    assert chunks[0]["chunk_text"] + "".join(c["chunk_text"][200:] for c in chunks[1:]) == text
    for i, chunk in enumerate(chunks):
        assert 0 < len(chunk["chunk_text"]) <= 2000
        assert chunk["chunk_id"] == f"report-a-{i:04d}"
        assert chunk["chunk_index"] == i
        assert chunk["language"] == "si"
        assert chunk["ut"] == 123
        assert chunk["chunk_size_bytes"] == len(chunk["chunk_text"].encode("utf-8"))
        assert chunk["md5"] == hashlib.md5(chunk["chunk_text"].encode("utf-8")).hexdigest()


@pytest.mark.parametrize("metadata", ["{}", "[]", '{"doc_id": 42}', '{"doc_id": " "}'])
def test_export_rejects_metadata_without_document_id(tmp_path, metadata):
    directory = write_doc(tmp_path, "a", "A report")
    (directory / "doc.json").write_text(metadata, encoding="utf-8")
    with pytest.raises(ValueError, match="doc_id"):
        publishing.export_dataset(tmp_path)


def test_metadata_only_archive_exports_all_documents(tmp_path):
    write_doc(tmp_path, "a", None, description="Awaiting extraction")
    write_doc(tmp_path, "b", "", description="Scanned report")

    paths = publishing.export_dataset(tmp_path)

    docs = read_jsonl(paths[0])
    assert [doc["doc_id"] for doc in docs] == ["a", "b"]
    assert all(doc["text"] == "" for doc in docs)
    assert docs[0]["description"] == "Awaiting extraction"
    assert read_jsonl(paths[1]) == []


@pytest.mark.parametrize("invalid_metadata", [None, "{}", "broken json"])
def test_bad_archive_preserves_prior_exports(tmp_path, invalid_metadata):
    output = tmp_path / "exports"
    output.mkdir()
    for name in ("docs.jsonl", "chunks.jsonl"):
        (output / name).write_text("prior export", encoding="utf-8")
    if invalid_metadata is not None:
        write_doc(tmp_path, "a", "Valid first report")
        directory = write_doc(tmp_path, "z", None)
        (directory / "doc.json").write_text(invalid_metadata, encoding="utf-8")

    with pytest.raises(ValueError):
        publishing.export_dataset(tmp_path)

    assert (output / "docs.jsonl").read_text(encoding="utf-8") == "prior export"
    assert (output / "chunks.jsonl").read_text(encoding="utf-8") == "prior export"
    assert sorted(path.name for path in output.iterdir()) == ["chunks.jsonl", "docs.jsonl"]


def test_export_requires_existing_dataset_directory(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="directory"):
        publishing.export_dataset(missing)
    assert not missing.exists()


def test_export_requires_metadata(tmp_path):
    with pytest.raises(ValueError, match="No metadata"):
        publishing.export_dataset(tmp_path)
    assert not (tmp_path / "exports").exists()


def test_export_skips_whitespace_windows_and_preserves_original_chunk_indexes(tmp_path):
    write_doc(tmp_path, "trailing", "real report" + " " * 4000)
    write_doc(tmp_path, "middle", "real report" + " " * 4000 + "another report")

    paths = publishing.export_dataset(tmp_path)

    chunks = read_jsonl(paths[1])
    assert all(chunk["chunk_text"].strip() for chunk in chunks)
    assert [chunk["chunk_id"] for chunk in chunks if chunk["doc_id"] == "trailing"] == [
        "trailing-0000"
    ]
    middle = [chunk for chunk in chunks if chunk["doc_id"] == "middle"]
    assert [chunk["chunk_index"] for chunk in middle] == [0, 2]
    assert [chunk["chunk_id"] for chunk in middle] == ["middle-0000", "middle-0002"]


def test_export_includes_current_completed_analysis_result(tmp_path):
    text = "සිංහල report"
    directory = write_doc(tmp_path, "a", text)
    result = {
        "summary": "Summary",
        "report_date": "2026-09-13",
        "disaster_types": ["flood"],
        "locations": ["Colombo"],
        "impacts": [],
        "warnings": [],
    }
    envelope = {
        "status": "complete",
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "result": result,
        "provider": "local",
    }
    (directory / "analysis.json").write_text(json.dumps(envelope), encoding="utf-8")

    paths = publishing.export_dataset(tmp_path)

    assert read_jsonl(paths[0])[0]["analysis"] == result
    assert "analysis" not in read_jsonl(paths[1])[0]


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"summary": " "},
        {"summary": 123},
        {"locations": "Colombo"},
        {"warnings": [123]},
        {"report_date": "2026-02-30"},
        {"report_date": "20260913"},
    ],
)
def test_export_omits_invalid_result_with_matching_hash(tmp_path, invalid_fields):
    text = "Current report"
    directory = write_doc(tmp_path, "a", text)
    result = {
        "summary": "Summary",
        "report_date": None,
        "disaster_types": [],
        "locations": [],
        "impacts": [],
        "warnings": [],
        **invalid_fields,
    }
    envelope = {
        "status": "complete",
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "result": result,
    }
    (directory / "analysis.json").write_text(json.dumps(envelope), encoding="utf-8")

    paths = publishing.export_dataset(tmp_path)

    assert read_jsonl(paths[0])[0]["analysis"] is None
    assert read_jsonl(paths[0])[0]["text"] == text
    assert read_jsonl(paths[1])[0]["chunk_text"] == text


@pytest.mark.parametrize(
    "analysis",
    [
        {"status": "complete", "text_sha256": "stale", "result": {"summary": "old"}},
        {"status": "failed", "result": {"summary": "failed"}},
        {"status": "pending", "result": {}},
        {"status": "complete"},
        [],
        None,
        "malformed",
        b"\xff",
    ],
)
def test_export_omits_unusable_analysis_without_losing_source(tmp_path, analysis):
    text = "Current report"
    directory = write_doc(tmp_path, "a", text)
    if isinstance(analysis, dict) and "text_sha256" not in analysis:
        analysis["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path = directory / "analysis.json"
    if isinstance(analysis, bytes):
        path.write_bytes(analysis)
    elif isinstance(analysis, str):
        path.write_text(analysis, encoding="utf-8")
    else:
        path.write_text(json.dumps(analysis), encoding="utf-8")

    paths = publishing.export_dataset(tmp_path)

    assert read_jsonl(paths[0])[0]["text"] == text
    assert read_jsonl(paths[0])[0]["analysis"] is None
    assert read_jsonl(paths[1])[0]["chunk_text"] == text
