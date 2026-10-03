import { BrainIcon } from "@hugeicons/core-free-icons"
import type { IconSvgElement } from "@hugeicons/react"

import { iconByName } from "@/lib/persona-icons"

/**
 * Persona roster — mirrors `profiles/*.yaml`. Samantha is the only persona
 * that ships as a product default (see `CLAUDE.md`'s project rules); any
 * other persona is a user's own local customization, resolved live from
 * `GET /api/personas` rather than hardcoded here (see `fetchPersonas`
 * below). Each entry has a stable accent + icon so the same identity reads
 * consistently across the vault and the nebula.
 *
 * `accent` is a CSS color expression consumed as an inline custom property
 * (`--persona-accent`) rather than a Tailwind class, because personas are
 * user-extensible at runtime and cannot all be enumerated at build time.
 */
export type PersonaTier = "cloud" | "local"

export interface Persona {
  handle: string
  name: string
  title: string
  tier: PersonaTier
  /** Backend model family shown in the muted model chip. */
  model: string
  icon: IconSvgElement
  /** Light-mode accent (oklch). */
  accent: string
  /** Dark-mode accent (oklch). */
  accentDark: string
}

export const PERSONAS: Record<string, Persona> = {
  samantha: {
    handle: "samantha",
    name: "Samantha",
    title: "Vault Companion",
    tier: "cloud",
    model: "claude-sonnet-5",
    icon: BrainIcon,
    accent: "oklch(0.55 0.13 233)",
    accentDark: "oklch(0.78 0.13 220)",
  },
}

export const PERSONA_LIST: Persona[] = Object.values(PERSONAS)

export function getPersona(handle: string): Persona | undefined {
  return PERSONAS[handle.replace(/^@/, "").toLowerCase()]
}

/**
 * Live roster row from `GET /api/personas` — the backend's trimmed profile
 * projection. Identity + model + skills only; visuals (icon, accent) are not
 * a backend concern and are resolved client-side via `resolvePersonaVisuals`.
 */
export interface LivePersona {
  handle: string
  name: string
  title: string
  model: string
  skills: string[]
  isDefault: boolean
  /** Her look, from her `persona.yaml` (docs/decisions/062): the name of her icon in the icon set, and her colour
   *  in light and dark. Any may be missing. */
  icon?: string
  accent?: string
  accentDark?: string
}

interface PersonasResponse {
  default: string
  personas: Array<{
    handle: string
    name: string
    title: string
    model: string
    skills: string[]
    is_default: boolean
    icon?: string | null
    accent?: string | null
    accent_dark?: string | null
  }>
}

/**
 * Fetch the live persona roster. Falls back to the static `PERSONA_LIST` when
 * the backend is unreachable (offline dev), so the picker always renders.
 */
export async function fetchPersonas(): Promise<LivePersona[]> {
  try {
    const res = await fetch("/api/personas")
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = (await res.json()) as PersonasResponse
    const roster = data.personas.map((p) => ({
      handle: p.handle,
      name: p.name,
      title: p.title,
      model: p.model,
      skills: p.skills ?? [],
      isDefault: p.is_default,
      icon: p.icon ?? undefined,
      accent: p.accent ?? undefined,
      accentDark: p.accent_dark ?? undefined,
    }))
    setLiveLooks(roster)
    return roster
  } catch (err) {
    console.info(
      `[personas] /api/personas unreachable (${err}) — using the static roster`
    )
    return PERSONA_LIST.map((p) => ({
      handle: p.handle,
      name: p.name,
      title: p.title,
      model: p.model,
      skills: [],
      isDefault: p.handle === "samantha",
    }))
  }
}

/** Neutral visuals for a handle not in the curated static roster. */
const DEFAULT_VISUALS = {
  icon: BrainIcon,
  accent: "oklch(0.58 0.02 260)",
  accentDark: "oklch(0.72 0.02 260)",
} as const

type Look = { icon?: string; accent?: string; accentDark?: string }

/** What each persona's file says about her look, as the last roster read it (docs/decisions/062). Read by every
 *  place that draws her, so the roster is fetched once and nothing needs to pass her look down. */
let liveLooks = new Map<string, Look>()

const key = (handle: string) => handle.replace(/^@/, "").toLowerCase()

/** Remembers the look each persona's file names; the next draw of her uses it. */
export function setLiveLooks(roster: LivePersona[]): void {
  liveLooks = new Map(roster.map((p) => [key(p.handle), { icon: p.icon, accent: p.accent, accentDark: p.accentDark }]))
}

/** Icon + light/dark accent for a persona: what her `persona.yaml` names, else the curated default for a persona
 *  that ships, else neutral. A colour given for light only is used for dark too. */
export function resolvePersonaVisuals(handle: string): {
  icon: IconSvgElement
  accent: string
  accentDark: string
} {
  const base = getPersona(handle) ?? DEFAULT_VISUALS
  const look = liveLooks.get(key(handle))
  const accent = look?.accent ?? base.accent
  return {
    icon: iconByName(look?.icon) ?? base.icon,
    accent,
    accentDark: look?.accentDark ?? (look?.accent ? look.accent : base.accentDark),
  }
}
