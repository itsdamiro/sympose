import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for the persona's pending changes and the comments on a note (docs/decisions/070, 042, 069). The backend
 * keeps them in the persona's own folder, never in the vault, and works out each one's status against the note on
 * disk; the editor works out its own against the text in front of the user, with `passage-finder`.
 */
export interface Proposal {
  id: string
  time: string
  kind: "edit" | "create"
  /** The explanation she gave in one sentence. */
  say: string
  /** An edit: the passage she quoted, what replaces it, and a little text on each side of the passage. */
  find?: string
  replace?: string
  before?: string
  after?: string
  /** A new note: its whole text and the working name it is listed under. */
  text?: string
  name?: string
  /** Against the note on disk when it was fetched. */
  status: "pending" | "outdated"
}

export interface Annotation {
  id: string
  time: string
  author: "user" | "persona"
  quote: string
  before: string
  after: string
  text: string
  state: "open" | "resolved"
  reply_to: string | null
  status: "attached" | "detached"
}

export interface NoteChanges {
  path: string
  /** A new note she proposed is not on disk yet. */
  exists: boolean
  mtime: number | null
  proposals: Proposal[]
  annotations: Annotation[]
}

export interface Draft {
  path: string
  name: string | null
  is_new: boolean
  /** Changes waiting; 0 for a note listed only for its open comments. */
  count: number
  /** Open comments, by the user or by her (the answers under one are not counted). */
  comments: number
  time: string
}

/** `GET /api/vault/changes`: one note's proposals and comments; `null` when the backend is unreachable. */
export async function fetchChanges(path: string, persona: string): Promise<NoteChanges | null> {
  try {
    const res = await fetch(`/api/vault/changes?path=${encodeURIComponent(path)}&persona=${encodeURIComponent(persona)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return (await res.json()) as NoteChanges
  } catch (err) {
    console.info(`[persona-changes] /api/vault/changes unreachable (${err})`)
    return null
  }
}

/** `GET /api/vault/drafts`: the notes with a proposal waiting; empty when the backend is unreachable. */
export async function fetchDrafts(persona: string): Promise<Draft[]> {
  try {
    const res = await fetch(`/api/vault/drafts?persona=${encodeURIComponent(persona)}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return ((await res.json()) as { drafts: Draft[] }).drafts
  } catch (err) {
    console.info(`[persona-changes] /api/vault/drafts unreachable (${err})`)
    return []
  }
}

export type ResolveResult = { ok: true; resolved: string[] } | { ok: false; error: string }

/**
 * `POST /api/vault/changes/resolve`: the user accepted or declined these proposals (`ids`), or every one the note has
 * (`"all"`). An accepted one has already been applied to the editor's own text; the server only forgets it.
 */
export async function resolveChanges(path: string, persona: string, which: string[] | "all"): Promise<ResolveResult> {
  try {
    const res = await fetch("/api/vault/changes/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, persona, ...(which === "all" ? { all: true } : { ids: which }) }),
    })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
    return { ok: true, resolved: ((await res.json()) as { resolved: string[] }).resolved }
  } catch {
    return { ok: false, error: "the Sympose backend is not reachable" }
  }
}

export type CommentResult = { ok: true; comment?: Annotation } | { ok: false; error: string }

async function sendComment(method: "POST" | "PATCH", body: Record<string, unknown>): Promise<CommentResult> {
  try {
    const res = await fetch("/api/vault/annotations", { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
    return { ok: true, comment: method === "POST" ? ((await res.json()) as Annotation) : undefined }
  } catch {
    return { ok: false, error: "the Sympose backend is not reachable" }
  }
}

/**
 * `POST /api/vault/annotations`: a new comment on a passage. `before` and `after` are the text just around it in the
 * editor's own text, which can be ahead of the file on disk, so the backend keeps them instead of searching the file.
 */
export function addComment(args: { path: string; persona: string; quote: string; before: string; after: string; text: string }): Promise<CommentResult> {
  return sendComment("POST", args)
}

/** `POST /api/vault/annotations` with `reply_to`: an answer under a comment, about the same passage. */
export function replyToComment(args: { path: string; persona: string; replyTo: string; text: string }): Promise<CommentResult> {
  return sendComment("POST", { path: args.path, persona: args.persona, reply_to: args.replyTo, text: args.text })
}

/** `PATCH /api/vault/annotations`: resolve or reopen a comment (its answers with it), and/or change its text. */
export function changeComment(args: { path: string; persona: string; id: string; state?: "open" | "resolved"; text?: string }): Promise<CommentResult> {
  return sendComment("PATCH", args)
}

/** `DELETE /api/vault/annotations`: a comment and the answers under it. */
export async function deleteComment(path: string, persona: string, id: string): Promise<CommentResult> {
  try {
    const res = await fetch(`/api/vault/annotations?path=${encodeURIComponent(path)}&id=${encodeURIComponent(id)}&persona=${encodeURIComponent(persona)}`, { method: "DELETE" })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
    return { ok: true }
  } catch {
    return { ok: false, error: "the Sympose backend is not reachable" }
  }
}
