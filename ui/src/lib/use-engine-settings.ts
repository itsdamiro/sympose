import * as React from "react"

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

  const change = React.useCallback(
    async (key: string, value: boolean | string | number | null): Promise<boolean> => {
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
    },
    []
  )

  return { state, change }
}
