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
    """Body of `POST /api/vault/annotations` — a highlight with a comment on `quote`, from the user. `start` is where
    in the note the passage begins, needed when the same words occur more than once. `reply_to` is a comment this
    answers."""

    path: str = Field(..., min_length=1)
    quote: str = Field(..., min_length=1)
    text: str = ""
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
