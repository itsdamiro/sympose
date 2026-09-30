"""Refuses a state-changing request that a web page on another origin sent. The server has no login, and CORS only hides a
response -- it does not stop a page the user happens to visit from POSTing to 127.0.0.1. A browser
always sends `Origin` on such a request, so a request whose `Origin` is neither this server's own
address nor the dev server's is refused. A request with no `Origin` (curl, the CLI, a test) is not
a browser page and is let through."""

from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

DEV_ORIGINS = frozenset({"http://localhost:5173", "http://localhost:3000"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def allowed(origin: str, host: str) -> bool:
    """`origin` is the page's own origin, or the address this server is being reached at (`host`)."""
    return origin in DEV_ORIGINS or urlsplit(origin).netloc == host


async def refuse_foreign_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and request.method not in _SAFE_METHODS and not allowed(origin, request.headers.get("host", "")):
        return JSONResponse({"detail": "Cross-origin request refused."}, status_code=403)
    return await call_next(request)
