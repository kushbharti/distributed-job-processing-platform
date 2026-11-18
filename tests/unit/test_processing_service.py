import pytest

from app.core.config import settings
from app.services.pdf_service import NoTextFoundError, PDFProcessingError
from app.services.processing_service import run_pipeline


def _stage_source(content: bytes) -> str:
    path = settings.upload_path / "documents" / "src.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return "documents/src.pdf"


def _run(source: str, key: str = "job-1", progress=None):
    return run_pipeline(
        source_relative_path=source,
        original_filename="src.pdf",
        output_key=key,
        on_progress=(lambda stage, pct: progress.append(pct)) if progress is not None else (lambda s, p: None),
    )


def test_pipeline_creates_outputs_and_reports_monotonic_progress(make_pdf):
    progress: list[int] = []
    output = _run(_stage_source(make_pdf(pages=2)), progress=progress)

    assert progress == sorted(progress)
    assert progress[-1] == 100
    assert output["stats"]["pages"] == 2
    assert output["summary"]
    assert (settings.upload_path / output["extracted_text_path"]).is_file()
    report = settings.upload_path / output["report_path"]
    assert report.read_bytes().startswith(b"%PDF")
    assert not list(settings.upload_path.rglob("*.tmp"))  # no temp files left behind


def test_pipeline_is_idempotent(make_pdf):
    source = _stage_source(make_pdf())
    _run(source)
    files_after_first = sorted(p.name for p in settings.upload_path.rglob("*") if p.is_file())
    _run(source)
    files_after_second = sorted(p.name for p in settings.upload_path.rglob("*") if p.is_file())
    assert files_after_first == files_after_second


def test_pipeline_rejects_pdf_without_text(make_pdf):
    with pytest.raises(NoTextFoundError):
        _run(_stage_source(make_pdf(pages=1, text=None)))


def test_pipeline_rejects_paths_outside_the_upload_folder():
    with pytest.raises(PDFProcessingError):
        _run("../outside.pdf")