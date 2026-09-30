import { afterEach, describe, expect, it, vi } from "vitest"

import { fetchVaultTree } from "./vault-tree-api"

afterEach(() => vi.unstubAllGlobals())

describe("fetchVaultTree (#90)", () => {
  it("returns the tree and the vault's name", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ tree: [{ name: "a" }], vaultName: "V" }) }))
    expect(await fetchVaultTree("samantha")).toEqual({ tree: [{ name: "a" }], vaultName: "V" })
  })

  it("returns an empty tree, not null, for an empty vault", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ tree: [], vaultName: null }) }))
    expect(await fetchVaultTree("samantha")).toEqual({ tree: [], vaultName: null })
  })

  it("returns null on an error or when unreachable, so a failure is never mistaken for an empty vault", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    expect(await fetchVaultTree("samantha")).toBeNull()
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")))
    expect(await fetchVaultTree("samantha")).toBeNull()
  })
})
