/**
 * Said when a setting was changed outside the part of the app that shows it (a persona's request the user accepted,
 * docs/decisions/080), so whatever reads that setting once, such as what a cloud model may receive or the edit mode, reads
 * it again.
 */
export const SETTINGS_CHANGED = "sympose:settings-changed"

export function announceSettingsChanged() {
  window.dispatchEvent(new Event(SETTINGS_CHANGED))
}
