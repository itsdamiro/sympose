import * as React from "react"

import type { VaultNode } from "@/components/sympose"
import { findNoteByPath, findNoteByWikilink } from "@/lib/find-note-by-wikilink"

/**
 * Opening a note from a link: a `[[wikilink]]` in the open note, a note named
 * under a chat reply (what the reply was based on), or a `[[wikilink]]` in a
 * chat reply. Everything is resolved against `vaultTree`, the notes the user
 * can see, so a link to a note hidden from view (docs/decisions/037) or since
 * deleted does nothing instead of opening it.
 *
 * `previewRequest` counts the opens that should show the note in preview mode:
 * a note reached from the chat is read, not edited.
 */
export function useNoteOpening({
  vaultTree,
  selectNote,
  openEditor,
}: {
  vaultTree: VaultNode[]
  selectNote: (path: string) => void
  openEditor: () => void
}) {
  const [previewRequest, setPreviewRequest] = React.useState(0)

  const openWikilink = (target: string) => {
    const match = findNoteByWikilink(vaultTree, target)
    if (match) {
      selectNote(match.path)
      openEditor()
    }
  }

  const openGroundedNote = (path: string) => {
    if (!findNoteByPath(vaultTree, path)) return
    selectNote(path)
    openEditor()
    setPreviewRequest((n) => n + 1)
  }

  const openChatWikilink = (target: string) => {
    const match = findNoteByWikilink(vaultTree, target)
    if (match) openGroundedNote(match.path)
  }

  return { previewRequest, openWikilink, openGroundedNote, openChatWikilink }
}
