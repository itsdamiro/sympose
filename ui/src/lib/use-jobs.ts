import * as React from "react"

import { notify } from "@/lib/notify"
import { chooseJobModel, createJob, deleteJob, fetchJobs, renameJob, switchJob, type Job } from "@/lib/jobs-api"

export type JobsState =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; jobs: Job[] }

const byName = (a: Job, b: Job) => a.name.localeCompare(b.name)

/**
 * The persona's scheduled jobs (docs/decisions/091), read when the persona changes and again when `version` does (the
 * editor saved a job's file), one switched on or off, given a model, a new one made, one renamed and one deleted. A refusal is an error toast and the list
 * keeps what the backend last said, so the screen never guesses; what a change answers replaces that job's row.
 */
export function useJobs(persona: string | null | undefined, version = 0) {
  const [loaded, setLoaded] = React.useState<{ persona: string; state: JobsState } | null>(null)

  React.useEffect(() => {
    if (!persona) return
    let cancelled = false
    void fetchJobs(persona).then((result) => {
      if (cancelled) return
      const state: JobsState = result.ok ? { status: "ready", jobs: result.jobs } : { status: "error", error: result.error }
      setLoaded({ persona, state })
    })
    return () => {
      cancelled = true
    }
  }, [persona, version])

  const replace = React.useCallback(
    (forPersona: string, job: Job) =>
      setLoaded((prev) => {
        if (!prev || prev.persona !== forPersona || prev.state.status !== "ready") return prev
        const others = prev.state.jobs.filter((j) => j.name !== job.name)
        return { persona: forPersona, state: { status: "ready", jobs: [...others, job].sort(byName) } }
      }),
    []
  )

  const setEnabled = React.useCallback(
    async (name: string, enabled: boolean) => {
      if (!persona) return false
      const result = await switchJob(persona, name, enabled)
      if (!result.ok) {
        notify.error(result.error)
        return false
      }
      replace(persona, result.job)
      return true
    },
    [persona, replace]
  )

  /** Give a job its own model, or `null` for the persona's; `true` once saved. */
  const setModel = React.useCallback(
    async (name: string, model: string | null) => {
      if (!persona) return false
      const result = await chooseJobModel(persona, name, model)
      if (!result.ok) {
        notify.error(result.error)
        return false
      }
      replace(persona, result.job)
      return true
    },
    [persona, replace]
  )

  /** Make a job from the template; the new job, or `null` if refused. */
  const add = React.useCallback(async () => {
    if (!persona) return null
    const result = await createJob(persona)
    if (!result.ok) {
      notify.error(result.error)
      return null
    }
    replace(persona, result.job)
    return result.job
  }, [persona, replace])

  /** Rename a job; the job under its new name, or `null` if refused. Its old row goes only once the backend has done it. */
  const rename = React.useCallback(
    async (name: string, newName: string) => {
      if (!persona) return null
      const result = await renameJob(persona, name, newName)
      if (!result.ok) {
        notify.error(result.error)
        return null
      }
      setLoaded((prev) =>
        prev && prev.persona === persona && prev.state.status === "ready"
          ? { persona, state: { status: "ready", jobs: [...prev.state.jobs.filter((j) => j.name !== name && j.name !== result.job.name), result.job].sort(byName) } }
          : prev
      )
      return result.job
    },
    [persona]
  )

  /** Delete a job; its row goes only once the backend has done it. */
  const remove = React.useCallback(
    async (name: string) => {
      if (!persona) return false
      const result = await deleteJob(persona, name)
      if (!result.ok) {
        notify.error(result.error)
        return false
      }
      setLoaded((prev) =>
        prev && prev.persona === persona && prev.state.status === "ready"
          ? { persona, state: { status: "ready", jobs: prev.state.jobs.filter((j) => j.name !== name) } }
          : prev
      )
      return true
    },
    [persona]
  )

  // A state read for another persona is not this persona's until its own read arrives.
  const state: JobsState = loaded && loaded.persona === persona ? loaded.state : { status: "loading" }
  return { state, setEnabled, setModel, add, rename, remove }
}
