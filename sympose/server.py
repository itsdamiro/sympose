"""
Minimal FastAPI backend for the Sympose web app — vault browsing, note
editing, trash recovery, and the Knowledge Nebula graph. Ported from
sympose-legacy's much larger `server.py` (~21 routes: chat, personas,
skills, Slack, search, TLS, and a password-auth middleware), trimmed to
the routes the web app's tree, editor, note-management menus, bin,
nebula, and search actually call. Deliberately not included yet: asset
(image) serving. No auth yet — this is a local dev server bound to
localhost; add `DashboardAuthMiddleware` back before this is ever exposed
beyond that.

Request/response models and handler logic live in `server_handlers.py`
(note/folder CRUD), `server_trash_handlers.py` (the bin), and
`server_search_handlers.py` (search), and `server_definition_handlers.py` (setting up a new folder); this file only wires routes to them.
"""

from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from sympose import server_chat_handlers as ch
from sympose import server_definition_handlers as dh
from sympose import server_origin
from sympose import server_handlers as h
from sympose import server_hidden_handlers as hh
from sympose import server_persona_handlers as ph
from sympose import server_settings_handlers as seh
from sympose import server_sharing_handlers as sph
from sympose import server_search_handlers as sh
from sympose import server_trash_handlers as th
from sympose import server_vault_handlers as vh
from sympose import vault_paths
from sympose.server_models import ChatSessionStart, ChatTurn, DefinitionsSwitch, FolderDefinition, HiddenPath, SettingChange, SharingChange, TrashEmpty, TrashRestore, VaultActivate


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sympose Web API (minimal)",
        description="Vault browsing and note editing — no auth, local dev only.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(server_origin.refuse_foreign_origin)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "healthy", "vault": vault_paths.get_master_vault()}

    @app.get("/api/vaults")
    def list_vaults() -> dict[str, Any]:
        return vh.list_vaults()

    @app.post("/api/vaults/active")
    def set_active_vault(body: VaultActivate) -> dict[str, Any]:
        return vh.set_active_vault(body.path)

    @app.post("/api/vaults", status_code=201)
    def add_vault(body: VaultActivate) -> dict[str, Any]:
        return vh.add_vault(body.path)

    @app.post("/api/chat/turn")
    def chat_turn(body: ChatTurn) -> dict[str, Any]:
        return ch.send_turn(body)

    @app.get("/api/chat/status")
    def chat_status(persona: str | None = Query(None)) -> dict[str, Any]:
        return ch.get_status(persona)

    @app.get("/api/chat/session")
    def chat_session(
        persona: str | None = Query(None),
        session_id: str | None = Query(None),
        before: int | None = Query(None, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
        return ch.get_session(persona, session_id, before, limit)

    @app.post("/api/chat/session")
    def chat_session_start(body: ChatSessionStart) -> dict[str, Any]:
        return ch.start_session(body)

    @app.get("/api/settings")
    def get_settings() -> dict[str, Any]:
        return seh.get_settings()

    @app.put("/api/settings/{key}")
    def put_setting(key: str, body: SettingChange) -> dict[str, Any]:
        return seh.put_setting(key, body)

    @app.get("/api/sharing")
    def get_sharing(persona: str | None = Query(None)) -> dict[str, Any]:
        return sph.get_sharing(persona)

    @app.put("/api/sharing/{category}")
    def put_sharing(category: str, body: SharingChange, persona: str | None = Query(None)) -> dict[str, Any]:
        return sph.put_sharing(category, persona, body)

    @app.get("/api/personas")
    def get_personas() -> dict[str, Any]:
        return ph.get_personas()

    @app.get("/api/vault/tree")
    def get_vault_tree(persona: str | None = Query(None)) -> dict[str, Any]:
        return h.get_vault_tree(persona)

    @app.get("/api/vault/graph")
    def get_vault_graph(persona: str | None = Query(None)) -> dict[str, Any]:
        return h.get_vault_graph(persona)

    @app.get("/api/vault/hidden")
    def get_hidden() -> dict[str, Any]:
        return hh.get_hidden()

    @app.post("/api/vault/hidden")
    def hide_path(body: HiddenPath) -> dict[str, Any]:
        return hh.hide(body)

    @app.delete("/api/vault/hidden")
    def unhide_path(
        path: str = Query(..., description="Vault-relative path to show again"),
    ) -> dict[str, Any]:
        return hh.unhide(path)

    @app.put("/api/vault/hidden/definitions")
    def set_definitions(body: DefinitionsSwitch) -> dict[str, Any]:
        return hh.set_definitions(body)

    @app.get("/api/vault/search")
    def search_vault(
        q: str = Query(..., description="Search query"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return sh.search_vault(q, persona)

    @app.get("/api/vault/note")
    def read_note(
        path: str = Query(..., description="Relative path of note"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return h.read_note(path, persona)

    @app.put("/api/vault/note")
    def write_note(body: h.NoteWrite) -> dict[str, Any]:
        return h.write_note(body)

    @app.post("/api/vault/note", status_code=201)
    def create_note(body: h.NoteCreate) -> dict[str, Any]:
        return h.create_note(body)

    @app.post("/api/vault/folder", status_code=201)
    def create_folder(body: h.FolderCreate) -> dict[str, Any]:
        return h.create_folder(body)

    @app.get("/api/vault/note-template")
    def get_note_template(
        folder: str | None = Query(None, description="A root folder to ask whether it can have a definition"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return dh.get_note_template(folder, persona)

    @app.post("/api/vault/folder/definition", status_code=201)
    def write_folder_definition(body: FolderDefinition) -> dict[str, Any]:
        return dh.write_definition(body)

    @app.patch("/api/vault/note")
    def rename_note(body: h.NoteRename) -> dict[str, Any]:
        return h.rename_note(body)

    @app.delete("/api/vault/note")
    def delete_note(
        path: str = Query(..., description="Relative path of the note to delete"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return h.delete_note(path, persona)

    @app.delete("/api/vault/folder")
    def delete_folder(
        path: str = Query(
            ..., description="Vault-relative path of the folder to delete"
        ),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return h.delete_folder(path, persona)

    @app.get("/api/vault/trash")
    def list_trash(persona: str | None = Query(None)) -> dict[str, Any]:
        return th.list_trash(persona)

    @app.post("/api/vault/trash/restore")
    def restore_trash(body: TrashRestore) -> dict[str, Any]:
        return th.restore_trash(body)

    @app.delete("/api/vault/trash")
    def purge_trash(
        path: str = Query(..., description="`.trash`-relative path to delete"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return th.purge_trash(path, persona)

    @app.post("/api/vault/trash/empty")
    def empty_trash(body: TrashEmpty) -> dict[str, Any]:
        return th.empty_trash(body)

    return app
