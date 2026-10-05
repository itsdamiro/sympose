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

from sympose import server_change_handlers as chg
from sympose import server_chat_handlers as ch
from sympose import server_check_handlers as ckh
from sympose import server_definition_handlers as dh
from sympose import server_origin
from sympose import server_handlers as h
from sympose import server_hidden_handlers as hh
from sympose import server_edit_mode_handlers as emh
from sympose import server_model_handlers as mh
from sympose import server_persona_file_handlers as pfh
from sympose import server_persona_handlers as ph
from sympose import server_settings_handlers as seh
from sympose import server_sharing_handlers as sph
from sympose import server_search_handlers as sh
from sympose import server_session_handlers as sess
from sympose import server_trash_handlers as th
from sympose import server_vault_handlers as vh
from sympose import vault_paths
from sympose.server_change_models import AnnotationChange, AnnotationCreate, ChangesResolve, DraftText
from sympose.server_models import ChatBinAction, ChatCancel, ChatCompact, ChatSessionStart, ChatSessionUpdate, ChatTurn, DefinitionsSwitch, EditModeChoice, FolderDefinition, FolderIcon, HiddenPath, ModelChoice, PersonaFileWrite, SettingChange, SharingChange, TrashEmpty, TrashRestore, VaultActivate


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

    @app.get("/api/doctor")
    def get_doctor() -> dict[str, Any]:
        return ckh.get_doctor()

    @app.post("/api/doctor/fix")
    def fix_doctor() -> dict[str, Any]:
        return ckh.fix_doctor()

    @app.get("/api/vault/health")
    def get_vault_health() -> dict[str, Any]:
        return ckh.get_vault_health()

    @app.post("/api/vault/health/icon")
    def add_folder_icon(body: FolderIcon) -> dict[str, Any]:
        return ckh.add_folder_look(body.folder)

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

    @app.post("/api/chat/compact")
    def chat_compact(body: ChatCompact) -> dict[str, Any]:
        return ch.compact_session(body)

    @app.post("/api/chat/cancel")
    def chat_cancel(body: ChatCancel) -> dict[str, Any]:
        return ch.cancel_turn(body)

    @app.get("/api/chat/status")
    def chat_status(persona: str | None = Query(None), session_id: str | None = Query(None)) -> dict[str, Any]:
        return ch.get_status(persona, session_id)

    @app.get("/api/chat/status-phrases")
    def chat_status_phrases(persona: str | None = Query(None)) -> dict[str, Any]:
        return ch.get_status_phrases(persona)

    @app.get("/api/chat/context")
    def chat_context(persona: str | None = Query(None), session_id: str | None = Query(None)) -> dict[str, Any]:
        return ch.get_context(persona, session_id)

    @app.get("/api/chat/session")
    def chat_session(
        persona: str | None = Query(None),
        session_id: str | None = Query(None),
        before: int | None = Query(None, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
        return ch.get_session(persona, session_id, before, limit)

    @app.get("/api/chat/sessions")
    def chat_sessions(persona: str | None = Query(None)) -> dict[str, Any]:
        return sess.list_sessions(persona)

    @app.get("/api/chat/sessions/bin")
    def chat_sessions_bin(persona: str | None = Query(None)) -> dict[str, Any]:
        return sess.list_bin(persona)

    @app.post("/api/chat/sessions/bin/restore")
    def chat_sessions_bin_restore(body: ChatBinAction) -> dict[str, Any]:
        return sess.restore_from_bin(body)

    @app.delete("/api/chat/sessions/bin")
    def chat_sessions_bin_purge(id: str = Query(...), persona: str | None = Query(None)) -> dict[str, Any]:
        return sess.purge_from_bin(id, persona)

    @app.post("/api/chat/sessions/bin/empty")
    def chat_sessions_bin_empty(body: ChatBinAction) -> dict[str, Any]:
        return sess.empty_bin(body)

    @app.patch("/api/chat/session/{session_id}")
    def chat_session_update(session_id: str, body: ChatSessionUpdate) -> dict[str, Any]:
        return sess.update_session(session_id, body)

    @app.delete("/api/chat/session/{session_id}")
    def chat_session_delete(session_id: str, persona: str | None = Query(None)) -> dict[str, Any]:
        return sess.delete_session(session_id, persona)

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

    @app.get("/api/models")
    def get_models(persona: str | None = Query(None)) -> dict[str, Any]:
        return mh.get_models(persona)

    @app.put("/api/personas/{handle}/model")
    def put_persona_model(handle: str, body: ModelChoice) -> dict[str, Any]:
        return mh.put_persona_model(handle, body)

    @app.get("/api/edit-mode/global")
    def get_global_edit_mode() -> dict[str, Any]:
        return emh.get_global_edit_mode()

    @app.get("/api/personas/{handle}/edit-mode")
    def get_persona_edit_mode(handle: str) -> dict[str, Any]:
        return emh.get_edit_mode(handle)

    @app.put("/api/personas/{handle}/edit-mode")
    def put_persona_edit_mode(handle: str, body: EditModeChoice) -> dict[str, Any]:
        return emh.put_edit_mode(handle, body)

    @app.get("/api/personas")
    def get_personas() -> dict[str, Any]:
        return ph.get_personas()

    @app.get("/api/personas/{handle}/files")
    def list_persona_files(handle: str) -> dict[str, Any]:
        return pfh.list_files(handle)

    @app.get("/api/personas/{handle}/files/{name}")
    def get_persona_file(handle: str, name: str) -> dict[str, Any]:
        return pfh.get_file(handle, name)

    @app.put("/api/personas/{handle}/files/{name}")
    def put_persona_file(handle: str, name: str, body: PersonaFileWrite) -> dict[str, Any]:
        return pfh.put_file(handle, name, body)

    @app.post("/api/personas/{handle}/files/soul.md/reset")
    def reset_persona_soul(handle: str) -> dict[str, Any]:
        return pfh.reset_soul(handle)

    @app.get("/api/personas/{handle}/files/{name}/pending")
    def get_persona_file_pending(handle: str, name: str) -> dict[str, str]:
        return pfh.get_pending(handle, name)

    @app.post("/api/personas/{handle}/files/{name}/pending/accept")
    def accept_persona_file_pending(handle: str, name: str) -> dict[str, Any]:
        return pfh.accept_pending(handle, name)

    @app.post("/api/personas/{handle}/files/{name}/pending/discard")
    def discard_persona_file_pending(handle: str, name: str) -> dict[str, Any]:
        return pfh.discard_pending(handle, name)

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

    @app.get("/api/vault/related")
    def related_notes(
        path: str = Query(..., description="Relative path of the open note"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return sh.related_notes(path, persona)

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

    @app.get("/api/vault/drafts")
    def list_drafts(persona: str | None = Query(None)) -> dict[str, Any]:
        return chg.list_drafts(persona)

    @app.get("/api/vault/changes")
    def get_changes(
        path: str = Query(..., description="Relative path of the note"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return chg.get_changes(path, persona)

    @app.post("/api/vault/changes/resolve")
    def resolve_changes(body: ChangesResolve) -> dict[str, Any]:
        return chg.resolve_changes(body)

    @app.patch("/api/vault/changes/draft")
    def save_draft(body: DraftText) -> dict[str, Any]:
        return chg.save_draft(body)

    @app.post("/api/vault/annotations", status_code=201)
    def add_annotation(body: AnnotationCreate) -> dict[str, Any]:
        return chg.add_annotation(body)

    @app.patch("/api/vault/annotations")
    def change_annotation(body: AnnotationChange) -> dict[str, Any]:
        return chg.change_annotation(body)

    @app.delete("/api/vault/annotations")
    def delete_annotation(
        path: str = Query(..., description="Relative path of the note"),
        id: str = Query(..., description="The comment's id"),
        persona: str | None = Query(None),
    ) -> dict[str, Any]:
        return chg.delete_annotation(path, id, persona)

    @app.get("/api/vault/trash")
    def list_trash(persona: str | None = Query(None)) -> dict[str, Any]:
        return th.list_trash(persona)

    @app.post("/api/vault/trash/restore")
    def restore_trash(body: TrashRestore) -> dict[str, Any]:
        return th.restore_trash(body)

    @app.post("/api/vault/trash/restore-folder")
    def restore_trash_folder(body: TrashRestore) -> dict[str, Any]:
        return th.restore_trash_folder(body)

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
