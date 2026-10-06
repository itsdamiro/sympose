import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/settings` — the engine settings the terminal's `/settings` lists too (docs/decisions/044).
 * The backend describes every row (its kind, value, default, choices, hint) and decides what is valid, so the
 * browser holds no rule of its own: it draws what comes back and shows the reason when a value is refused.
 */
export interface EngineSetting {
  key: string
  kind: "toggle" | "choice" | "number"
  summary: string
  /** The value in force: a boolean, a choice, or a number (`null` is "automatic"). */
  value: boolean | string | number | null
  /** What the setting gives when it is not set. */
  default: boolean | string | number | null
  isDefault: boolean
  /** The value as the terminal says it: `on`, `keywords`, `50 (default)`, `automatic`. */
  text: string
  choices: string[]
  hint: string
  whole: boolean
}

export interface SettingsGroup {
  name: string
  settings: EngineSetting[]
}

export type SettingsResult =
  | { ok: true; groups: SettingsGroup[] }
  | { ok: false; error: string }

export type ChangeResult =
  | { ok: true; setting: EngineSetting }
  | { ok: false; error: string }

interface RawSetting extends Omit<EngineSetting, "isDefault"> {
  is_default: boolean
}

const toSetting = ({ is_default, ...rest }: RawSetting): EngineSetting => ({
  ...rest,
  isDefault: is_default,
})

const BACKEND_DOWN = "Sympose isn't responding. Check that it's still running, then try again."

/** `GET /api/settings`. */
export async function fetchSettings(): Promise<SettingsResult> {
  try {
    const res = await fetch("/api/settings")
    if (!res.ok) return { ok: false, error: `Something failed on Sympose's side (code ${res.status}). Try again.` }
    const body = (await res.json()) as {
      groups: { name: string; settings: RawSetting[] }[]
    }
    return {
      ok: true,
      groups: body.groups.map((g) => ({ name: g.name, settings: g.settings.map(toSetting) })),
    }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `PUT /api/settings/{key}`; `value` `null` puts the setting back to its default. */
export async function changeSetting(
  key: string,
  value: boolean | string | number | null
): Promise<ChangeResult> {
  try {
    const res = await fetch(`/api/settings/${encodeURIComponent(key)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    })
    if (res.ok) {
      const body = (await res.json()) as { setting: RawSetting }
      return { ok: true, setting: toSetting(body.setting) }
    }
    return { ok: false, error: (await detailOf(res)) || `Couldn't save ${key} (code ${res.status}). Try again.` }
  } catch {
    return { ok: false, error: `Couldn't save ${key}: ${BACKEND_DOWN}` }
  }
}
