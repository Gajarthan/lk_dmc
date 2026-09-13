"""Portable report metadata, including the historical document ID format."""

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class Report:
    doc_type: str
    num: str
    date_str: str
    description: str
    url_metadata: str
    url_pdf: str
    time_str: str
    ut: int
    lang: str = "und"

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9_]+", self.doc_type):
            raise ValueError("Invalid dataset label")
        date.fromisoformat(self.date_str)

    @property
    def doc_id(self) -> str:
        short = self.num
        if len(short) >= 32:
            digest = hashlib.md5(short.encode(), usedforsecurity=False).hexdigest()[:8]
            short = f"{short[:23]}-{digest}"
        return re.sub(r"[^a-zA-Z0-9-]", "-", f"{self.date_str}-{short}")

    def to_dict(self) -> dict:
        return {"doc_id": self.doc_id, **asdict(self)}
