import pytest

from app.services.pdf_service import (
    PDFProcessingError,
    clean_text,
    count_words,
    extract_pdf,
)


def test_clean_text_fixes_common_extraction_problems():
    raw = "Ex-\nample  text with \ufb01ne   ligatures\r\n\r\n\r\n\r\nnext   paragraph\x00"
    cleaned = clean_text(raw)
    assert "Example" in cleaned  # hyphenated line break re-joined
    assert "fine" in cleaned  # ligature normalised
    assert "\x00" not in cleaned  # control character removed
    assert "\n\n\n" not in cleaned  # blank lines collapsed
    assert "  " not in cleaned  # runs of spaces collapsed


def test_count_words():
    assert count_words("Hello world 123") == 3
    assert count_words("") == 0


def test_extract_pdf_reads_pages_and_text(tmp_path, make_pdf):
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_pdf(pages=3))
    extracted = extract_pdf(path)
    assert extracted.page_count == 3
    assert len(extracted.pages) == 3
    assert "Workers process queued jobs" in extracted.pages[0]


def test_extract_pdf_rejects_corrupted_file(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4 this is not a real pdf")
    with pytest.raises(PDFProcessingError):
        extract_pdf(path)


def test_extract_pdf_rejects_missing_file(tmp_path):
    with pytest.raises(PDFProcessingError):
        extract_pdf(tmp_path / "missing.pdf")