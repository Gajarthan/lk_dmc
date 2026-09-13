"""Bounded, resumable OpenCode analysis of locally extracted report text."""

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dmc.opencode import SCHEMA_VERSION, OpenCodeClient, validate_analysis
from dmc.storage import write_json


@dataclass
class AnalysisResult:
    analyzed: int = 0
    skipped: int = 0
    attempted: int = 0
    limited: bool = False
    errors: list[str] = field(default_factory=list)


def _retry_order(metadata_path: Path):
    """New work precedes errors; rotate errors by last attempt to prevent starvation."""
    try:
        status = json.loads(metadata_path.with_name("analysis.json").read_text(encoding="utf-8"))
        if isinstance(status, dict) and status.get("status") == "error":
            attempted_at = status.get("attempted_at")
            return (1, attempted_at if isinstance(attempted_at, str) else "", str(metadata_path))
    except (OSError, ValueError):
        pass
    return (0, "", str(metadata_path))


def analyze_dataset(
    dataset_dir: Path,
    *,
    client: OpenCodeClient,
    max_documents: int = 10,
    max_seconds: float = 300,
    max_characters: int = 40000,
    force: bool = False,
) -> AnalysisResult:
    if (
        max_documents <= 0
        or max_characters <= 0
        or not math.isfinite(max_seconds)
        or max_seconds <= 0
    ):
        raise ValueError("Analysis limits must be positive finite numbers")
    if not dataset_dir.is_dir():
        raise ValueError("Dataset directory does not exist")
    result = AnalysisResult()
    deadline = time.monotonic() + max_seconds
    config_hash = hashlib.sha256(
        json.dumps(
            {
                "endpoint": client.config.base_url,
                "model": client.config.model,
                "schema_version": SCHEMA_VERSION,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    for metadata_path in sorted(dataset_dir.rglob("doc.json"), key=_retry_order):
        if time.monotonic() >= deadline or result.attempted >= max_documents:
            result.limited = True
            break
        status_path = metadata_path.with_name("analysis.json")
        record = {"status": "error", "schema_version": SCHEMA_VERSION, "config_sha256": config_hash}
        record["attempted_at"] = datetime.now(UTC).isoformat()
        doc_id = metadata_path.parent.name
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict) or not isinstance(metadata.get("doc_id"), str):
                raise ValueError("Invalid document metadata")
            doc_id = metadata["doc_id"]
            text_path = metadata_path.with_name("doc.txt")
            text = text_path.read_text(encoding="utf-8") if text_path.is_file() else ""
            if not text.strip():
                result.skipped += 1
                continue
            record["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if not force and status_path.is_file():
                try:
                    previous = json.loads(status_path.read_text(encoding="utf-8"))
                    if (
                        isinstance(previous, dict)
                        and previous.get("status") == "complete"
                        and previous.get("text_sha256") == record["text_sha256"]
                        and previous.get("config_sha256") == config_hash
                    ):
                        validate_analysis(previous.get("result"))
                        result.skipped += 1
                        continue
                except (ValueError, OSError):
                    pass
            result.attempted += 1
            if len(text) > max_characters:
                raise ValueError(
                    "Report exceeds analysis character limit; increase --max-characters"
                )
            response = client.analyze(text, doc_id, timeout=deadline - time.monotonic())
            record.update(response)
            record["result"] = validate_analysis(response["result"])
            record["status"] = "complete"
            record["analyzed_at"] = datetime.now(UTC).isoformat()
            write_json(status_path, record)
            result.analyzed += 1
        except (ValueError, OSError) as exc:
            # Client errors deliberately exclude credentials and raw server response bodies.
            record["status"] = "error"
            record.pop("result", None)
            record["error"] = str(exc)
            write_json(status_path, record)
            result.errors.append(f"{doc_id}: {exc}")
    write_json(dataset_dir / "analysis-run.json", asdict(result))
    return result
