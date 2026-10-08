import * as React from "react"

import { fetchEditMode, saveEditMode, type EditModeId, type EditModeInfo } from "@/lib/edit-mode-api"
import { notify } from "@/lib/notify"
import { askBeforeEditMode } from "@/lib/edit-mode-ask"
import { SETTINGS_CHANGED } from "@/lib/settings-changed"

const CHANGED = "sympose:edit-mode-changed"

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

  const [again, setAgain] = React.useState(0)
  const me = React.useRef({}) // this hook's identity, so it does not re-read a change it made itself

  React.useEffect(() => {
    let cancelled = false
    void fetchEditMode(handle).then((next) => {
      if (!cancelled && next) setLoaded({ handle, info: next })
    })
    return () => {
      cancelled = true
    }
  }, [handle, again])

  // Every reader of the mode follows a change made elsewhere: another part of the app (the Persona page's chip while a
  // note is open in the editor) or another window or the terminal (seen when the window is focused again).
  React.useEffect(() => {
    const read = () => setAgain((n) => n + 1)
    const changed = (e: Event) => (e as CustomEvent).detail !== me.current && read()
    window.addEventListener(CHANGED, changed)
    window.addEventListener("focus", read)
    window.addEventListener(SETTINGS_CHANGED, read)
    return () => {
      window.removeEventListener(CHANGED, changed)
      window.removeEventListener("focus", read)
      window.removeEventListener(SETTINGS_CHANGED, read)
    }
  }, [])

  const apply = React.useCallback(
    async (mode: EditModeId | null) => {
      const result = await saveEditMode(handle, mode)
      if (result.ok) {
        setLoaded({ handle, info: result.info })
        window.dispatchEvent(new CustomEvent(CHANGED, { detail: me.current }))
      }
      else notify.error(`Couldn't save the edit mode: ${result.error}`)
      return result.ok
    },
    [handle]
  )

  const choose = React.useCallback(
    (mode: EditModeId | null) =>
      askBeforeEditMode({ mode, who: personaName, note: mode && info ? info.notes[mode as "accept" | "auto"] : null, apply: () => apply(mode) }),
    [info, personaName, apply]
  )

  return { info, choose }
}
