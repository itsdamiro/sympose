"""Dev entry point: `python -m sympose.main`. Reads `VAULT_PATHS` (and
optionally `SYMPOSE_PROFILES_DIR`) from the environment — see `.env.example`.
`npm run dev` in `ui/` proxies `/api`, `/health` and `/docs` here and serves the
frontend itself, so this rarely serves a page in that setup; hitting this port
directly (no `ui/` dev server) still gets the last built `sympose/webui/`, same
as `sympose web` (docs/decisions/028) — including the same Host-header guard,
added unconditionally below so it holds under uvicorn's `reload=True` too (a
reloaded worker process re-imports this module fresh; the guard must be part
of that re-import, not of a `__main__`-only branch it never runs)."""

import os

import uvicorn

from sympose.envfile import load_env

load_env()

from sympose import web_static  # noqa: E402 — after load_env()
from sympose.server import create_app  # noqa: E402 — after load_env()

app = create_app()
try:
    web_static.mount_web_app(app)
except web_static.WebAppMissing:
    pass  # a checkout that has not run `npm run build` in `ui/` yet: the API alone, as before
web_static.guard_own_names(app)

if __name__ == "__main__":
    uvicorn.run(
        "sympose.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
