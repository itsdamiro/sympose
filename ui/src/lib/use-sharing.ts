import * as React from "react"

import { notify } from "@/lib/notify"
import { SETTINGS_CHANGED } from "@/lib/settings-changed"
import { changeSharing, fetchSharing, type SharingState } from "@/lib/sharing-api"

/**
 * What the persona's model may receive (docs/decisions/044, 031), read when the persona changes and changed
 * one category at a time. `model` is only a reason to read again: a persona's model can change (the picker), and
 * what it may receive follows it. `state` is `null` until known, or when the backend cannot say: the chat then shows
 * no notice, and the engine's own gate still holds back whatever was not approved. A failed save is an error
 * toast and the row keeps what the backend last reported.
 */
export function useSharing(persona: string | null | undefined, model?: string | null) {
  const [loaded, setLoaded] = React.useState<{ persona: string; state: SharingState } | null>(null)
  const [again, setAgain] = React.useState(0)

  // A persona's request the user accepted may have changed what a cloud model may receive (docs/decisions/080).
  React.useEffect(() => {
    const read = () => setAgain((n) => n + 1)
    window.addEventListener(SETTINGS_CHANGED, read)
    return () => window.removeEventListener(SETTINGS_CHANGED, read)
  }, [])

  React.useEffect(() => {
    if (!persona) return
    let cancelled = false
    void fetchSharing(persona).then((result) => {
      if (!cancelled && result.ok) setLoaded({ persona, state: result.state })
    })
    return () => {
      cancelled = true
    }
  }, [persona, model, again])

  const setShared = React.useCallback(
    async (category: string, shared: boolean) => {
      if (!persona) return
      const result = await changeSharing(persona, category, shared)
      if (!result.ok) return void notify.error(result.error)
      setLoaded({ persona, state: result.state })
    },
    [persona]
  )

  // A state read for another persona is not this persona's until its own read arrives.
  const state = loaded && loaded.persona === persona ? loaded.state : null
  return { state, setShared }
}
