"""Build local dataset indexes and Markdown without personal branding."""

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path

from dmc.sources import SOURCES, Source
from dmc.storage import Storage, atomic_write, write_json

START = "<!-- DATASETS:START -->"
END = "<!-- DATASETS:END -->"


def build_summary(store: Storage, source: Source) -> dict:
    documents = list(store.documents())
    records = [record for record, _ in documents]
    dates = [record["date_str"] for record in records]
    summary = {
        "doc_class_label": source.label,
        "doc_class_description": source.description,
        "time_updated": datetime.now(UTC).isoformat(),
        "n_docs": len(records),
        "n_docs_with_pdfs": sum(path.with_name("doc.pdf").is_file() for _, path in documents),
        "n_docs_with_text": sum(
            path.with_name("doc.txt").is_file() and path.with_name("doc.txt").stat().st_size > 0
            for _, path in documents
        ),
        "n_docs_with_tabular": sum(
            any((path.parent / "tabular").glob("*.csv")) for _, path in documents
        ),
        "date_str_min": min(dates, default=None),
        "date_str_max": max(dates, default=None),
        "langs": sorted({record.get("lang", "und") for record in records}),
        "dataset_size": sum(
            path.stat().st_size
            for _, metadata in documents
            for path in metadata.parent.rglob("*")
            if path.is_file()
        ),
    }
    write_json(store.directory / "summary.json", summary)
    fields = sorted({key for record in records for key in record})
    for count, suffix in (
        (None, "all"),
        (100, "last100"),
        (1000, "last1000"),
        (10000, "last10000"),
    ):
        if count and count > len(records):
            continue
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields, delimiter="\t")
        if fields:
            writer.writeheader()
            writer.writerows(records[:count] if count else records)
        atomic_write(store.directory / f"docs_{suffix}.tsv", output.getvalue())
    atomic_write(
        store.directory / "README.md",
        (
            f"# {source.title}\n\n{source.description}\n\n"
            f"Documents: **{len(records):,}**\n\n"
            f"Date range: {summary['date_str_min'] or 'none'} to "
            f"{summary['date_str_max'] or 'none'}\n\n"
            "Source: [Disaster Management Centre](https://www.dmc.gov.lk).\n\n"
            "See `summary.json` and `docs_all.tsv` for the generated index.\n"
        ),
    )
    return summary


def build_global_readme(path: Path, summaries: list[dict]) -> None:
    if not summaries:
        raise ValueError("No dataset summaries available; README was not changed")
    rows = ["| Dataset | Documents | Date range |", "|---|---:|---|"]
    for summary in summaries:
        label = summary["doc_class_label"]
        if label not in SOURCES:
            raise ValueError(f"Unknown dataset summary: {label}")
        rows.append(
            f"| {SOURCES[label].title} | {summary['n_docs']:,} | "
            f"{summary.get('date_str_min') or '—'} – "
            f"{summary.get('date_str_max') or '—'} |"
        )
    section = START + "\n\n" + "\n".join(rows) + "\n\n" + END
    existing = path.read_text(encoding="utf-8") if path.exists() else "# DMC datasets\n"
    if START in existing and END in existing:
        before, rest = existing.split(START, 1)
        _, after = rest.split(END, 1)
        content = before + section + after
    else:
        content = existing.rstrip() + "\n\n" + section + "\n"
    atomic_write(path, content)


def load_local_summaries(root: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for label in SOURCES
        if (path := root / label / "summary.json").is_file()
    ]
