import * as React from "react"

import type { FolderMoveAsk } from "@/components/sympose/folder-move-dialog"
import { notify } from "@/lib/notify"
import { moveVaultFolder, planFolderMove, type FolderMoveAnswers } from "@/lib/vault-folder-move-api"

/**
 * Moving a folder by dropping its row on another folder, a root folder or the vault root (docs/decisions/074). The
 * plan is asked of the server first (read only); whatever needs the user's word is asked in turn (a folder of that name
 * already there: rename or merge; files in both: rename the incoming ones; a persona whose reach would change), and the
 * move is sent only when nothing is left to ask. Cancelling any prompt changes nothing.
 *
 * - `before` runs first and `false` holds the move back (a note with unsaved edits is saved, as for a rename).
 * - `after(old, new)` follows a move that happened: the open note, pins, recents and expanded folders.
 * - `noteRenamedAway` is called with the open note when a merge renamed it to avoid a clash, so the editor does not
 *   follow it onto the note that was already there.
 */
export function useFolderMove({
  persona,
  selectedNote,
  before,
  after,
  noteRenamedAway,
  refreshVault,
}: {
  persona: string
  selectedNote: string | undefined
  before: () => Promise<boolean>
  after: (oldFolder: string, newFolder: string) => Promise<void> | void
  noteRenamedAway: () => void
  refreshVault: () => void
}) {
  const [ask, setAsk] = React.useState<FolderMoveAsk | null>(null)
  const busy = React.useRef(false)

  // The prompt is cleared as it is answered, so the next one is never mistaken for it.
  const prompt = <T,>(make: (resolve: (value: T) => void) => FolderMoveAsk) =>
    new Promise<T>((resolve) =>
      setAsk(
        make((value) => {
          setAsk(null)
          resolve(value)
        })
      )
    )

  const moveFolder = async (path: string, destination: string) => {
    if (busy.current) return
    busy.current = true
    try {
      if (!(await before())) return
      const plan = await planFolderMove(path, destination, persona)
      if (!plan.ok) return void notify.error(plan.error)

      const answers: FolderMoveAnswers = {}
      let reach = plan.reach
      if (plan.clash) {
        const name = path.slice(path.lastIndexOf("/") + 1)
        const choice = await prompt<{ merge: true } | { newName: string } | null>((resolve) => ({ kind: "clash", name, destination, resolve }))
        if (!choice) return
        if ("merge" in choice) answers.ifExists = "merge"
        else {
          Object.assign(answers, { ifExists: "rename", newName: choice.newName })
          // What a persona reads is decided by where the folder really goes: ask again for that name.
          const renamed = await planFolderMove(path, destination, persona, choice.newName)
          if (!renamed.ok) return void notify.error(renamed.error)
          if (renamed.clash) return void notify.error(`A folder named “${choice.newName}” already exists in ${destination || "the vault root"}.`)
          reach = renamed.reach
        }
        if (answers.ifExists === "merge" && plan.noteClashes.length > 0) {
          if (!(await prompt<boolean>((resolve) => ({ kind: "notes", files: plan.noteClashes, resolve })))) return
          answers.renameClashingNotes = true
        }
      }
      if (reach.length > 0) {
        if (!(await prompt<boolean>((resolve) => ({ kind: "reach", reach, resolve })))) return
        answers.confirmReach = true
      }

      const res = await moveVaultFolder(path, destination, persona, answers)
      if (!res.ok) return void notify.error(res.error)
      const mine = selectedNote?.startsWith(`${path}/`) ? selectedNote.slice(path.length + 1) : undefined
      await after(path, res.path)
      if (mine !== undefined && answers.renameClashingNotes && plan.noteClashes.includes(mine)) noteRenamedAway()
      refreshVault()
      ;(res.relinkFailed > 0 ? notify.warning : notify.success)(res.detail)
    } finally {
      busy.current = false
    }
  }

  return { moveFolder, ask, closeAsk: () => setAsk(null) }
}
