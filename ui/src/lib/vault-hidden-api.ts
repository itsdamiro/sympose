import { detailOf } from "./vault-note-api"

/**
 * Client for `/api/vault/hidden*` — the folders and notes the user has hidden
 * from view (docs/decisions/037). The list lives in the settings file, per
 * vault; every call answers with the whole state. Hiding is a display
 * preference: the persona still reads what is hidden.
 */
export interface HiddenState {
  /** Vault-relative paths the user hid — a folder hides everything under it. */
  hidden: string[]
  /** Whether the tree lists folder definition notes (off by default). */
  showDefinitionNotes: boolean
}

/** A stable value for "nothing hidden yet / backend unreachable". */
export const NO_HIDDEN: HiddenState = { hidden: [], showDefinitionNotes: false }

export type HiddenResult =
  | { ok: true; state: HiddenState }
  | { ok: false; error: string }

function toState(data: Partial<HiddenState>): HiddenState {
  return {
    hidden: data.hidden ?? [],
    showDefinitionNotes: data.showDefinitionNotes ?? false,
  }
}

/** `GET /api/vault/hidden`. Nothing hidden when the backend is unreachable. */
export async function fetchHidden(): Promise<HiddenState> {
  try {
    const res = await fetch("/api/vault/hidden")
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return toState((await res.json()) as Partial<HiddenState>)
  } catch (err) {
    console.info(`[vault-hidden] /api/vault/hidden unreachable (${err})`)
    return NO_HIDDEN
  }
}

async function send(
  url: string,
  init: RequestInit,
  failure: string
): Promise<HiddenResult> {
  try {
    const res = await fetch(url, init)
    if (res.ok) {
      return { ok: true, state: toState((await res.json()) as Partial<HiddenState>) }
    }
    return {
      ok: false,
      error: (await detailOf(res)) || `${failure} (HTTP ${res.status})`,
    }
  } catch (err) {
    return { ok: false, error: `${failure} — backend unreachable (${err})` }
  }
}

const JSON_HEADERS = { "Content-Type": "application/json" }

/** `POST /api/vault/hidden` — hide a folder or note. Idempotent. */
export function hidePath(path: string): Promise<HiddenResult> {
  return send(
    "/api/vault/hidden",
    { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ path }) },
    "Couldn't hide it"
  )
}

/** `DELETE /api/vault/hidden` — show a hidden path again. Idempotent. */
export function unhidePath(path: string): Promise<HiddenResult> {
  return send(
    `/api/vault/hidden?path=${encodeURIComponent(path)}`,
    { method: "DELETE" },
    "Couldn't unhide it"
  )
}

/** `PUT /api/vault/hidden/definitions` — list folder definition notes in the tree, or not. */
export function setShowDefinitionNotes(show: boolean): Promise<HiddenResult> {
  return send(
    "/api/vault/hidden/definitions",
    { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ show }) },
    "Couldn't save the setting"
  )
}
