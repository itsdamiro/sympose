import {
  MENU_ACCOUNT_ID,
  MENU_SETTINGS_ID,
  MENU_TRASH_ID,
} from "@/components/sympose"

/** Labels for the non-folder sections the footer rows can select. */
export const SECTION_LABELS: Record<string, string> = {
  [MENU_SETTINGS_ID]: "Settings",
  [MENU_ACCOUNT_ID]: "Persona",
  [MENU_TRASH_ID]: "Bin",
}

/** Settings, Persona and the Bin are sections of the app, not folders of the vault. */
export function isSentinelSection(id: string): boolean {
  return id === MENU_SETTINGS_ID || id === MENU_ACCOUNT_ID || id === MENU_TRASH_ID
}

/** The section in view after the folder `oldFolder` was renamed or moved to `newFolder` (docs/decisions/073, 074): a
 *  root folder that was in view stays in view under its new name, and when it went inside another folder the section
 *  is that one's root, since only root folders are sections. Any other section stays. */
export function sectionAfterFolderMove(active: string, oldFolder: string, newFolder: string): string {
  return active === oldFolder ? newFolder.split("/")[0] : active
}
