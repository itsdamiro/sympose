import * as React from "react"

import { notify } from "@/lib/notify"
import { chooseModel, fetchModels, type ModelsState } from "@/lib/models-api"

/**
 * The persona's model and the ones on offer (docs/decisions/044), read when the persona changes. A choice is
 * saved on the persona by the backend and the state replaced with what it reports; a refused or failed save is
 * an error toast and the state stays as it was. `state` is `null` until known, or when the backend cannot say.
 */
export function useModels(persona: string | null | undefined) {
  const [loaded, setLoaded] = React.useState<{ persona: string; state: ModelsState } | null>(null)

  React.useEffect(() => {
    if (!persona) return
    let cancelled = false
    void fetchModels(persona).then((result) => {
      if (!cancelled && result.ok) setLoaded({ persona, state: result.state })
    })
    return () => {
      cancelled = true
    }
  }, [persona])

  /** Resolves `true` once saved. */
  const choose = React.useCallback(
    async (model: string | null): Promise<boolean> => {
      if (!persona) return false
      const result = await chooseModel(persona, model)
      if (!result.ok) {
        notify.error(result.error)
        return false
      }
      setLoaded({ persona, state: result.state })
      return true
    },
    [persona]
  )

  // A state read for another persona is not this persona's until its own read arrives.
  const state = loaded && loaded.persona === persona ? loaded.state : null
  return { state, choose }
}
