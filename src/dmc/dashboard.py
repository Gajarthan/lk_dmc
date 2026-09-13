"""Render a GitHub-native dashboard from published dataset summaries."""

import html
import re
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

from dmc.sources import SOURCES

COUNT_FIELDS = (
    "n_docs",
    "n_docs_with_pdfs",
    "n_docs_with_text",
    "n_docs_with_analysis",
    "n_docs_with_tabular",
    "dataset_size",
)


def _cell(value) -> str:
    text = html.escape(" ".join(str(value).split()), quote=False)
    return re.sub(r"([\\`*\[\]_|])", r"\\\1", text)


def _count(summary, field):
    value = summary.get(field)
    if value is None and summary["n_docs"] == 0:
        return 0
    return value


def _number(value) -> str:
    return f"{value:,}" if value is not None else "Not reported"


def _timestamp(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    except (ValueError, TypeError):
        pass
    return None


def _pdf_link(value) -> str:
    try:
        url = urlsplit(value)
        if url.scheme in {"http", "https"} and url.hostname and not url.username:
            return f"[PDF]({quote(value, safe=':/?&=%#@+,-._~')})"
    except (ValueError, TypeError):
        pass
    return "Unavailable"


def render_dashboard(summaries: list[dict], repository: str | None = None) -> str:
    if not summaries:
        raise ValueError("No dataset summaries available; README was not changed")
    if repository and not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Repository must be owner/name")
    indexed = {}
    for summary in summaries:
        if not isinstance(summary, dict):
            raise ValueError("Invalid dataset summary")
        label = summary.get("doc_class_label")
        if label not in SOURCES or label in indexed:
            raise ValueError("Unknown or duplicate dataset summary")
        for field in COUNT_FIELDS:
            value = summary.get(field)
            if (field == "n_docs" or value is not None) and (type(value) is not int or value < 0):
                raise ValueError(f"Invalid {field} in dataset summary")
        if not isinstance(summary.get("latest_reports", []), list):
            raise ValueError("Invalid recent reports in dataset summary")
        indexed[label] = summary

    def total(field):
        values = [_count(s, field) for s in summaries]
        return sum(values) if all(v is not None for v in values) else None

    lines = [
        "### Coverage",
        "",
        "| Reports | Original PDFs | Extracted text | AI analyzed | With tables |",
        "|:---:|:---:|:---:|:---:|:---:|",
        "| " + " | ".join(f"**{_number(total(f))}**" for f in COUNT_FIELDS[:-1]) + " |",
        "",
    ]
    updates = [date for s in summaries if (date := _timestamp(s.get("time_updated")))]
    stamp = max(updates).strftime("%Y-%m-%d %H:%M UTC") if updates else "Not reported"
    size = total("dataset_size")
    if size is None:
        size_text = "Not reported"
    elif size < 1024:
        size_text = f"{size:,} B"
    elif size < 1024 * 1024:
        size_text = f"{size / 1024:.1f} KiB"
    else:
        size_text = f"{size / (1024 * 1024):.1f} MiB"
    lines += [
        f"**Report files:** {size_text} · **Latest summary:** {stamp} · "
        f"**Sources reporting:** {len(indexed)}/{len(SOURCES)}",
        "",
    ]
    if len(indexed) < len(SOURCES):
        lines += ["Totals cover available summaries only; missing sources are marked below.", ""]
    if total("n_docs") == 0:
        action = (
            f"[Start collection](https://github.com/{repository}/actions/workflows/pipeline.yml)"
            if repository
            else "Run `dmc scrape DATASET --export`"
        )
        lines += [
            f"**No reports have been published yet.** {action} to populate the archive.",
            "",
        ]
    lines += [
        "### Dataset monitor",
        "",
        "| Dataset | Reports | PDFs | Text | AI | Newest report | Collection |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for label, source in SOURCES.items():
        title = source.title
        if repository:
            title = f"[{title}](https://github.com/{repository}/tree/data_{label}/data/{label})"
        summary = indexed.get(label)
        if summary is None:
            lines.append(f"| {title} | — | — | — | — | — | Not available |")
            continue
        counts = " | ".join(_number(_count(summary, f)) for f in COUNT_FIELDS[:4])
        state = summary.get("collection_status") or "Not reported"
        if summary["n_docs"] == 0 and state != "Needs attention":
            state = "Waiting for reports"
        lines.append(
            f"| {title} | {counts} | {_cell(summary.get('date_str_max') or '—')} | {_cell(state)} |"
        )
    lines += [
        "",
        "Counts describe archived files. AI counts include only validated results "
        "matching the current source text. **Bounded run** means a collection limit was "
        "reached; it does not mean the full source history is archived.",
        "",
        "### Recent source reports",
        "",
    ]
    recent = [
        (label, report)
        for label, s in indexed.items()
        for report in s.get("latest_reports", [])
        if isinstance(report, dict)
    ]
    recent.sort(
        key=lambda pair: (pair[1].get("date_str") or "", pair[1].get("time_str") or ""),
        reverse=True,
    )
    if recent:
        lines += ["| Report date | Dataset | Report | Source | AI |", "|---|---|---|---|---|"]
        for label, report in recent[:8]:
            description = report.get("description") or report.get("doc_id") or "Untitled report"
            lines.append(
                f"| {_cell(report.get('date_str') or '—')} | {SOURCES[label].title} | "
                f"{_cell(description)} | "
                f"{_pdf_link(report.get('url_pdf'))} | "
                f"{'Analyzed' if report.get('analyzed') is True else 'Pending'} |"
            )
    else:
        lines.append("Recent report links will appear after a collection run publishes them.")
    lines += [
        "",
        "This section refreshes after pipeline completion and on the scheduled dashboard "
        "refresh. Workflow badges show the latest workflow result, not real-time service health.",
    ]
    return "\n".join(lines)
