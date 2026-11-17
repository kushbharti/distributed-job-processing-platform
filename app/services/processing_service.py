import os
import uuid
from collections.abc import Callable
from pathlib import Path

from app.core.config import settings
from app.services import pdf_service, report_service, summary_service
from app.services.pdf_service import NoTextFoundError, PDFProcessingError

ProgressCallback = Callable[[str, int], None]


def _unique_tmp(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")


def run_pipeline(
    *,
    source_relative_path: str,
    original_filename: str,
    output_key: str,
    on_progress: ProgressCallback,
) -> dict:
    source = (settings.upload_path / source_relative_path).resolve()
    if not source.is_relative_to(settings.upload_path):
        raise PDFProcessingError("Invalid source path")

    on_progress("Validating document", 5)
    on_progress("Reading metadata", 15)
    extracted = pdf_service.extract_pdf(source)

    on_progress("Extracting text", 40)
    text = pdf_service.clean_text("\n\n".join(extracted.pages))
    words = pdf_service.count_words(text)
    if words == 0:
        raise NoTextFoundError(
            "No extractable text found (the PDF may be a scanned image; OCR is not supported)"
        )

    on_progress("Cleaning text", 55)
    stats = {
        "pages": extracted.page_count,
        "words": words,
        "characters": len(text),
        "reading_minutes": max(1, round(words / 200)),
    }

    on_progress("Generating summary", 75)
    summary = summary_service.summarize(text)
    keywords = summary_service.top_keywords(text)

    on_progress("Generating report", 90)
    text_rel = Path("extracted") / f"{output_key}.txt"
    report_rel = Path("reports") / f"{output_key}.pdf"
    text_abs = settings.upload_path / text_rel
    report_abs = settings.upload_path / report_rel

    text_tmp = _unique_tmp(text_abs)
    report_tmp = _unique_tmp(report_abs)
    try:
        report_service.build_report(
            report_tmp,
            filename=original_filename,
            stats=stats,
            metadata=extracted.metadata,
            keywords=keywords,
            summary=summary,
        )
        on_progress("Saving results", 95)
        text_tmp.write_text(text, encoding="utf-8")
        # Atomic rename: readers never see a half-written file.
        os.replace(text_tmp, text_abs)
        os.replace(report_tmp, report_abs)
    finally:
        text_tmp.unlink(missing_ok=True)
        report_tmp.unlink(missing_ok=True)

    on_progress("Completed", 100)
    return {
        "summary": summary,
        "keywords": keywords,
        "metadata": extracted.metadata,
        "stats": stats,
        "extracted_text_path": text_rel.as_posix(),
        "report_path": report_rel.as_posix(),
    }