import * as React from "react"

import { confirm } from "@/lib/confirm-store"
import { fetchEditMode, saveEditMode, type EditModeId, type EditModeInfo } from "@/lib/edit-mode-api"
import { notify } from "@/lib/notify"
import { getNotificationPreferences } from "@/lib/use-notification-preferences"

const ASKS: Partial<Record<EditModeId, { message: (name: string) => string; confirmLabel: string }>> = {
  accept: { message: (name) => `Let ${name} apply her edits in the editor?`, confirmLabel: "Use Accept edits" },
  auto: { message: (name) => `Let ${name} act on her own initiative?`, confirmLabel: "Use Auto" },
}

/**
 * The active persona's edit mode (docs/decisions/072) for the persona page's chip. Read when the persona changes.
 * `choose` saves her own mode (`null` clears it). `accept` and `auto` first show the note about the model she uses,
 * in the way the user's Notifications settings say a question is asked (the dialog, or the one-line form); with
 * confirmations set to none the choice is applied at once and the same note is shown as a notice, so the figures are
 * never silently skipped. Only the newest read is kept, and another persona's mode is never shown for this one.
 */
export function useEditMode(handle: string, personaName: string) {
  const [loaded, setLoaded] = React.useState<{ handle: string; info: EditModeInfo } | null>(null)
  const info = loaded?.handle === handle ? loaded.info : null

  React.useEffect(() => {
    let cancelled = false
    void fetchEditMode(handle).then((next) => {
      if (!cancelled && next) setLoaded({ handle, info: next })
    })
    return () => {
      cancelled = true
    }
  }, [handle])

  const apply = React.useCallback(
    async (mode: EditModeId | null) => {
      const result = await saveEditMode(handle, mode)
      if (result.ok) setLoaded({ handle, info: result.info })
      else notify.error(`Couldn't save the edit mode: ${result.error}`)
      return result.ok
    },
    [handle]
  )

  const choose = React.useCallback(
    (mode: EditModeId | null) => {
      const ask = mode ? ASKS[mode] : undefined
      const note = mode && info ? info.notes[mode as "accept" | "auto"] : null
      if (!ask || !note) return void apply(mode)
      if (getNotificationPreferences().confirm === "none") {
        void apply(mode).then((ok) => ok && notify.warning(note, { duration: 12000 }))
        return
      }
      confirm({ message: ask.message(personaName), description: note, confirmLabel: ask.confirmLabel, tone: "default", onConfirm: () => void apply(mode) })
    },
    [info, personaName, apply]
  )

  return { info, choose }
}
