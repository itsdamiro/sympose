import { describe, expect, it } from "vitest"

import { iconByName } from "./persona-icons"
import { VAULT_FOLDERS, folderIconFor } from "./vault-folders"

describe("the curated folder icons", () => {
  it("each name an icon the shared set has, so a folder never falls back by accident", () => {
    for (const f of VAULT_FOLDERS) expect(iconByName(f.icon), f.name).toBeDefined()
  })

  it("falls back to the generic folder for a name that is a property of the object prototype", () => {
    const generic = folderIconFor("Unheard Of")
    expect(folderIconFor("Garden", "constructor")).toBe(generic)
    expect(folderIconFor("Garden", "toString")).toBe(generic)
    expect(folderIconFor("constructor")).toBe(generic)
  })
})
