from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SITE_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

# Swagger UI loads scripts from a CDN and runs inline code, so the site's policy would break it.
DOCS_PREFIXES = ("/docs", "/redoc", "/openapi.json")
API_PREFIX = "/api/"


class SecurityHeadersMiddleware:
    """Adds security and caching headers to every HTTP response."""

    def __init__(self, app: ASGIApp, production: bool = False) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # WebSockets pass through untouched
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]
        is_api = path.startswith(API_PREFIX)
        is_docs = path.startswith(DOCS_PREFIXES)
        is_site = not is_api and not is_docs
        revalidate = path == "/" or path.startswith("/static/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "same-origin"
                headers["Permissions-Policy"] = PERMISSIONS_POLICY
                headers["X-Frame-Options"] = "DENY"
                if is_site:
                    headers["Content-Security-Policy"] = SITE_CSP
                if is_api:
                    headers["Cache-Control"] = "no-store"  # tokens and personal data: never cache
                elif revalidate:
                    # Files are not fingerprinted, so always ask the server whether they changed.
                    # Unchanged files cost only a 304 response.
                    headers["Cache-Control"] = "no-cache"
                if self.production:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        await self.app(scope, receive, send_with_headers)