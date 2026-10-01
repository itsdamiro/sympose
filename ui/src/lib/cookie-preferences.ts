import * as React from "react"

import { getCookie, setCookie } from "@/lib/cookies"
import { isOneOf } from "@/lib/utils"

/**
 * One declaration per cookie-backed interface preference — cookie name, default and how its value is
 * written — so the read and write paths of every preference hook derive from a single source instead of
 * each keeping its own hand-written lists. Per-browser view state, not backend configuration.
 *
 * - a `boolean` is stored as `"1"` / `"0"`;
 * - a `number` is stored as its text, and a cookie that is not a finite number falls back to the default;
 * - a string union lists its `values`: a stored value outside the list (an older build's renamed value,
 *   or a hand edit) falls back to the default instead of being cast blind.
 */
export type PrefField<V> = { cookie: string; default: V } & ([V] extends [boolean]
  ? { kind: "bool" }
  : [V] extends [number]
    ? { kind: "num" }
    : [V] extends [string]
      ? { kind: "enum"; values: readonly V[] }
      : never)

export type PrefSpec<T> = { [K in keyof T]: PrefField<T[K]> }

const keysOf = <T>(spec: PrefSpec<T>) => Object.keys(spec) as (keyof T)[]

export function defaultsOf<T>(spec: PrefSpec<T>): T {
  return Object.fromEntries(keysOf(spec).map((k) => [k, spec[k].default])) as T
}

function decode<V>(field: PrefField<V>, raw: string | null): V {
  if (raw == null) return field.default
  if (field.kind === "bool") return (raw === "1") as V
  if (field.kind === "num") {
    const n = Number(raw)
    return (Number.isFinite(n) ? n : field.default) as V
  }
  return isOneOf(raw, field.values as readonly string[]) ? (raw as V) : field.default
}

/** Every preference in `spec`, as the cookies hold them now. */
export function readPreferences<T>(spec: PrefSpec<T>): T {
  const out = {} as T
  for (const k of keysOf(spec)) out[k] = decode(spec[k], getCookie(spec[k].cookie))
  return out
}

/** Persist one preference. */
export function writePreference<T, K extends keyof T>(spec: PrefSpec<T>, key: K, value: T[K]): void {
  const field = spec[key] as PrefField<T[K]>
  setCookie(field.cookie, field.kind === "bool" ? (value ? "1" : "0") : String(value))
}

/**
 * The state and setter for one group of preferences. `spec` must be a module-level constant. Threaded from
 * one call site where several parts of the screen read the same group, so a second instance cannot hold a
 * divergent copy.
 */
export function useCookiePreferences<T>(spec: PrefSpec<T>): readonly [
  T,
  <K extends keyof T>(key: K, value: T[K]) => void,
] {
  const [prefs, setPrefs] = React.useState<T>(() => readPreferences(spec))
  const set = React.useCallback(
    <K extends keyof T>(key: K, value: T[K]) => {
      writePreference(spec, key, value)
      setPrefs((prev) => ({ ...prev, [key]: value }))
    },
    [spec]
  )
  return [prefs, set] as const
}
