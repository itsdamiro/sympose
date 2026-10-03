/**
 * Client for `GET /api/vault/related` — the notes close in meaning to the open note (docs/decisions/066), for the
 * notes panel's footer. `enabled` is false when the user turned `connections_by_meaning` off (or the backend could
 * not be reached): the footer then shows no section at all. A note with no neighbour is enabled with an empty list.
 */
export interface RelatedNote {
  rel_path: string
  title: string
  /** A reading of how strong the relation is, 0 to 100 (never a probability). */
  percent: number
  /** The note sits inside something the user hid from view (docs/decisions/037). */
  hidden?: boolean
}

export interface RelatedState {
  enabled: boolean
  related: RelatedNote[]
  /** The first index of the vault is still being built, so an empty list will fill in: ask again soon. */
  indexing?: boolean
}

/** A stable value for "off / backend unreachable". */
export const NO_RELATED: RelatedState = { enabled: false, related: [] }

export async function fetchRelated(
  path: string,
  persona: string,
  signal?: AbortSignal
): Promise<RelatedState> {
  const params = new URLSearchParams({ path, persona })
  try {
    const res = await fetch(`/api/vault/related?${params}`, { signal })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as Partial<RelatedState>
    return { enabled: data.enabled ?? false, related: data.related ?? [], indexing: data.indexing ?? false }
  } catch (err) {
    if ((err as { name?: string })?.name !== "AbortError") {
      console.info(`[vault-related] /api/vault/related unreachable (${err}) — showing no related notes`)
    }
    return NO_RELATED
  }
}
