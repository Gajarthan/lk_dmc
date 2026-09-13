"""Atomic local storage with historical directories and non-destructive resume."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from dmc.models import Report


def atomic_write(path: Path, content: str | bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path: Path, value) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class Storage:
    def __init__(self, root: Path, label: str):
        if not re.fullmatch(r"[a-z0-9_]+", label):
            raise ValueError("Invalid dataset label")
        self.directory = Path(root) / label

    def save(self, report: Report) -> Path:
        if report.doc_type != self.directory.name:
            raise ValueError("Report belongs to another dataset")
        year = report.date_str[:4]
        parent = self.directory / f"{year[:3]}0s" / year
        path = parent / report.doc_id / "doc.json"
        record = report.to_dict()
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("url_pdf") == report.url_pdf:
                return path
            suffix = hashlib.sha256(report.url_pdf.encode()).hexdigest()[:12]
            record["doc_id"] += f"-{suffix}"
            path = parent / record["doc_id"] / "doc.json"
            if path.exists():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("url_pdf") != report.url_pdf:
                    raise ValueError(f"Document ID collision at {path}")
                return path
        write_json(path, record)
        return path

    def documents(self):
        for path in sorted(self.directory.rglob("doc.json"), reverse=True):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                required = ("doc_id", "doc_type", "date_str", "url_pdf")
                if not isinstance(record, dict) or not all(record.get(key) for key in required):
                    raise ValueError("Missing required metadata fields")
                if record["doc_type"] != self.directory.name:
                    raise ValueError("Metadata belongs to another dataset")
            except (ValueError, OSError) as exc:
                raise ValueError(f"Invalid metadata at {path}: {exc}") from exc
            yield record, path
