import * as React from "react"

import type { Panels, StagePanel } from "@/lib/use-panels"

/**
 * The stage in front of the ambient Knowledge Nebula.
 *
 * - **Explore** collapses the stage panels (content, editor) so the whole canvas
 *   is click-through to the nebula underneath; the trip back to Focus reopens
 *   exactly what was showing, oldest-first, the same order `usePanels` keeps.
 *   A ref (not a `panels` dependency) reads the live panel handle, so this only
 *   acts on an actual mode change, not on every panel-order write `usePanels`
 *   makes.
 * - **`nebulaReady`** turns true once the browser is idle after first paint, so
 *   the nebula's renderer chunk (`react-force-graph`) never competes with the
 *   shell's time to first byte of content.
 */
export function useNebulaStage(panels: Panels, interaction: "explore" | "focus") {
  const panelsRef = React.useRef(panels)
  React.useEffect(() => {
    panelsRef.current = panels
  })
  const stashedPanels = React.useRef<StagePanel[] | null>(null)
  const prevInteraction = React.useRef(interaction)
  React.useEffect(() => {
    const was = prevInteraction.current
    prevInteraction.current = interaction
    if (was === interaction) return
    if (interaction === "explore") {
      stashedPanels.current = panelsRef.current.visible
      for (const p of panelsRef.current.visible) panelsRef.current.close(p)
    } else {
      const stash = stashedPanels.current
      stashedPanels.current = null
      stash?.forEach((p) => panelsRef.current.open(p))
    }
  }, [interaction])

  const [nebulaReady, setNebulaReady] = React.useState(false)
  React.useEffect(() => {
    const hasIdle = typeof window.requestIdleCallback === "function"
    const handle = hasIdle
      ? window.requestIdleCallback(() => setNebulaReady(true), {
          timeout: 2000,
        })
      : window.setTimeout(() => setNebulaReady(true), 400)
    return () => {
      if (hasIdle) window.cancelIdleCallback(handle as number)
      else window.clearTimeout(handle as number)
    }
  }, [])

  return { nebulaReady }
}
