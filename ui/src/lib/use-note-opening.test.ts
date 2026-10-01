// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { useNoteOpening } from "./use-note-opening"

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const tree: VaultNode[] = [
  { type: "folder", name: "Work", path: "Work", children: [note("Work/Atlas.md")] } as VaultNode,
  note("README.md"),
]

function setup(vaultTree = tree) {
  const selectNote = vi.fn()
  const openEditor = vi.fn()
  const hook = renderHook(() => useNoteOpening({ vaultTree, selectNote, openEditor }))
  return { selectNote, openEditor, ...hook }
}

describe("useNoteOpening", () => {
  it("opens the note a [[wikilink]] names, in the editor, without asking for preview", () => {
    const { result, selectNote, openEditor } = setup()
    act(() => result.current.openWikilink("Atlas"))
    expect(selectNote).toHaveBeenCalledWith("Work/Atlas.md")
    expect(openEditor).toHaveBeenCalledTimes(1)
    expect(result.current.previewRequest).toBe(0)
  })

  it("does nothing for a [[wikilink]] to a note the user cannot see", () => {
    const { result, selectNote, openEditor } = setup()
    act(() => result.current.openWikilink("Hidden"))
    expect(selectNote).not.toHaveBeenCalled()
    expect(openEditor).not.toHaveBeenCalled()
  })

  it("opens a note named under a chat reply in preview mode, once per open", () => {
    const { result, selectNote, openEditor } = setup()
    act(() => result.current.openGroundedNote("README.md"))
    act(() => result.current.openGroundedNote("README.md"))
    expect(selectNote).toHaveBeenCalledWith("README.md")
    expect(openEditor).toHaveBeenCalledTimes(2)
    expect(result.current.previewRequest).toBe(2)
  })

  it("does nothing for a grounded note that is hidden or deleted (not in the tree)", () => {
    const { result, selectNote, openEditor } = setup()
    act(() => result.current.openGroundedNote("Gone.md"))
    expect(selectNote).not.toHaveBeenCalled()
    expect(openEditor).not.toHaveBeenCalled()
    expect(result.current.previewRequest).toBe(0)
  })

  it("opens a [[wikilink]] from a chat reply in preview mode, and ignores an unknown one", () => {
    const { result, selectNote } = setup()
    act(() => result.current.openChatWikilink("Atlas"))
    expect(selectNote).toHaveBeenCalledWith("Work/Atlas.md")
    expect(result.current.previewRequest).toBe(1)
    act(() => result.current.openChatWikilink("Nope"))
    expect(selectNote).toHaveBeenCalledTimes(1)
    expect(result.current.previewRequest).toBe(1)
  })
})
