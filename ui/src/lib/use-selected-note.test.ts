// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { getCookie, setCookie, vaultScopedKey } from "./cookies"
import { resolveSelectedNoteFor, useSelectedNote } from "./use-selected-note"

const COOKIE = "sympose:shell.note"

function setup(vaultPath: string | null, hidden: string[] = []) {
  const recordVisit = vi.fn()
  const remapPin = vi.fn()
  const remapRecent = vi.fn()
  const remapPinFolder = vi.fn()
  const remapRecentFolder = vi.fn()
  const hook = renderHook(
    (p: { vaultPath: string | null }) =>
      useSelectedNote({
        vaultPath: p.vaultPath,
        isHidden: (path) => !!path && hidden.includes(path),
        recordVisit,
        remapPin,
        remapRecent,
        remapPinFolder,
        remapRecentFolder,
      }),
    { initialProps: { vaultPath } }
  )
  return { recordVisit, remapPin, remapRecent, remapPinFolder, remapRecentFolder, ...hook }
}

beforeEach(() => {
  document.cookie.split(";").forEach((c) => {
    const name = c.split("=")[0]?.trim()
    if (name) document.cookie = `${name}=; path=/; max-age=0`
  })
})

describe("resolveSelectedNoteFor", () => {
  it("reads the note a vault left open from that vault's own cookie, and nothing from another's", () => {
    setCookie(vaultScopedKey(COOKIE, "/a"), "Notes/One.md")
    expect(resolveSelectedNoteFor("/a")).toBe("Notes/One.md")
    expect(resolveSelectedNoteFor("/b")).toBeUndefined()
  })

  it("treats an empty cookie as no note", () => {
    setCookie(vaultScopedKey(COOKIE, "/a"), "")
    expect(resolveSelectedNoteFor("/a")).toBeUndefined()
  })
})

describe("useSelectedNote", () => {
  it("opens the note the vault last had open", () => {
    setCookie(vaultScopedKey(COOKIE, "/a"), "Notes/One.md")
    const { result } = setup("/a")
    expect(result.current.selectedNote).toBe("Notes/One.md")
    expect(result.current.openableNote).toBe("Notes/One.md")
  })

  it("remembers the open note for its vault, and each vault has its own", () => {
    const { result, rerender } = setup("/a")
    act(() => result.current.selectNote("A.md"))
    expect(getCookie(vaultScopedKey(COOKIE, "/a"))).toBe("A.md")
    rerender({ vaultPath: "/b" })
    expect(result.current.selectedNote).toBeUndefined()
    act(() => result.current.selectNote("B.md"))
    rerender({ vaultPath: "/a" })
    expect(result.current.selectedNote).toBe("A.md")
    expect(getCookie(vaultScopedKey(COOKIE, "/b"))).toBe("B.md")
  })

  it("records a visit when a note is opened, but not when the path is only remapped or cleared", () => {
    const { result, recordVisit } = setup("/a")
    act(() => result.current.selectNote("A.md"))
    expect(recordVisit).toHaveBeenCalledWith("A.md")
    act(() => result.current.setSelectedNote("A2.md"))
    act(() => result.current.setSelectedNote(undefined))
    expect(recordVisit).toHaveBeenCalledTimes(1)
  })

  it("forgets the note, in the cookie too, when it is cleared", () => {
    const { result } = setup("/a")
    act(() => result.current.selectNote("A.md"))
    act(() => result.current.setSelectedNote(undefined))
    expect(result.current.selectedNote).toBeUndefined()
    expect(getCookie(vaultScopedKey(COOKIE, "/a"))).toBe("")
  })

  it("does not offer a note that is hidden from view, though it stays remembered", () => {
    setCookie(vaultScopedKey(COOKIE, "/a"), "Secret.md")
    const { result } = setup("/a", ["Secret.md"])
    expect(result.current.selectedNote).toBe("Secret.md")
    expect(result.current.openableNote).toBeUndefined()
  })

  it("has no open note when none is selected", () => {
    expect(setup("/a").result.current.openableNote).toBeUndefined()
  })

  it("follows a renamed or moved note: its pin, its place in the recents and the open editor", () => {
    const { result, remapPin, remapRecent } = setup("/a")
    act(() => result.current.selectNote("Old.md"))
    act(() => result.current.noteRenamed("Old.md", "New.md"))
    expect(remapPin).toHaveBeenCalledWith("Old.md", "New.md")
    expect(remapRecent).toHaveBeenCalledWith("Old.md", "New.md")
    expect(result.current.selectedNote).toBe("New.md")
  })

  it("leaves the open note alone when a different note is renamed", () => {
    const { result, remapPin, remapRecent } = setup("/a")
    act(() => result.current.selectNote("Open.md"))
    act(() => result.current.noteRenamed("Other.md", "Elsewhere.md"))
    expect(remapPin).toHaveBeenCalledWith("Other.md", "Elsewhere.md")
    expect(remapRecent).toHaveBeenCalledWith("Other.md", "Elsewhere.md")
    expect(result.current.selectedNote).toBe("Open.md")
  })

  it("follows a renamed folder: the pins and recents under it, and the open note when it is inside", () => {
    const { result, remapPinFolder, remapRecentFolder } = setup("/a")
    act(() => result.current.selectNote("People/Sub/Anna.md"))

    act(() => result.current.folderRenamed("People", "Team"))

    expect(remapPinFolder).toHaveBeenCalledWith("People", "Team")
    expect(remapRecentFolder).toHaveBeenCalledWith("People", "Team")
    expect(result.current.selectedNote).toBe("Team/Sub/Anna.md")
    expect(getCookie(vaultScopedKey(COOKIE, "/a"))).toBe("Team/Sub/Anna.md")
  })

  it("leaves the open note alone when it is not inside the renamed folder, even one whose name starts the same", () => {
    const { result } = setup("/a")
    act(() => result.current.selectNote("People and Pets/Rex.md"))

    act(() => result.current.folderRenamed("People", "Team"))

    expect(result.current.selectedNote).toBe("People and Pets/Rex.md")
  })
})

