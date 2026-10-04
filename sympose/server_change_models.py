"""Request bodies for the pending-changes and annotation routes (docs/decisions/070), split out of
`server_models.py` (project's 200-LOC-per-file guideline)."""

from pydantic import BaseModel, Field


class ChangesResolve(BaseModel):
    """Body of `POST /api/vault/changes/resolve` — the user accepted or declined proposals for the note at `path`.
    The editor has already applied an accepted one to its own text (the note is saved by the ordinary save), so the
    server only forgets it. `ids` names them; `all` forgets every proposal the note has."""

    path: str = Field(..., min_length=1)
    ids: list[str] = Field(default_factory=list)
    all: bool = False
    persona: str | None = None


class AnnotationCreate(BaseModel):
    """Body of `POST /api/vault/annotations` — a comment from the user. Either a new highlight on `quote`, with the
    text just `before` and `after` it as the editor sees it (else the note is searched for the passage, and `start` says
    where when the same words occur more than once), or an answer: `reply_to` names the comment it is under and the
    passage is that comment's."""

    path: str = Field(..., min_length=1)
    quote: str | None = None
    text: str = ""
    before: str | None = Field(None, max_length=2000)
    after: str | None = Field(None, max_length=2000)
    start: int | None = Field(None, ge=0)
    reply_to: str | None = None
    persona: str | None = None


class AnnotationChange(BaseModel):
    """Body of `PATCH /api/vault/annotations` — resolve or reopen a comment, and/or change its text."""

    path: str = Field(..., min_length=1)
    id: str = Field(..., min_length=1)
    state: str | None = None
    text: str | None = None
    persona: str | None = None
