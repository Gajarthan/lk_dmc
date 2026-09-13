"""Parse report listings without treating skipped rows as the end of history."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from dmc.models import Report
from dmc.sources import Source

SRI_LANKA_TIME = timezone(timedelta(hours=5, minutes=30))


class ParseError(ValueError):
    """The upstream listing does not have the expected structure."""


@dataclass
class Page:
    reports: list[Report] = field(default_factory=list)
    row_count: int = 0
    errors: list[str] = field(default_factory=list)
    fingerprint: str = ""


def parse_page(html: str, url: str, source: Source) -> Page:
    table = BeautifulSoup(html, "html.parser").find("table", class_="mtable")
    if table is None:
        raise ParseError(f"Report table missing at {url}")
    result = Page(fingerprint=hashlib.sha256(str(table).encode()).hexdigest())
    for index, row in enumerate(table.find_all("tr"), 1):
        cells = row.find_all("td")
        if "mhead" in (row.get("class") or []) or (not cells and row.find("th")):
            continue
        if not cells:
            continue
        result.row_count += 1
        try:
            if len(cells) != 4:
                raise ParseError(f"Expected 4 cells, found {len(cells)}")
            description, day, time = (cell.get_text().strip() for cell in cells[:3])
            anchor = cells[3].find("a")
            if anchor is None:
                continue
            href = anchor.get("href")
            if not isinstance(href, str) or not href.strip():
                raise ParseError("Download link has no href")
            pdf_url = urljoin(url, href.strip())
            parsed = urlsplit(pdf_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ParseError("Download URL must use HTTP or HTTPS")
            if parsed.path.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            if not parsed.path.lower().endswith(".pdf"):
                raise ParseError(f"Unsupported download link: {href}")
            moment = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M")
            description = re.sub(r"\s+", " ", description)
            slug = re.sub(r"[^a-zA-Z0-9\s]", "", description).strip().replace(" ", "-").lower()
            result.reports.append(
                Report(
                    doc_type=source.label,
                    num=f"{time.replace(':', '-')}-{slug}",
                    date_str=moment.date().isoformat(),
                    description=description,
                    url_metadata=url,
                    url_pdf=pdf_url,
                    time_str=moment.strftime("%H:%M"),
                    ut=int(moment.replace(tzinfo=SRI_LANKA_TIME).timestamp()),
                )
            )
        except (ValueError, TypeError) as exc:
            result.errors.append(f"{url} row {index}: {exc}")
    return result
