import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/personas/{handle}/jobs`: a persona's scheduled jobs (docs/decisions/091) listed with how each last ran,
 * one switched on or off, a new one made from the template, one renamed and one deleted. A job's file is edited through the persona-file routes
 * (`file` names it there). The backend holds every rule; this only asks and reports.
 */
export interface Job {
  name: string
  /** The name the persona-file routes know the job's file by, `jobs/<name>.md`. */
  file: string
  /** The schedule in the user's words, as written in the file; empty when there is none. */
  schedule: string
  kind: string
  /** Runs without a model (the vault check, the search index). */
  mechanical: boolean
  /** The model a run uses, `null` for a job that calls none. */
  model: string | null
  /** The model written in the job's file, or `null` when it uses the persona's. */
  own_model: string | null
  cloud: boolean
  enabled: boolean
  /** The first thing wrong with the file, else `null`: such a job never runs. */
  problem: string | null
  /** Stopped itself after failing three times in a row. */
  paused: boolean
  failures: number
  /** When it last ran, in the user's own clock, else `null`. */
  last_run: string | null
  outcome: "ok" | "failed" | null
  /** Why the last run failed, or what a cloud model was not given. */
  detail: string
  /** The conversation the last run opened. */
  session_id: string | null
}

export type JobsResult = { ok: true; jobs: Job[] } | { ok: false; error: string }
export type JobResult = { ok: true; job: Job } | { ok: false; error: string }

const BACKEND_DOWN = "Sympose isn't responding. Check that it's still running, then try again."
const base = (persona: string) => `/api/personas/${encodeURIComponent(persona)}/jobs`
const failed = async (res: Response, what: string) => (await detailOf(res)) || `Couldn't ${what} (code ${res.status}). Try again.`

/** `GET /api/personas/{handle}/jobs`. */
export async function fetchJobs(persona: string): Promise<JobsResult> {
  try {
    const res = await fetch(base(persona))
    if (!res.ok) return { ok: false, error: await failed(res, "load the jobs") }
    return { ok: true, jobs: ((await res.json()) as { jobs: Job[] }).jobs }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `POST /api/personas/{handle}/jobs`: a new job from the template, off. */
export async function createJob(persona: string): Promise<JobResult> {
  try {
    const res = await fetch(base(persona), { method: "POST" })
    if (!res.ok) return { ok: false, error: await failed(res, "make the job") }
    return { ok: true, job: ((await res.json()) as { job: Job }).job }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `PUT /api/personas/{handle}/jobs/{name}`: switch it on or off (on also lifts a pause); answers with the job now. */
export async function switchJob(persona: string, name: string, enabled: boolean): Promise<JobResult> {
  try {
    const res = await fetch(`${base(persona)}/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    })
    if (!res.ok) return { ok: false, error: await failed(res, `change ${name}`) }
    return { ok: true, job: ((await res.json()) as { job: Job }).job }
  } catch {
    return { ok: false, error: `Couldn't change ${name}: ${BACKEND_DOWN}` }
  }
}

/** `PUT /api/personas/{handle}/jobs/{name}/model`: the job's own model, or `null` to use the persona's; answers with the job now. */
export async function chooseJobModel(persona: string, name: string, model: string | null): Promise<JobResult> {
  try {
    const res = await fetch(`${base(persona)}/${encodeURIComponent(name)}/model`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    })
    if (!res.ok) return { ok: false, error: await failed(res, `change the model of ${name}`) }
    return { ok: true, job: ((await res.json()) as { job: Job }).job }
  } catch {
    return { ok: false, error: `Couldn't change the model of ${name}: ${BACKEND_DOWN}` }
  }
}

/** `POST /api/personas/{handle}/jobs/{name}/rename`: the job under its new name (the backend makes it a file name). */
export async function renameJob(persona: string, name: string, newName: string): Promise<JobResult> {
  try {
    const res = await fetch(`${base(persona)}/${encodeURIComponent(name)}/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    })
    if (!res.ok) return { ok: false, error: await failed(res, `rename ${name}`) }
    return { ok: true, job: ((await res.json()) as { job: Job }).job }
  } catch {
    return { ok: false, error: `Couldn't rename ${name}: ${BACKEND_DOWN}` }
  }
}

/** `DELETE /api/personas/{handle}/jobs/{name}`: the job goes; its file is kept beside the others as a backup. */
export async function deleteJob(persona: string, name: string): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const res = await fetch(`${base(persona)}/${encodeURIComponent(name)}`, { method: "DELETE" })
    if (!res.ok) return { ok: false, error: await failed(res, `delete ${name}`) }
    return { ok: true }
  } catch {
    return { ok: false, error: `Couldn't delete ${name}: ${BACKEND_DOWN}` }
  }
}
