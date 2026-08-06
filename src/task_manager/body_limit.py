"""Application-level request body size limit.

Defense in depth, not a replacement: like rate limiting (see
`rate_limit.py`), a real production deployment should also cap request
body size at the gateway/reverse-proxy layer (nginx `client_max_body_size`,
an API gateway, Cloudflare, etc.), which rejects oversized requests
before they ever reach this process. This in-app layer protects
deployments that don't have such a layer yet, and rejects cheaply --
before FastAPI/Pydantic ever reads or parses the body -- for those that
do.
"""

import os

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Well above any legitimate payload (the largest single field allowed by
# schemas.py is DESCRIPTION_MAX_LENGTH=2000 chars; a full request body is
# a few KB at most) and orders of magnitude below an attack payload (the
# pentest report used 48MB).
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", str(100 * 1024)))


class BodySizeLimitMiddleware:
    """Rejects requests whose declared Content-Length exceeds MAX_BODY_BYTES.

    Checked from the `Content-Length` header alone, before Starlette or
    FastAPI reads a single byte of the body, so an oversized request is
    never buffered into memory or parsed as JSON. A request with no
    `Content-Length` header (e.g. chunked transfer-encoding) is not
    inspected here — this middleware targets the common case reported by
    the pentest, not every possible way to stream an unbounded body.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    length = int(content_length)
                except ValueError:
                    length = None
                if length is not None and length > MAX_BODY_BYTES:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large (max {MAX_BODY_BYTES} bytes)"
                        },
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)
