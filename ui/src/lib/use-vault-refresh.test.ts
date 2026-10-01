// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useVaultRefresh } from "./use-vault-refresh"

describe("useVaultRefresh", () => {
  it("counts up from zero each time the vault is refreshed", () => {
    const { result } = renderHook(() => useVaultRefresh())
    expect(result.current.vaultRefreshKey).toBe(0)
    act(() => result.current.refreshVault())
    act(() => result.current.refreshVault())
    expect(result.current.vaultRefreshKey).toBe(2)
  })

  it("hands out one refresh function for good, so an effect that lists it does not re-run", () => {
    const { result } = renderHook(() => useVaultRefresh())
    const first = result.current.refreshVault
    act(() => result.current.refreshVault())
    expect(result.current.refreshVault).toBe(first)
  })
})
