import * as React from "react"

import { notify } from "@/lib/notify"
import { changeSharing, fetchSharing, type SharingState } from "@/lib/sharing-api"

/**
 * What the persona's model may receive (docs/decisions/044, 031), read when the persona changes and changed
 * one category at a time. `state` is `null` until known, or when the backend cannot say: the chat then shows
 * no notice, and the engine's own gate still holds back whatever was not approved. A failed save is an error
 * toast and the row keeps what the backend last reported.
 */
export function useSharing(persona: string | null | undefined) {
  const [loaded, setLoaded] = React.useState<{ persona: string; state: SharingState } | null>(null)

  React.useEffect(() => {
    if (!persona) return
    let cancelled = false
    void fetchSharing(persona).then((result) => {
      if (!cancelled && result.ok) setLoaded({ persona, state: result.state })
    })
    return () => {
      cancelled = true
    }
  }, [persona])

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
