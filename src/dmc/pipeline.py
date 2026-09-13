"""Coordinate collection and processing; publication is an explicit CLI step."""

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

from dmc.client import Client, DeadlineExceeded
from dmc.parser import parse_page
from dmc.processing import process_pdf
from dmc.sources import Source
from dmc.storage import Storage, write_json
from dmc.summaries import build_summary

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    pages: int = 0
    discovered: int = 0
    processed: int = 0
    attempted: int = 0
    limited: bool = False
    errors: list[str] = field(default_factory=list)


def run_pipeline(
    source: Source,
    output_dir: Path,
    *,
    client=None,
    max_pages: int = 100,
    max_seconds: float = 300,
    max_documents: int | None = None,
    metadata_only: bool = False,
) -> RunResult:
    if (
        max_pages <= 0
        or not math.isfinite(max_seconds)
        or max_seconds <= 0
        or (max_documents is not None and max_documents <= 0)
    ):
        raise ValueError("Collection limits must be positive finite numbers")
    if client is None:
        with Client() as http:
            return run_pipeline(
                source,
                output_dir,
                client=http,
                max_pages=max_pages,
                max_seconds=max_seconds,
                max_documents=max_documents,
                metadata_only=metadata_only,
            )
    result = RunResult()
    store = Storage(output_dir, source.label)
    started = time.monotonic()
    if isinstance(client, Client):
        client.deadline = started + max_seconds
    seen = set()
    for index in range(max_pages):
        if time.monotonic() - started >= max_seconds:
            result.limited = True
            break
        url = source.page_url(index * 10)
        try:
            page = parse_page(client.get_text(url), url, source)
            result.pages += 1
            if not page.row_count:
                break
            if page.fingerprint in seen:
                raise ValueError(f"Repeated report page at {url}")
            seen.add(page.fingerprint)
            result.errors.extend(page.errors)
            for report in page.reports:
                store.save(report)
                result.discovered += 1
            log.info("Page %s: %s reports", index + 1, len(page.reports))
        except DeadlineExceeded:
            result.limited = True
            break
        except Exception as exc:
            result.errors.append(f"Collection failed: {exc}")
            break
    else:
        result.limited = True

    if not metadata_only:
        started = time.monotonic()
        if isinstance(client, Client):
            client.deadline = started + max_seconds
        for record, metadata in store.documents():
            status_path = metadata.with_name("processing.json")
            if status_path.is_file():
                try:
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                    if not isinstance(status, dict):
                        status = {}
                except (ValueError, OSError):
                    log.warning("Recovering invalid processing status: %s", status_path)
                    status = {}
                if (
                    status.get("status") in {"complete", "no_text"}
                    and metadata.with_name("doc.pdf").is_file()
                    and metadata.with_name("doc.txt").is_file()
                ):
                    continue
            if time.monotonic() - started >= max_seconds or (
                max_documents is not None and result.attempted >= max_documents
            ):
                result.limited = True
                break
            pdf = metadata.with_name("doc.pdf")
            result.attempted += 1
            try:
                if not pdf.is_file() or pdf.stat().st_size == 0:
                    client.download_pdf(record["url_pdf"], pdf)
                status = process_pdf(pdf)
                write_json(status_path, status)
                result.processed += 1
            except DeadlineExceeded:
                result.limited = True
                break
            except Exception as exc:
                write_json(status_path, {"status": "error", "error": str(exc)})
                result.errors.append(f"{record['doc_id']}: {exc}")

    write_json(
        store.directory / "run.json",
        {
            "pages": result.pages,
            "discovered": result.discovered,
            "processed": result.processed,
            "attempted": result.attempted,
            "limited": result.limited,
            "errors": result.errors,
        },
    )
    build_summary(store, source)
    return result
