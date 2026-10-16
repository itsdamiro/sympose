"""
The route that serves one vault image (docs/decisions/085). Anything it does not serve is a 404, so the web
app's `HEAD` leaves a reference as text and a path outside the persona's folders is not told apart from a
missing file; only a file over the limit says why (413).
"""

from fastapi import HTTPException
from fastapi.responses import FileResponse

from sympose import vault_image
from sympose.server_handlers import require_profile

SVG_SANDBOX = "sandbox; default-src 'none'"


def get_vault_image(path: str, from_path: str, persona: str | None) -> FileResponse:
    profile = require_profile(persona)
    try:
        target = vault_image.resolve_image(profile, path, from_path)
    except vault_image.ImageTooLarge:
        raise HTTPException(status_code=413, detail=f"Image `{path}` is over the size limit.")
    if target is None:
        raise HTTPException(status_code=404, detail=f"Image `{path}` was not found in the folders this persona can read.")
    media_type = vault_image.media_type(target)
    headers = {"X-Content-Type-Options": "nosniff"}
    if media_type == "image/svg+xml":
        headers["Content-Security-Policy"] = SVG_SANDBOX
    return FileResponse(target, media_type=media_type, headers=headers)
