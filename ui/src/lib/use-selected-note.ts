import * as React from "react"

import { getCookie, vaultScopedKey } from "@/lib/cookies"
import { useVaultScopedState } from "@/lib/use-vault-scoped-state"

const NOTE_COOKIE = "sympose:shell.note"

function readSelectedNote(raw: string | null): string | undefined {
  return raw || undefined
}
function serializeSelectedNote(path: string | undefined): string {
  return path ?? ""
}

/**
 * The note a vault switch or add should open to, read straight from that vault's
 * own scoped cookie. The switch handlers call this directly, bypassing
 * `useVaultScopedState`'s own one-render-later reseed, so `<MarkdownPanel>` never
 * sees the new vault paired with the outgoing vault's still-selected note.
 */
export function resolveSelectedNoteFor(vaultPath: string | null): string | undefined {
  return readSelectedNote(getCookie(vaultScopedKey(NOTE_COOKIE, vaultPath)))
}

/**
 * The note open in the editor. Persisted across a refresh so the editor reopens
 * on the same note instead of coming back empty, and scoped per vault (reseeded
 * on a vault switch by `useVaultScopedState`): a note path is a reference into
 * one vault's content, meaningless in another, so each vault remembers its own
 * last-open note.
 *
 * - `selectNote` is a note genuinely opened by the user (row click, wikilink,
 *   search result, newly created) and is recorded as a visit. `setSelectedNote`
 *   alone just remaps the still-open note's path or clears it, neither of which
 *   is a new visit.
 * - `noteRenamed` follows a renamed or moved note: its pin, its place in the
 *   recents and, when open, the editor (docs/decisions/051).
 * - `openableNote` is what the editor shows: a remembered note that has since
 *   been hidden does not reopen, and a note hidden while open closes at once
 *   (docs/decisions/037). Nebula node ids are the note's full vault-relative
 *   path, so this also drives the nebula's focus with no transformation.
 */
export function useSelectedNote({
  vaultPath,
  isHidden,
  recordVisit,
  remapPin,
  remapRecent,
}: {
  vaultPath: string | null
  isHidden: (path: string | undefined) => boolean
  recordVisit: (path: string) => void
  remapPin: (oldPath: string, newPath: string) => void
  remapRecent: (oldPath: string, newPath: string) => void
}) {
  const [selectedNote, setSelectedNote] = useVaultScopedState(
    NOTE_COOKIE,
    vaultPath,
    readSelectedNote,
    serializeSelectedNote
  )
  const selectNote = React.useCallback(
    (path: string) => {
      setSelectedNote(path)
      recordVisit(path)
    },
    [recordVisit, setSelectedNote]
  )
  const noteRenamed = React.useCallback(
    (oldPath: string, newPath: string) => {
      remapPin(oldPath, newPath)
      remapRecent(oldPath, newPath)
      if (selectedNote === oldPath) setSelectedNote(newPath)
    },
    [remapPin, remapRecent, selectedNote, setSelectedNote]
  )
  const openableNote = isHidden(selectedNote) ? undefined : selectedNote
  return { selectedNote, setSelectedNote, openableNote, selectNote, noteRenamed }
}
