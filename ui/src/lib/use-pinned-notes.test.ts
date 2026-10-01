// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import { readList } from "./cookie-list"
import { getCookie, vaultScopedKey } from "./cookies"

import { usePinnedNotes } from "./use-pinned-notes"

function clearCookies() {
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim()
    if (name) document.cookie = `${name}=; path=/; max-age=0`
  })
}

describe("usePinnedNotes", () => {
  beforeEach(() => {
    clearCookies()
  })

  it("starts with nothing pinned before a vault is known", () => {
    const { result } = renderHook(() => usePinnedNotes(null))
    expect(result.current.pinnedPaths).toEqual([])
    expect(result.current.isPinned("a.md")).toBe(false)
  })

  it("toggles a path pinned and unpinned", () => {
    const { result } = renderHook(() => usePinnedNotes("/vault-a"))

    act(() => result.current.togglePin("a.md"))
    expect(result.current.isPinned("a.md")).toBe(true)
    expect(result.current.pinnedPaths).toEqual(["a.md"])

    act(() => result.current.togglePin("a.md"))
    expect(result.current.isPinned("a.md")).toBe(false)
    expect(result.current.pinnedPaths).toEqual([])
  })

  it("unpins several paths at once via unpinMany, leaving the rest", () => {
    const { result } = renderHook(() => usePinnedNotes("/vault-a"))

    act(() => result.current.togglePin("a.md"))
    act(() => result.current.togglePin("b.md"))
    act(() => result.current.togglePin("c.md"))
    act(() => result.current.unpinMany(["a.md", "c.md"]))

    expect(result.current.pinnedPaths).toEqual(["b.md"])
  })

  it("keeps a vault's pins across a re-render, restored from its cookie", () => {
    const { result, unmount } = renderHook(() => usePinnedNotes("/vault-a"))
    act(() => result.current.togglePin("a.md"))
    unmount()

    const { result: second } = renderHook(() => usePinnedNotes("/vault-a"))
    expect(second.current.pinnedPaths).toEqual(["a.md"])
  })

  it("does not leak pins across a vault switch", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => usePinnedNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" as string | null },
    })

    act(() => result.current.togglePin("a-note.md"))
    expect(result.current.pinnedPaths).toEqual(["a-note.md"])

    rerender({ vaultPath: "/vault-b" })
    expect(result.current.pinnedPaths).toEqual([])

    act(() => result.current.togglePin("b-note.md"))
    expect(result.current.pinnedPaths).toEqual(["b-note.md"])
  })

  it("restores a vault's own pins when switching back to it", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => usePinnedNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" as string | null },
    })

    act(() => result.current.togglePin("a-note.md"))
    rerender({ vaultPath: "/vault-b" })
    act(() => result.current.togglePin("b-note.md"))

    rerender({ vaultPath: "/vault-a" })
    expect(result.current.pinnedPaths).toEqual(["a-note.md"])

    rerender({ vaultPath: "/vault-b" })
    expect(result.current.pinnedPaths).toEqual(["b-note.md"])
  })

  it("does not reset pins on a re-render with the same vault (reseed-on-every-render regression)", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => usePinnedNotes(vaultPath), {
      initialProps: { vaultPath: "/vault-a" as string | null },
    })

    act(() => result.current.togglePin("a-note.md"))
    rerender({ vaultPath: "/vault-a" })
    rerender({ vaultPath: "/vault-a" })

    expect(result.current.pinnedPaths).toEqual(["a-note.md"])
  })

  it("resolves the unscoped, pre-vault pins once the vault becomes known", () => {
    const { result, rerender } = renderHook(({ vaultPath }) => usePinnedNotes(vaultPath), {
      initialProps: { vaultPath: null as string | null },
    })

    act(() => result.current.togglePin("early.md"))
    expect(result.current.pinnedPaths).toEqual(["early.md"])

    rerender({ vaultPath: "/vault-a" })
    // the pre-vault write lived on the bare, unscoped key — a real vault's
    // scoped key starts fresh, it does not inherit it.
    expect(result.current.pinnedPaths).toEqual([])
  })

  it("keeps a name with a comma as one pin across a reload", () => {
    const first = renderHook(() => usePinnedNotes("/vault-a"))
    act(() => first.result.current.togglePin("Notes, 2026.md"))
    first.unmount()

    const second = renderHook(() => usePinnedNotes("/vault-a"))
    expect(second.result.current.pinnedPaths).toEqual(["Notes, 2026.md"])
  })

  it("reads a pin cookie written in the older comma form", () => {
    document.cookie = `${vaultScopedKey("sympose:vault.pinned", "/vault-a")}=${encodeURIComponent("a.md,b/c.md")}; path=/`
    const { result } = renderHook(() => usePinnedNotes("/vault-a"))
    expect(result.current.pinnedPaths).toEqual(["a.md", "b/c.md"])
  })

  it("follows a renamed or moved note, in the same place", () => {
    const { result } = renderHook(() => usePinnedNotes("/vault-a"))
    act(() => result.current.togglePin("a.md"))
    act(() => result.current.togglePin("b.md"))
    act(() => result.current.togglePin("c.md"))

    act(() => result.current.remapPin("b.md", "Daily/b.md"))
    expect(result.current.pinnedPaths).toEqual(["a.md", "Daily/b.md", "c.md"])
    expect(result.current.isPinned("b.md")).toBe(false)
  })

  it("leaves the pins alone when an unpinned note is renamed", () => {
    const { result } = renderHook(() => usePinnedNotes("/vault-a"))
    act(() => result.current.togglePin("a.md"))
    act(() => result.current.remapPin("z.md", "y.md"))
    expect(result.current.pinnedPaths).toEqual(["a.md"])
  })

  it("keeps the saved cookie small enough to be stored, dropping the oldest pins", () => {
    const { result } = renderHook(() => usePinnedNotes("/vault-a"))
    for (let i = 0; i < 300; i++) {
      act(() => result.current.togglePin(`Projects/Archive/note-number-${i}.md`))
    }
    const raw = getCookie(vaultScopedKey("sympose:vault.pinned", "/vault-a"))
    expect(raw).not.toBeNull()
    const saved = readList(raw)
    expect(saved.length).toBeGreaterThan(0)
    expect(saved.length).toBeLessThan(300)
    expect(saved[saved.length - 1]).toBe("Projects/Archive/note-number-299.md")
  })
})
