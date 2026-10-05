import * as React from "react"

import { askBeforeEditMode } from "@/lib/edit-mode-ask"
import { fetchGlobalEditMode } from "@/lib/edit-mode-api"
import { notify } from "@/lib/notify"
import {
  changeSetting,
  fetchSettings,
  type SettingsGroup,
} from "@/lib/settings-api"

export type EngineSettingsState =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; groups: SettingsGroup[] }

/**
 * The engine settings (docs/decisions/044), loaded once when the Settings panel opens and changed one row
 * at a time. A refused value is shown as an error toast and the row keeps what is in force; a saved one
 * replaces the row with what the backend now reports, so the screen never guesses.
 */
export function useEngineSettings() {
  const [state, setState] = React.useState<EngineSettingsState>({ status: "loading" })

  React.useEffect(() => {
    let cancelled = false
    void fetchSettings().then((result) => {
      if (cancelled) return
      setState(result.ok ? { status: "ready", groups: result.groups } : { status: "error", error: result.error })
    })
    return () => {
      cancelled = true
    }
  }, [])

  const save = React.useCallback(async (key: string, value: boolean | string | number | null): Promise<boolean> => {
    const result = await changeSetting(key, value)
    if (!result.ok) {
      notify.error(result.error)
      return false
    }
    setState((prev) =>
      prev.status !== "ready"
        ? prev
        : {
            status: "ready",
            groups: prev.groups.map((g) => ({
              ...g,
              settings: g.settings.map((s) => (s.key === key ? result.setting : s)),
            })),
          }
    )
    return true
  }, [])

  // The global edit mode (docs/decisions/072): `accept` and `auto` first show the note about the models of the personas
  // that follow it, so the row keeps what is in force until the user confirms (`false` here means "asked, not saved").
  const change = React.useCallback(
    async (key: string, value: boolean | string | number | null): Promise<boolean> => {
      if (key === "edit_mode" && (value === "accept" || value === "auto")) {
        const note = (await fetchGlobalEditMode())?.notes[value]
        if (note) {
          askBeforeEditMode({ mode: value, who: null, note, apply: () => save(key, value) })
          return false
        }
      }
      return save(key, value)
    },
    [save]
  )

  return { state, change }
}
