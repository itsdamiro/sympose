import { describe, expect, it } from "vitest"

import { MENU_ACCOUNT_ID, MENU_SETTINGS_ID, MENU_TRASH_ID } from "@/components/sympose"
import { SECTION_LABELS, isSentinelSection } from "./shell-sections"

describe("shell sections", () => {
  it("names Settings, Persona and the Bin", () => {
    expect(SECTION_LABELS[MENU_SETTINGS_ID]).toBe("Settings")
    expect(SECTION_LABELS[MENU_ACCOUNT_ID]).toBe("Persona")
    expect(SECTION_LABELS[MENU_TRASH_ID]).toBe("Bin")
  })

  it("tells the three app sections from the vault's own folders and notes", () => {
    for (const id of [MENU_SETTINGS_ID, MENU_ACCOUNT_ID, MENU_TRASH_ID]) expect(isSentinelSection(id)).toBe(true)
    for (const id of ["", "Notes", "README.md", "__other__"]) expect(isSentinelSection(id)).toBe(false)
  })
})
