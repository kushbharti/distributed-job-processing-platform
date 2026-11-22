import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.http_headers import SecurityHeadersMiddleware

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "app" / "static"
JS_FILES = sorted((STATIC / "js").rglob("*.js"))


def name_of(path: Path) -> str:
    return path.relative_to(STATIC).as_posix()


# ---- Headers ----


def test_site_pages_get_a_strict_content_security_policy(client):
    for path in ("/", "/static/js/main.js"):
        policy = client.get(path).headers["content-security-policy"]
        assert "script-src 'self'" in policy
        assert "'unsafe-inline'" not in policy and "'unsafe-eval'" not in policy
        assert "frame-ancestors 'none'" in policy


def test_swagger_docs_are_not_restricted_by_the_site_policy(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_api_responses_are_never_cached(client):
    response = client.get("/api/v1/health")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in response.headers


def test_the_page_and_scripts_are_revalidated(client):
    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/static/js/main.js").headers["cache-control"] == "no-cache"


def test_hsts_is_only_sent_in_production():
    for production in (True, False):
        sub_app = FastAPI()

        @sub_app.get("/")
        def home():
            return {}

        sub_app.add_middleware(SecurityHeadersMiddleware, production=production)
        with TestClient(sub_app) as test_client:
            sent = "strict-transport-security" in test_client.get("/").headers
        assert sent is production


# ---- 404 handling ----


def test_unknown_pages_get_an_html_404_for_browsers(client):
    response = client.get("/nope", headers={"accept": "text/html"})
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Page not found" in response.text
    assert "content-security-policy" in response.headers


def test_api_paths_and_non_browser_clients_still_get_json(client):
    assert client.get("/api/v1/nope", headers={"accept": "text/html"}).json() == {"detail": "Not Found"}
    assert client.get("/nope").json() == {"detail": "Not Found"}  # the test client sends Accept: */*


# ---- Static site structure ----

IMPORT_RE = re.compile(r"""(?:\bfrom\s+|\bimport\s*\(\s*)["']([^"']+)["']""")
UNSAFE_RE = re.compile(
    r"\binnerHTML\b|\bouterHTML\b|\binsertAdjacentHTML\b|\bdocument\.write\b|\beval\(|\bnew Function\("
)


@pytest.mark.parametrize("path", JS_FILES, ids=name_of)
def test_every_import_resolves_to_a_file(path):
    for target in IMPORT_RE.findall(path.read_text(encoding="utf-8")):
        assert target.startswith("."), f"{name_of(path)} imports {target!r}; there is no bundler to resolve it"
        assert (path.parent / target).resolve().is_file(), f"{name_of(path)} imports a missing file: {target}"


@pytest.mark.parametrize("path", JS_FILES, ids=name_of)
def test_scripts_never_turn_strings_into_markup_or_code(path):
    match = UNSAFE_RE.search(path.read_text(encoding="utf-8"))
    assert match is None, f"{name_of(path)} uses {match.group(0)!r}"


def test_files_referenced_by_the_html_pages_exist():
    for page in ("index.html", "404.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        for reference in re.findall(r'(?:href|src)="(/static/[^"]+)"', html):
            target = STATIC / reference.removeprefix("/static/")
            assert target.is_file(), f"{page} references {reference}, which does not exist"


def test_html_pages_work_under_the_strict_policy():
    for page in ("index.html", "404.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)", html), f"{page} has an inline script"
        assert "<style" not in html, f"{page} has an inline stylesheet"
        assert not re.search(r"\sstyle=", html), f"{page} has an inline style attribute"
        assert not re.search(r"\son[a-z]+=", html), f"{page} has an inline event handler"


def test_pipeline_stages_in_the_browser_match_what_the_worker_reports():
    worker_source = (ROOT / "app" / "services" / "processing_service.py").read_text(encoding="utf-8")
    worker = [
        (stage, int(progress))
        for stage, progress in re.findall(r'on_progress\("([^"]+)",\s*(\d+)\)', worker_source)
        if stage != "Completed"
    ]
    browser_source = (STATIC / "js" / "ui" / "pipeline.js").read_text(encoding="utf-8")
    browser = [(stage, int(at)) for stage, at in re.findall(r'stage:\s*"([^"]+)",\s*at:\s*(\d+)', browser_source)]

    assert worker, "found no on_progress calls in processing_service.py"
    assert browser == worker, "the track in pipeline.js has drifted from the worker's stages"