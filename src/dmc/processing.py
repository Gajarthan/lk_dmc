"""Extract the text layer and ruled tables from downloaded PDFs; no OCR is performed."""

import csv
import io
from pathlib import Path

import pdfplumber

from dmc.storage import atomic_write, write_json


def process_pdf(pdf_path: Path) -> dict:
    """Write page text and tables beside a PDF, replacing each output atomically.

    Page and table numbers are one-based. Extraction finishes before any output
    is replaced, so malformed PDFs leave previous extraction files intact.
    """
    blocks = []
    tables = []
    pages_without_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            blocks.append({"page": page.page_number, "text": text})
            if not text:
                pages_without_text.append(page.page_number)
            for index, table in enumerate(page.extract_tables(), 1):
                buffer = io.StringIO(newline="")
                csv.writer(buffer).writerows(table)
                tables.append((f"table-{page.page_number}-{index}.csv", buffer.getvalue()))
            page.close()

    directory = pdf_path.parent
    atomic_write(directory / "doc.txt", "\n\n".join(b["text"] for b in blocks).strip())
    write_json(directory / "blocks.json", blocks)
    for filename, content in tables:
        atomic_write(directory / "tabular" / filename, content)
    return {
        "status": "complete" if any(b["text"] for b in blocks) else "no_text",
        "pages": len(blocks),
        "pages_without_text": pages_without_text,
        "tables": len(tables),
    }
