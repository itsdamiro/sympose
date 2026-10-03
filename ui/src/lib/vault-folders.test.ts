import { describe, expect, it } from "vitest"

import { iconByName } from "./persona-icons"
import { VAULT_FOLDERS } from "./vault-folders"

describe("the curated folder icons", () => {
  it("each name an icon the shared set has, so a folder never falls back by accident", () => {
    for (const f of VAULT_FOLDERS) expect(iconByName(f.icon), f.name).toBeDefined()
  })
})
