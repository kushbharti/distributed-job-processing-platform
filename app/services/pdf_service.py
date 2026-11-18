import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf


class PDFProcessingError(Exception):
    """Permanent failure: running the same file again will not help."""


class NoTextFoundError(PDFProcessingError):
    pass


@dataclass
class ExtractedPDF:
    page_count: int
    metadata: dict[str, str]
    pages: list[str]


_METADATA_KEYS = (
    "title", "author", "subject", "keywords",
    "creator", "producer", "creationDate", "modDate",
)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def extract_pdf(path: Path) -> ExtractedPDF:
    if not path.is_file():
        raise PDFProcessingError("Source file is missing")
    try:
        with pymupdf.open(stream=path.read_bytes(), filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise PDFProcessingError("Password-protected PDFs are not supported")
            if pdf.page_count == 0:
                raise PDFProcessingError("PDF has no pages")

            raw = pdf.metadata or {}
            metadata = {
                key: str(raw[key]).strip()
                for key in _METADATA_KEYS
                if raw.get(key) and str(raw[key]).strip()
            }
            pages = [page.get_text("text", sort=True) for page in pdf]
            page_count = pdf.page_count
    except PDFProcessingError:
        raise
    except Exception as exc:
        raise PDFProcessingError("PDF is corrupted or unreadable") from exc

    return ExtractedPDF(page_count=page_count, metadata=metadata, pages=pages)


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)          # ligatures like "ﬁ" become "fi"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)        # re-join words hyphenated at line ends
    text = re.sub(r"[ \t]+", " ", text)                 # collapse runs of spaces
    text = re.sub(r" *\n *", "\n", text)                # trim spaces around line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)              # at most one blank line
    return text.strip()


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))