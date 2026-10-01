import { defaultsOf, type PrefSpec, useCookiePreferences } from "@/lib/cookie-preferences"
import type { NebulaMode } from "@/components/sympose/knowledge-nebula-shared"

/**
 * Explore = the nebula is sharp and interactive, foreground panels give way to
 * it. Focus = it falls back to a dimmed ambient layer with no pointer
 * interaction so you can work over it.
 */
export type NebulaInteraction = "explore" | "focus"

export interface NebulaPreferences {
  /** Sharp-and-interactive vs. dimmed-ambient. Default `"focus"` (work first). */
  interaction: NebulaInteraction
  /** `"2d"` flat canvas or `"3d"` WebGL cloud. Default `"2d"`. */
  mode: NebulaMode

  /** Show the folder-colour legend in Explore. */
  legend: boolean
  /** Show the floating control dock in Explore. Default `true`; now that
   *  every dock knob is also reachable from Settings → Knowledge Nebula
   *  (`layout="inline"`), this lets an unobstructed Explore view be the
   *  common case instead of the dock always covering a corner of it. */
  dock: boolean

  // Filters
  tags: boolean
  attachments: boolean
  existingOnly: boolean
  orphans: boolean

  // Display
  arrows: boolean
  autoRotate: boolean
  labels: boolean
  nodeSeparation: number
  nodeVividness: number
  nodeRelSize: number
  linkWidth: number
  clickZoomDistance: number
  /**
   * Focus-mode scrim — how the graph is hidden behind the panels. No effect in
   * Explore.
   *   `focusBlur` — backdrop-blur radius in px (`0` = sharp).
   *   `focusTint` — matte `--background` fill opacity over it (`0` = clear,
   *   `1` = solid); reads as darkening in a dark theme, lightening in a light one.
   */
  focusBlur: number
  focusTint: number
  /** The shell panels over the nebula in Focus — fill opacity (`1` = the usual
   *  solid surface); no backdrop blur (opacity alone reads
   *  clearly and the blur read as visual noise against the Focus scrim). */
  panelOpacity: number

  // Forces
  centerForce: number
  repelForce: number
  linkForce: number
  linkDistance: number
}

/**
 * One declaration per knob (see `cookie-preferences`), so the read and write
 * paths derive from a single source rather than two hand-kept lists. Every
 * knob is persisted; which ones the control dock actually exposes is a
 * separate, smaller list in `nebula-controls.tsx`.
 */
const SPEC: PrefSpec<NebulaPreferences> = {
  interaction: {
    cookie: "sympose:nebula.interaction",
    kind: "enum",
    default: "focus",
    values: ["explore", "focus"],
  },
  mode: {
    cookie: "sympose:nebula.mode",
    kind: "enum",
    default: "2d",
    values: ["2d", "3d"],
  },
  legend: { cookie: "sympose:nebula.legend", kind: "bool", default: true },
  dock: { cookie: "sympose:nebula.dock", kind: "bool", default: true },
  tags: { cookie: "sympose:nebula.tags", kind: "bool", default: true },
  attachments: { cookie: "sympose:nebula.attachments", kind: "bool", default: false },
  existingOnly: { cookie: "sympose:nebula.existing_only", kind: "bool", default: false },
  orphans: { cookie: "sympose:nebula.orphans", kind: "bool", default: false },
  arrows: { cookie: "sympose:nebula.arrows", kind: "bool", default: false },
  autoRotate: { cookie: "sympose:nebula.auto_rotate", kind: "bool", default: false },
  labels: { cookie: "sympose:nebula.labels", kind: "bool", default: true },
  nodeSeparation: { cookie: "sympose:nebula.node_separation", kind: "num", default: 0 },
  nodeVividness: { cookie: "sympose:nebula.node_vividness", kind: "num", default: 0 },
  nodeRelSize: { cookie: "sympose:nebula.node_rel_size", kind: "num", default: 1.67 * 2.4 },
  linkWidth: { cookie: "sympose:nebula.link_width", kind: "num", default: 0.8 },
  clickZoomDistance: { cookie: "sympose:nebula.click_zoom_distance", kind: "num", default: 60 },
  focusBlur: { cookie: "sympose:nebula.focus_blur", kind: "num", default: 12 },
  focusTint: { cookie: "sympose:nebula.focus_tint", kind: "num", default: 0.8 },
  panelOpacity: { cookie: "sympose:nebula.panel_opacity", kind: "num", default: 1 },
  centerForce: { cookie: "sympose:nebula.center_force", kind: "num", default: 0.52 },
  repelForce: { cookie: "sympose:nebula.repel_force", kind: "num", default: 13.89 },
  linkForce: { cookie: "sympose:nebula.link_force", kind: "num", default: 1.0 },
  linkDistance: { cookie: "sympose:nebula.link_distance", kind: "num", default: 492 },
}

export const NEBULA_DEFAULTS = defaultsOf(SPEC)

/**
 * Every Knowledge Nebula knob, cookie-backed per the UI-preference convention
 * — per-browser view state, not backend/persona configuration. Threaded from
 * one call in the app shell the same way the editor and notification
 * preferences are, so a second hook instance can't hold a divergent copy.
 */
export function useNebulaPreferences() {
  return useCookiePreferences(SPEC)
}
