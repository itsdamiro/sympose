import * as React from "react"

import { notify } from "@/lib/notify"
import { addSkill, fetchSkills, removeSkill, switchSkill, type Skill } from "@/lib/skills-api"

export type SkillsState =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; skills: Skill[] }

const byName = (a: Skill, b: Skill) => a.name.localeCompare(b.name)

/**
 * The persona's skills (docs/decisions/077), read when the persona changes, a folder added, each switched on or off and one of the user's own removed.
 * A refusal is an error toast and the list keeps what the backend last said, so the screen never guesses; what a
 * save answers replaces that skill's row.
 */
export function useSkills(persona: string | null | undefined) {
  const [loaded, setLoaded] = React.useState<{ persona: string; state: SkillsState } | null>(null)

  React.useEffect(() => {
    if (!persona) return
    let cancelled = false
    void fetchSkills(persona).then((result) => {
      if (cancelled) return
      const state: SkillsState = result.ok ? { status: "ready", skills: result.skills } : { status: "error", error: result.error }
      setLoaded({ persona, state })
    })
    return () => {
      cancelled = true
    }
  }, [persona])

  const replace = React.useCallback(
    (forPersona: string, skill: Skill) =>
      setLoaded((prev) => {
        if (!prev || prev.persona !== forPersona || prev.state.status !== "ready") return prev
        const others = prev.state.skills.filter((s) => s.name !== skill.name)
        return { persona: forPersona, state: { status: "ready", skills: [...others, skill].sort(byName) } }
      }),
    []
  )

  /** Copy the skill at `folder` in; the added skill (off) and how many other things sat in the folder, or `null` if refused. */
  const add = React.useCallback(
    async (folder: string) => {
      if (!persona) return null
      const result = await addSkill(persona, folder)
      if (!result.ok) {
        notify.error(result.error)
        return null
      }
      replace(persona, result.skill)
      return { skill: result.skill, leftOut: result.leftOut }
    },
    [persona, replace]
  )

  const setEnabled = React.useCallback(
    async (name: string, enabled: boolean) => {
      if (!persona) return false
      const result = await switchSkill(persona, name, enabled)
      if (!result.ok) {
        notify.error(result.error)
        return false
      }
      replace(persona, result.skill)
      return true
    },
    [persona, replace]
  )

  /** Delete one of the user's own skills; its row goes only once the backend has done it. */
  const remove = React.useCallback(
    async (name: string) => {
      if (!persona) return false
      const result = await removeSkill(persona, name)
      if (!result.ok) {
        notify.error(result.error)
        return false
      }
      setLoaded((prev) =>
        prev && prev.persona === persona && prev.state.status === "ready"
          ? { persona, state: { status: "ready", skills: prev.state.skills.filter((s) => s.name !== name) } }
          : prev
      )
      return true
    },
    [persona]
  )

  // A state read for another persona is not this persona's until its own read arrives.
  const state: SkillsState = loaded && loaded.persona === persona ? loaded.state : { status: "loading" }
  return { state, add, setEnabled, remove }
}
