import { describe, expect, it } from "vitest"

import { MENU_ACCOUNT_ID, MENU_SETTINGS_ID, MENU_TRASH_ID } from "@/components/sympose"
import { SECTION_LABELS, isSentinelSection, sectionAfterFolderMove } from "./shell-sections"

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

describe("the section after a folder is renamed or moved", () => {
  it("follows a renamed root folder", () => expect(sectionAfterFolderMove("People", "People", "Team")).toBe("Team"))

  it("becomes the root folder it went into when a root folder is moved inside another, since only roots are sections", () =>
    expect(sectionAfterFolderMove("People", "People", "Archive/Old/People")).toBe("Archive"))

  it("stays when another folder moved", () => {
    expect(sectionAfterFolderMove("People", "Garden", "Archive/Garden")).toBe("People")
    expect(sectionAfterFolderMove("People", "People/Sub", "Archive/Sub")).toBe("People")
  })

  it("stays on the app's own sections", () => expect(sectionAfterFolderMove(MENU_SETTINGS_ID, "People", "Team")).toBe(MENU_SETTINGS_ID))
})
