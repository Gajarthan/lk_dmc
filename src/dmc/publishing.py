"""Export document datasets to local JSONL files."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .opencode import validate_analysis


def _current_analysis(path: Path, text: str):
    """Include only completed analysis for the exported source text."""
    try:
        analysis = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        isinstance(analysis, dict)
        and analysis.get("status") == "complete"
        and analysis.get("text_sha256") == hashlib.sha256(text.encode("utf-8")).hexdigest()
    ):
        try:
            return validate_analysis(analysis.get("result"))
        except ValueError:
            return None
    return None


def _export_jsonl(dataset_dir: Path, output: Path) -> None:
    metadata_paths = sorted(dataset_dir.rglob("doc.json"))
    if not metadata_paths:
        raise ValueError(f"No metadata records found in {dataset_dir}")
    output.mkdir(parents=True, exist_ok=True)
    # Keep only one document and one chunk in memory. Stage both exports before
    # replacement so invalid historical metadata cannot truncate prior exports.
    with tempfile.TemporaryDirectory(prefix=".export-", dir=output) as temporary:
        staging = Path(temporary)
        with (
            (staging / "docs.jsonl").open("w", encoding="utf-8", newline="\n") as docs,
            (staging / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as chunks,
        ):
            for metadata_path in metadata_paths:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if (
                    not isinstance(metadata, dict)
                    or not isinstance(metadata.get("doc_id"), str)
                    or not metadata["doc_id"].strip()
                ):
                    raise ValueError(f"Missing or invalid doc_id in {metadata_path}")
                text_path = metadata_path.with_name("doc.txt")
                text = text_path.read_text(encoding="utf-8") if text_path.is_file() else ""
                metadata.setdefault("doc_type", dataset_dir.name)
                language = metadata.get("language") or metadata.get("lang") or "und"
                doc = {
                    **metadata,
                    "language": language,
                    "text": text,
                    "analysis": _current_analysis(metadata_path.with_name("analysis.json"), text),
                }
                docs.write(json.dumps(doc, ensure_ascii=False) + "\n")
                if not text.strip():
                    continue
                for index, start in enumerate(range(0, len(text), 1800)):
                    chunk_text = text[start : start + 2000]
                    if not chunk_text.strip():
                        continue
                    encoded = chunk_text.encode("utf-8")
                    chunk = {
                        **metadata,
                        "chunk_id": f"{metadata['doc_id']}-{index:04d}",
                        "chunk_index": index,
                        "language": language,
                        "md5": hashlib.md5(encoded, usedforsecurity=False).hexdigest(),
                        "chunk_size_bytes": len(encoded),
                        "chunk_text": chunk_text,
                    }
                    chunks.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    if start + 2000 >= len(text):
                        break
        for kind in ("docs", "chunks"):
            os.replace(staging / f"{kind}.jsonl", output / f"{kind}.jsonl")


def export_dataset(dataset_dir: Path) -> list[Path]:
    """Export every metadata record and chunks for nonempty extracted text.

    Missing text is exported as an empty string. Chunks contain at most 2,000
    characters with 200-character overlap. Existing metadata fields are retained;
    malformed source records are not suppressed. Analysis is included only when
    completed for the current text. Both exports are staged before replacement.
    """
    if not dataset_dir.is_dir():
        raise ValueError(f"Dataset directory does not exist: {dataset_dir}")

    output = dataset_dir / "exports"
    _export_jsonl(dataset_dir, output)
    return [output / "docs.jsonl", output / "chunks.jsonl"]
