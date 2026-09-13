"""Export document datasets and upload them to a configured Hugging Face namespace."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from huggingface_hub import HfApi


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
                doc = {**metadata, "language": language, "text": text}
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


def publish_dataset(dataset_dir: Path, namespace: str, token: str) -> list[str]:
    """Publish every metadata record and chunks for nonempty extracted text.

    Missing text is exported as an empty string. Chunks contain at most 2,000
    characters with 200-character overlap. Existing metadata fields are retained;
    malformed records and upload errors are not suppressed.
    """
    if not namespace or not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9_-]{0,94}[A-Za-z0-9])?", namespace.strip()
    ):
        raise ValueError("The Hugging Face namespace must be one account or organization name")
    if not token or not token.strip():
        raise ValueError("A Hugging Face token is required")
    if not dataset_dir.is_dir():
        raise ValueError(f"Dataset directory does not exist: {dataset_dir}")

    output = dataset_dir / "hugging_face_data"
    _export_jsonl(dataset_dir, output)

    api = HfApi(token=token)
    repos = []
    for kind in ("docs", "chunks"):
        repo_id = f"{namespace.strip()}/{dataset_dir.name.replace('_', '-')}-{kind}"
        api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
        api.upload_file(
            path_or_fileobj=str(output / f"{kind}.jsonl"),
            path_in_repo=f"{kind}.jsonl",
            repo_id=repo_id,
            repo_type="dataset",
        )
        card = (
            "---\nconfigs:\n- config_name: default\n  data_files:\n"
            f"  - split: train\n    path: {kind}.jsonl\n---\n\n"
            f"# {dataset_dir.name.replace('_', ' ')}: {kind}\n\n"
            "Sri Lankan Disaster Management Centre reports. Text is extracted from "
            "PDF text layers; scanned pages require separate OCR.\n"
            "The documents dataset retains every metadata record, with an empty string "
            "when extracted text is unavailable. Chunks include only nonempty text.\n"
        )
        api.upload_file(
            path_or_fileobj=card.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
        )
        repos.append(repo_id)
    return repos
