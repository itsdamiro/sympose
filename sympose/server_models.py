"""Request body models for the web API — split out of
`server_handlers.py` (project's 200-LOC-per-file guideline)."""

from typing import Any

from pydantic import BaseModel, Field


class NoteWrite(BaseModel):
    """Body of `PUT /api/vault/note` — the web app editor saving an
    *existing* note back to the vault verbatim, frontmatter included."""

    path: str = Field(..., min_length=1)
    content: str
    persona: str | None = None
    expected_mtime: float | None = Field(
        None,
        description="mtime this save was opened from (from GET /api/vault/note). "
        "When given, a save is rejected with 409 if the file changed on disk "
        "since then, instead of silently overwriting it.",
    )


class NoteCreate(BaseModel):
    """Body of `POST /api/vault/note` — create a *new* note at `path`
    (relative to the vault, e.g. `Projects/Idea`). `content` is optional;
    omitted, the backend seeds a frontmatter + title stub."""

    path: str = Field(..., min_length=1)
    content: str | None = None
    persona: str | None = None


class FolderCreate(BaseModel):
    """Body of `POST /api/vault/folder` — create a new *empty* folder at
    `path` (relative to the vault, e.g. `Projects/Archive`)."""

    path: str = Field(..., min_length=1)
    persona: str | None = None


class FolderRename(BaseModel):
    """Body of `PATCH /api/vault/folder` — rename the folder at `path` to `new_name`, one plain name: the folder keeps its
    parent (moving a folder is a separate step). Links that name it, the personas' scopes, the hidden list and the
    persona's pending changes follow (docs/decisions/073)."""

    path: str = Field(..., min_length=1)
    new_name: str
    persona: str | None = None


class NoteRename(BaseModel):
    """Body of `PATCH /api/vault/note` — rename `path` to `new_path` and
    rewrite every `[[wikilink]]` that referenced it. `new_path` stays in
    the same folder unless it carries a separator (then it is relative to
    the vault); a leading slash (`/name`) means the vault root."""

    path: str = Field(..., min_length=1)
    new_path: str = Field(..., min_length=1)
    persona: str | None = None


class TrashRestore(BaseModel):
    """Body of `POST /api/vault/trash/restore` — move the trashed note at
    `path` (a `.trash`-relative path from `GET /api/vault/trash`) back to
    where it was deleted from."""

    path: str = Field(..., min_length=1)
    persona: str | None = None


class TrashEmpty(BaseModel):
    """Body of `POST /api/vault/trash/empty` — permanently delete every
    in-scope trashed note."""

    persona: str | None = None


class VaultActivate(BaseModel):
    """Body of `POST /api/vaults/active` — switch the active vault to
    `path`, one of `GET /api/vaults`' configured paths."""

    path: str = Field(..., min_length=1)


class HiddenPath(BaseModel):
    """Body of `POST /api/vault/hidden` — hide the folder or note at `path` (vault-relative) from
    the web app's view (docs/decisions/037)."""

    path: str = Field(..., min_length=1)


class DefinitionsSwitch(BaseModel):
    """Body of `PUT /api/vault/hidden/definitions` — whether the tree lists folder definition notes."""

    show: bool


class FolderIcon(BaseModel):
    """Body of `POST /api/vault/health/icon` — the vault health's offer to add the built-in icon and colours to the
    definition note of the top-level folder `folder` (docs/decisions/064)."""

    folder: str = Field(..., min_length=1)


class FolderDefinition(BaseModel):
    """Body of `POST /api/vault/folder/definition` — write the definition note of the top-level folder `path` from
    what the user typed: an optional `purpose` and the property lines of the folder's `template`
    (docs/decisions/038)."""

    path: str = Field(..., min_length=1)
    purpose: str = ""
    template: list[str] = Field(default_factory=list)
    persona: str | None = None


class ChatCancel(BaseModel):
    """Body of `POST /api/chat/cancel` — stop a reply in flight (docs/decisions/054): the conversation
    `session_id` names, or every reply the persona is writing when it is left out, or with `unnamed` only a first message's, which has no id
    yet (docs/decisions/057)."""

    persona: str | None = None
    session_id: str | None = None
    unnamed: bool = False  # only a reply whose first message named no conversation: the web's, before its id is known


class OpenNoteBody(BaseModel):
    """The note open in the editor, as the editor holds it (docs/decisions/072): its path and its current text,
    which can be ahead of the file."""

    path: str = Field(..., min_length=1)
    text: str


class ChatTurn(BaseModel):
    """Body of `POST /api/chat/turn` — one message to a persona. `session_id` continues a conversation;
    omitted, a new one starts and its id comes back in the reply. `edits` says the screen can show a proposal
    (the web app does; the terminal does not), and `open_note` is the note open in the editor, if one is."""

    message: str = Field(..., min_length=1)
    persona: str | None = None
    session_id: str | None = None
    edits: bool = False
    open_note: OpenNoteBody | None = None


class ChatCompact(BaseModel):
    """Body of `POST /api/chat/compact` — condense the earlier part of a conversation into notes now
    (docs/decisions/055)."""

    persona: str | None = None
    session_id: str = Field(..., min_length=1)


class ChatSessionStart(BaseModel):
    """Body of `POST /api/chat/session` — start a fresh, empty conversation with a persona."""

    persona: str | None = None


class ChatBinAction(BaseModel):
    """Body of the Bin's conversation routes (docs/decisions/057): the persona, and for a restore the
    conversation's name in the Bin (`id` is left out to empty the Bin)."""

    persona: str | None = None
    id: str | None = None


class ChatSessionUpdate(BaseModel):
    """Body of `PATCH /api/chat/session/<id>` — a new title and/or whether the conversation is pinned
    (docs/decisions/057). What is left out is left as it is."""

    persona: str | None = None
    title: str | None = None
    pinned: bool | None = None


class SettingChange(BaseModel):
    """Body of `PUT /api/settings/{key}` — the value wanted, or `null` for the setting's default."""

    value: Any = None


class SharingChange(BaseModel):
    """Body of `PUT /api/sharing/{category}` — whether cloud models may receive that category."""

    shared: bool


class ModelChoice(BaseModel):
    """Body of `PUT /api/personas/{handle}/model` — the persona's own model, or `null` to clear it."""

    model: str | None = None


class EditModeChoice(BaseModel):
    """Body of `PUT /api/personas/{handle}/edit-mode` — the persona's own edit mode, or `null` to clear it."""

    mode: str | None = None


class PersonaFileWrite(BaseModel):
    """Body of `PUT /api/personas/{handle}/files/{name}` (docs/decisions/061): the editor saving one of a persona's
    own files. `expected_mtime` is the mtime it was opened at, so a change made meanwhile is a 409, not overwritten."""

    content: str
    expected_mtime: float | None = None

