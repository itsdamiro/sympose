import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/personas/{handle}/skills` — the skills a persona could carry, one read before it is switched
 * on, a folder added by its path (copied in, off) and a skill switched on or off (docs/decisions/077, the amendment of
 * 2026-10-14). The backend holds every rule (what a skill may be, where it is kept), so this only asks and reports.
 */
export interface Skill {
  name: string
  description: string
  /** The user's own, as against one that ships with Sympose. */
  own: boolean
  enabled: boolean
  /** Characters of the steps, and the most that is sent with a message. */
  length: number
  cap: number
  /** What the skill needs the persona to be able to do, by the engine's names. */
  tools: string[]
}

export interface SkillText extends Skill {
  /** `SKILL.md` exactly as stored. */
  text: string
}

export type SkillsResult = { ok: true; skills: Skill[] } | { ok: false; error: string }
export type SkillResult = { ok: true; skill: Skill } | { ok: false; error: string }
export type SkillTextResult = { ok: true; skill: SkillText } | { ok: false; error: string }
export type AddResult = { ok: true; skill: Skill; leftOut: number } | { ok: false; error: string }

const BACKEND_DOWN = "Sympose isn't responding. Check that it's still running, then try again."
const base = (persona: string) => `/api/personas/${encodeURIComponent(persona)}/skills`
const failed = async (res: Response, what: string) =>
  (await detailOf(res)) || `Couldn't ${what} (code ${res.status}). Try again.`

/** `GET /api/personas/{handle}/skills`. */
export async function fetchSkills(persona: string): Promise<SkillsResult> {
  try {
    const res = await fetch(base(persona))
    if (!res.ok) return { ok: false, error: await failed(res, "load the skills") }
    return { ok: true, skills: ((await res.json()) as { skills: Skill[] }).skills }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `GET /api/personas/{handle}/skills/{name}`: the skill and its text, to read before it is switched on. */
export async function readSkill(persona: string, name: string): Promise<SkillTextResult> {
  try {
    const res = await fetch(`${base(persona)}/${encodeURIComponent(name)}`)
    if (!res.ok) return { ok: false, error: await failed(res, `read ${name}`) }
    return { ok: true, skill: (await res.json()) as SkillText }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `POST /api/personas/{handle}/skills`: copy the skill at this folder path in, off. `leftOut` counts what else was in it. */
export async function addSkill(persona: string, folder: string): Promise<AddResult> {
  try {
    const res = await fetch(base(persona), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder }),
    })
    if (!res.ok) return { ok: false, error: await failed(res, "add the skill") }
    const body = (await res.json()) as { skill: Skill; left_out: number }
    return { ok: true, skill: body.skill, leftOut: body.left_out }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `PUT /api/personas/{handle}/skills/{name}`: switch it on or off; answers with the skill now. */
export async function switchSkill(persona: string, name: string, enabled: boolean): Promise<SkillResult> {
  try {
    const res = await fetch(`${base(persona)}/${encodeURIComponent(name)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    })
    if (!res.ok) return { ok: false, error: await failed(res, `change ${name}`) }
    return { ok: true, skill: ((await res.json()) as { skill: Skill }).skill }
  } catch {
    return { ok: false, error: `Couldn't change ${name}: ${BACKEND_DOWN}` }
  }
}
