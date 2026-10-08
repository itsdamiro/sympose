import * as React from "react"

import { fetchPersonas, resolvePersonaVisuals, type LivePersona } from "@/lib/personas"

/**
 * The roster of personas (fetched once) beside the active one, which is client
 * state kept elsewhere (`useActivePersona`, a cookie). Feeds the Persona card, the
 * main menu's account row, which wears the active persona's name, icon and
 * accent, and the chat's header.
 *
 * - `rosterPersonas` is the roster with the active persona's model replaced by
 *   the one in use now, so the card follows a pick made in the chat.
 * - A persona cookie left over from a roster that has since shrunk (a persona
 *   removed as a shipped default, say) heals itself to the default persona,
 *   otherwise the account row is stuck showing a raw, unresolvable handle for
 *   good, since nothing else ever clears a stale cookie value.
 * - `activePersonaModel` is the roster's model for the active persona (the
 *   persona's own setting, not the pick in use).
 */
export function usePersonaRoster({
  activePersona,
  setActivePersona,
  modelInUse,
}: {
  activePersona: string
  setActivePersona: (handle: string) => void
  modelInUse: string | undefined
}) {
  const [personas, setPersonas] = React.useState<LivePersona[]>([])
  const [reads, setReads] = React.useState(0)
  React.useEffect(() => {
    let alive = true
    fetchPersonas().then((list) => {
      if (alive) setPersonas(list)
    })
    return () => {
      alive = false
    }
  }, [reads])
  const reload = React.useCallback(() => setReads((n) => n + 1), [])
  const rosterPersonas = React.useMemo(
    () => personas.map((p) => (p.handle === activePersona && modelInUse ? { ...p, model: modelInUse } : p)),
    [personas, activePersona, modelInUse]
  )
  React.useEffect(() => {
    if (personas.length === 0) return
    if (personas.some((p) => p.handle === activePersona)) return
    setActivePersona(personas.find((p) => p.isDefault)?.handle ?? personas[0].handle)
  }, [personas, activePersona, setActivePersona])

  const active = personas.find((p) => p.handle === activePersona)
  return {
    rosterPersonas,
    reloadRoster: reload,
    activePersonaName: active?.name ?? activePersona,
    activePersonaModel: active?.model,
    activePersonaVisuals: resolvePersonaVisuals(activePersona),
  }
}
