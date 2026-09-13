import csv
import json
from pathlib import Path

import pytest


def make_pdf(path: Path, *, blank: bool = False) -> None:
    """Build a real one-page PDF with a ruled table using only standard library bytes."""
    stream = (
        b""
        if blank
        else (
            b"BT /F1 12 Tf 50 740 Td (Disaster report) Tj ET\n"
            b"50 600 m 250 600 l 250 680 l 50 680 l h S\n"
            b"150 600 m 150 680 l S 50 640 m 250 640 l S\n"
            b"BT /F1 12 Tf 60 655 Td (District) Tj ET\n"
            b"BT /F1 12 Tf 160 655 Td (People) Tj ET\n"
            b"BT /F1 12 Tf 60 615 Td (Colombo) Tj ET\n"
            b"BT /F1 12 Tf 160 615 Td (42) Tj ET\n"
        )
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += str(number).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    startxref = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
    pdf += str(startxref).encode() + b"\n%%EOF\n"
    path.write_bytes(pdf)


def test_process_pdf_extracts_real_text_and_table_without_removing_legacy_files(tmp_path):
    from dmc.processing import process_pdf

    pdf = tmp_path / "doc.pdf"
    make_pdf(pdf)
    legacy = tmp_path / "legacy.json"
    legacy.write_text("keep", encoding="utf-8")

    result = process_pdf(pdf)

    assert result == {"status": "complete", "pages": 1, "pages_without_text": [], "tables": 1}
    text = (tmp_path / "doc.txt").read_text(encoding="utf-8")
    assert "Disaster report" in text
    assert "Colombo" in text
    assert json.loads((tmp_path / "blocks.json").read_text(encoding="utf-8")) == [
        {"page": 1, "text": text.strip()}
    ]
    with (tmp_path / "tabular" / "table-1-1.csv").open(newline="", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [["District", "People"], ["Colombo", "42"]]
    assert legacy.read_text(encoding="utf-8") == "keep"


def test_process_pdf_marks_no_text_without_claiming_ocr(tmp_path):
    from dmc.processing import process_pdf

    pdf = tmp_path / "doc.pdf"
    make_pdf(pdf, blank=True)
    assert process_pdf(pdf) == {
        "status": "no_text",
        "pages": 1,
        "pages_without_text": [1],
        "tables": 0,
    }
    assert (tmp_path / "doc.txt").read_text(encoding="utf-8") == ""


def test_invalid_pdf_propagates_error_without_overwriting_existing_output(tmp_path):
    from dmc.processing import process_pdf

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"not a PDF")
    output = tmp_path / "doc.txt"
    output.write_text("existing text", encoding="utf-8")
    with pytest.raises(Exception):
        process_pdf(pdf)
    assert output.read_text(encoding="utf-8") == "existing text"
