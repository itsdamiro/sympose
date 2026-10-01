import { type PrefSpec, useCookiePreferences } from "@/lib/cookie-preferences"

export type EditorSurface = "in-place" | "source"
export type EditorReveal = "caret" | "never"
export type EditorSelectionUI = "menu" | "bar"
export type EditorTableEditing = "source" | "cells"
export type EditorFocusOutline = "on" | "off"
export type EditorAutosave = "on" | "off"
export type EditorHideExtension = "on" | "off"

export interface EditorPreferences {
  surface: EditorSurface
  reveal: EditorReveal
  selectionUI: EditorSelectionUI
  /** How the in-place canvas edits a table (stylo's `TableEditing`).
   *  `"source"` (default) reveals the aligned pipe source under the caret;
   *  `"cells"` edits the rendered table in place. Only meaningful when
   *  `surface` is `"in-place"`. */
  tableEditing: EditorTableEditing
  focusOutline: EditorFocusOutline
  /**
   * Persist body/frontmatter edits to the vault automatically, a beat after
   * typing stops. `"off"` (default) leaves saving to the toolbar
   * button and `⌘/Ctrl-S`.
   */
  autosave: EditorAutosave
  /** Hide the trailing `.md` on note labels in the vault tree and main menu.
   *  `"on"` (default) matches Obsidian's own convention. */
  hideExtension: EditorHideExtension
}

const SPEC: PrefSpec<EditorPreferences> = {
  surface: { cookie: "sympose:editor.surface", kind: "enum", default: "in-place", values: ["in-place", "source"] },
  reveal: { cookie: "sympose:editor.reveal", kind: "enum", default: "caret", values: ["caret", "never"] },
  selectionUI: { cookie: "sympose:editor.selection_ui", kind: "enum", default: "menu", values: ["menu", "bar"] },
  tableEditing: { cookie: "sympose:editor.table_editing", kind: "enum", default: "source", values: ["source", "cells"] },
  focusOutline: { cookie: "sympose:editor.focus_outline", kind: "enum", default: "off", values: ["on", "off"] },
  autosave: { cookie: "sympose:editor.autosave", kind: "enum", default: "off", values: ["on", "off"] },
  hideExtension: { cookie: "sympose:editor.hide_extension", kind: "enum", default: "on", values: ["on", "off"] },
}

/**
 * The markdown panel's editing preferences — cookie-backed, not localStorage,
 * and not a backend/persona-configuration knob: these are per-browser
 * editing behavior only.
 */
export function useEditorPreferences() {
  return useCookiePreferences(SPEC)
}
