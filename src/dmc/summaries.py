"""Build local dataset indexes and Markdown without personal branding."""

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path

from dmc.dashboard import render_dashboard
from dmc.publishing import _current_analysis
from dmc.sources import SOURCES, Source
from dmc.storage import Storage, atomic_write, write_json

START = "<!-- DATASETS:START -->"
END = "<!-- DATASETS:END -->"


def build_summary(store: Storage, source: Source) -> dict:
    documents = list(store.documents())
    records = [record for record, _ in documents]
    dates = [record["date_str"] for record in records]
    analyzed = set()
    for record, path in documents:
        text_path = path.with_name("doc.txt")
        if path.with_name("analysis.json").is_file() and text_path.is_file():
            text = text_path.read_text(encoding="utf-8")
            if (
                text.strip()
                and _current_analysis(path.with_name("analysis.json"), text) is not None
            ):
                analyzed.add(record["doc_id"])
    collection_status = "Not reported"
    try:
        run = json.loads((store.directory / "run.json").read_text(encoding="utf-8"))
        if (
            isinstance(run, dict)
            and isinstance(run.get("errors"), list)
            and isinstance(run.get("limited"), bool)
        ):
            collection_status = (
                "Needs attention"
                if run.get("errors")
                else "Bounded run"
                if run.get("limited")
                else "Complete"
            )
    except (OSError, ValueError):
        pass
    summary = {
        "doc_class_label": source.label,
        "doc_class_description": source.description,
        "time_updated": datetime.now(UTC).isoformat(),
        "n_docs": len(records),
        "n_docs_with_analysis": len(analyzed),
        "collection_status": collection_status,
        "latest_reports": [
            {
                **{
                    key: record.get(key)
                    for key in ("doc_id", "description", "date_str", "time_str", "url_pdf")
                },
                "analyzed": record["doc_id"] in analyzed,
            }
            for record in sorted(
                records, key=lambda r: (r["date_str"], r.get("time_str", "")), reverse=True
            )[:8]
        ],
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


def build_global_readme(
    path: Path,
    summaries: list[dict],
    *,
    repository: str | None = None,
) -> None:
    section = START + "\n\n" + render_dashboard(summaries, repository) + "\n\n" + END
    existing = path.read_text(encoding="utf-8") if path.exists() else "# DMC datasets\n"
    if START in existing or END in existing:
        if (
            existing.count(START) != 1
            or existing.count(END) != 1
            or existing.index(START) > existing.index(END)
        ):
            raise ValueError("Malformed dashboard markers; README was not changed")
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
