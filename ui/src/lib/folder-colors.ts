/**
 * The colours the Folder settings dialog offers a folder (docs/decisions/087): each is a pair, a deep tone for the
 * light theme and a bright one for the dark, as the Knowledge Nebula draws a folder's `accent` and `accent_dark`.
 * They are the tones the built-in folders have always had; any other pair can be set with the two colour inputs.
 */
export interface ColorPreset {
  name: string
  light: string
  dark: string
}

export const COLOR_PRESETS: ColorPreset[] = [
  { name: "Cyan", light: "#0284c7", dark: "#56c9e0" },
  { name: "Mint", light: "#059669", dark: "#6fdcb0" },
  { name: "Amber", light: "#b45309", dark: "#e7c14a" },
  { name: "Violet", light: "#7c3aed", dark: "#b98cff" },
  { name: "Rose", light: "#be123c", dark: "#f2889b" },
  { name: "Orange", light: "#c2410c", dark: "#f0a35a" },
  { name: "Blue", light: "#1d4ed8", dark: "#7aa7e0" },
  { name: "Teal", light: "#0f766e", dark: "#5fc7c7" },
  { name: "Magenta", light: "#a21caf", dark: "#e07ac0" },
  { name: "Slate", light: "#334155", dark: "#9aa7bd" },
]

/** The preset whose pair is exactly `light` and `dark` (hex, any case), or `undefined`. */
export function presetFor(light: string | null, dark: string | null): ColorPreset | undefined {
  if (!light || !dark) return undefined
  return COLOR_PRESETS.find((p) => p.light === light.toLowerCase() && p.dark === dark.toLowerCase())
}

function toHsl(hex: string): [number, number, number] {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = d / (1 - Math.abs(2 * l - 1))
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  return [(h * 60 + 360) % 360, s, l]
}

function fromHsl(h: number, s: number, l: number): string {
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  const [r, g, b] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x]
  return "#" + [r, g, b].map((v) => Math.round((v + m) * 255).toString(16).padStart(2, "0")).join("")
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

/**
 * The colour a person picks for one theme, turned into the matching one for the other (docs/decisions/087): the
 * same hue, brighter and a little softer for the dark theme, deeper and a little stronger for the light one, in the
 * ranges the built-in presets use, so one pick is enough. `from` is the theme `hex` is for. A grey stays a grey.
 */
export function counterpart(hex: string, from: "light" | "dark"): string {
  const [h, s, l] = toHsl(hex)
  return from === "light"
    ? fromHsl(h, s * 0.8, clamp(l + 0.28, 0.6, 0.78))
    : fromHsl(h, Math.min(s * 1.2, 0.95), clamp(l - 0.28, 0.25, 0.42))
}
