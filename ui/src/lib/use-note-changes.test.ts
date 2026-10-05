// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { VaultNode } from "@/components/sympose"
import { useNoteChanges } from "./use-note-changes"
import { setUnsavedGuard } from "./unsaved-guard"

const moveVaultNote = vi.fn()
const notify = { error: vi.fn(), success: vi.fn() }
vi.mock("./vault-note-api", () => ({ moveVaultNote: (...a: unknown[]) => moveVaultNote(...a) }))
vi.mock("./notify", () => ({ notify: { error: (...a: unknown[]) => notify.error(...a), success: (...a: unknown[]) => notify.success(...a) } }))

function setup(over: { selectedNote?: string; hideExtension?: boolean; openableNote?: string } = {}) {
  const fns = {
    setSelectedNote: vi.fn(),
    selectNote: vi.fn(),
    noteRenamed: vi.fn(),
    folderRenamed: vi.fn(),
    refreshVault: vi.fn(),
    openEditor: vi.fn(),
    hideFromView: vi.fn(),
    isPinned: vi.fn(() => true),
    togglePin: vi.fn(),
    unpinMany: vi.fn(),
    removeFromRecents: vi.fn(),
    clearRecents: vi.fn(),
  }
  const hook = renderHook(() =>
    useNoteChanges({
      activePersona: "samantha",
      selectedNote: over.selectedNote,
      openableNote: over.openableNote,
      hideExtension: over.hideExtension ?? false,
      ...fns,
    })
  )
  return { ...fns, ...hook }
}

beforeEach(() => vi.resetAllMocks())

describe("useNoteChanges: moving a note", () => {
  it("moves it, refreshes, follows the new path everywhere and says what the server said", async () => {
    moveVaultNote.mockResolvedValue({ ok: true, path: "Daily/a.md", detail: "Moved a to Daily" })
    const s = setup()
    await s.result.current.moveNote("Notes/a.md", "Daily")
    expect(moveVaultNote).toHaveBeenCalledWith("Notes/a.md", "Daily", "samantha")
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
    expect(s.noteRenamed).toHaveBeenCalledWith("Notes/a.md", "Daily/a.md")
    expect(notify.success).toHaveBeenCalledWith("Moved a to Daily")
  })

  it("does nothing, quietly, for a note dropped back on its own folder", async () => {
    moveVaultNote.mockResolvedValue({ ok: true, path: "Notes/a.md", detail: "nothing" })
    const s = setup()
    await s.result.current.moveNote("Notes/a.md", "Notes")
    expect(s.refreshVault).not.toHaveBeenCalled()
    expect(s.noteRenamed).not.toHaveBeenCalled()
    expect(notify.success).not.toHaveBeenCalled()
    expect(notify.error).not.toHaveBeenCalled()
  })

  it("says why when the server refuses, and changes nothing", async () => {
    moveVaultNote.mockResolvedValue({ ok: false, error: "exists there" })
    const s = setup()
    await s.result.current.moveNote("Notes/a.md", "Daily")
    expect(notify.error).toHaveBeenCalledWith("exists there")
    expect(s.refreshVault).not.toHaveBeenCalled()
    expect(s.noteRenamed).not.toHaveBeenCalled()
  })
})

describe("useNoteChanges: the open editor's unsaved edits across a rename or move", () => {
  // The editor's leave-note flush writes to the path it loaded; if the shell changes the path first, that
  // write goes to a file that no longer exists (404) and the edits are lost. So `retarget` must finish first.
  function guardLog() {
    const log: string[] = []
    let finish!: () => void
    setUnsavedGuard({
      name: () => "a",
      isDirty: () => true,
      save: async () => true,
      retarget: (o, n) => {
        log.push(`retarget ${o} ${n}`)
        return new Promise<void>((r) => (finish = () => (log.push("saved"), r())))
      },
    })
    return { log, finish: () => finish() }
  }

  it("lets the editor save to the new path before a tree rename changes anything", async () => {
    const g = guardLog()
    const s = setup({ selectedNote: "a.md" })
    s.noteRenamed.mockImplementation(() => g.log.push("renamed"))
    const done = s.result.current.vaultTreeActions.onRenamed("a.md", "b.md")
    await Promise.resolve()
    expect(s.noteRenamed).not.toHaveBeenCalled()
    expect(s.refreshVault).not.toHaveBeenCalled()
    g.finish()
    await done
    expect(g.log).toEqual(["retarget a.md b.md", "saved", "renamed"])
    setUnsavedGuard(null)
  })

  it("does the same for a note dropped on another folder", async () => {
    moveVaultNote.mockResolvedValue({ ok: true, path: "Daily/a.md", detail: "Moved" })
    const g = guardLog()
    const s = setup({ selectedNote: "Notes/a.md" })
    s.noteRenamed.mockImplementation(() => g.log.push("renamed"))
    const done = s.result.current.moveNote("Notes/a.md", "Daily")
    await vi.waitFor(() => expect(g.log).toHaveLength(1))
    expect(s.noteRenamed).not.toHaveBeenCalled()
    g.finish()
    await done
    expect(g.log).toEqual(["retarget Notes/a.md Daily/a.md", "saved", "renamed"])
    setUnsavedGuard(null)
  })
})

describe("useNoteChanges: the tree's rows", () => {
  it("opens a picked note in the editor", () => {
    const s = setup()
    s.result.current.vaultTreeActions.onSelect({ path: "Notes/a.md" } as VaultNode)
    expect(s.selectNote).toHaveBeenCalledWith("Notes/a.md")
    expect(s.openEditor).toHaveBeenCalledTimes(1)
  })

  it("opens a note just created from a row, and refreshes", () => {
    const s = setup()
    s.result.current.vaultTreeActions.onCreated("Notes/new.md")
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
    expect(s.selectNote).toHaveBeenCalledWith("Notes/new.md")
    expect(s.openEditor).toHaveBeenCalledTimes(1)
  })

  it("follows a rename, and refreshes", async () => {
    const s = setup()
    await s.result.current.vaultTreeActions.onRenamed("a.md", "b.md")
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
    expect(s.noteRenamed).toHaveBeenCalledWith("a.md", "b.md")
  })

  it("closes the editor when the open note is deleted, or the folder it is in", () => {
    for (const deleted of ["Notes/a.md", "Notes"]) {
      const s = setup({ selectedNote: "Notes/a.md" })
      s.result.current.vaultTreeActions.onDeleted(deleted)
      expect(s.setSelectedNote).toHaveBeenCalledWith(undefined)
      expect(s.refreshVault).toHaveBeenCalledTimes(1)
    }
  })

  it("leaves the editor alone when something else is deleted, even a folder whose name only starts the same", () => {
    for (const deleted of ["Notes/b.md", "Daily", "Not", "Notes/a.m"]) {
      const s = setup({ selectedNote: "Notes/a.md" })
      s.result.current.vaultTreeActions.onDeleted(deleted)
      expect(s.setSelectedNote).not.toHaveBeenCalled()
      expect(s.refreshVault).toHaveBeenCalledTimes(1)
    }
    const none = setup()
    none.result.current.vaultTreeActions.onDeleted("Notes")
    expect(none.setSelectedNote).not.toHaveBeenCalled()
  })

  it("hands the rows what they need: the open note, the persona, the pins, the recents and the extension setting", () => {
    const s = setup({ openableNote: "Notes/a.md", hideExtension: true })
    const a = s.result.current.vaultTreeActions
    expect(a.selectedPath).toBe("Notes/a.md")
    expect(a.persona).toBe("samantha")
    expect(a.hideExtension).toBe(true)
    expect(a.isPinned).toBe(s.isPinned)
    expect(a.onTogglePin).toBe(s.togglePin)
    expect(a.onUnpinAll).toBe(s.unpinMany)
    expect(a.onRemoveFromRecents).toBe(s.removeFromRecents)
    expect(a.onClearRecents).toBe(s.clearRecents)
    expect(a.onHide).toBe(s.hideFromView)
    expect(a.onMoveNote).toBe(s.result.current.moveNote)
  })
})

describe("useNoteChanges: the open editor", () => {
  it("follows the open note's rename, and refreshes", () => {
    const s = setup({ selectedNote: "a.md" })
    s.result.current.onEditorRenamed("b.md")
    expect(s.noteRenamed).toHaveBeenCalledWith("a.md", "b.md")
    expect(s.setSelectedNote).not.toHaveBeenCalled()
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
  })

  it("selects the reported path when no note was selected", () => {
    const s = setup()
    s.result.current.onEditorRenamed("b.md")
    expect(s.setSelectedNote).toHaveBeenCalledWith("b.md")
    expect(s.noteRenamed).not.toHaveBeenCalled()
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
  })

  it("closes on a delete, and refreshes", () => {
    const s = setup({ selectedNote: "a.md" })
    s.result.current.onEditorDeleted()
    expect(s.setSelectedNote).toHaveBeenCalledWith(undefined)
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
  })
})

describe("useNoteChanges: a folder was renamed (docs/decisions/073)", () => {
  const guard = (retarget = vi.fn(async () => {})) => {
    setUnsavedGuard({ name: () => "n", isDirty: () => false, save: async () => true, retarget })
    return retarget
  }

  it("lets the open editor save its unsaved edits at the note's new path first, then follows the rename everywhere", async () => {
    const order: string[] = []
    const retarget = guard(vi.fn(async () => void order.push("retarget")))
    const s = setup({ selectedNote: "People/Sub/Anna.md" })
    s.refreshVault.mockImplementation(() => void order.push("refresh"))
    s.folderRenamed.mockImplementation(() => void order.push("follow"))

    await s.result.current.vaultTreeActions.onFolderRenamed("People", "Team")

    expect(retarget).toHaveBeenCalledWith("People/Sub/Anna.md", "Team/Sub/Anna.md")
    expect(order).toEqual(["retarget", "refresh", "follow"])
    expect(s.folderRenamed).toHaveBeenCalledWith("People", "Team")
  })

  it("does not touch the editor when the open note is not inside the renamed folder", async () => {
    const retarget = guard()
    const s = setup({ selectedNote: "People and Pets/Rex.md" })

    await s.result.current.vaultTreeActions.onFolderRenamed("People", "Team")

    expect(retarget).not.toHaveBeenCalled()
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
    expect(s.folderRenamed).toHaveBeenCalledWith("People", "Team")
  })

  it("works with no note open", async () => {
    guard()
    const s = setup()

    await s.result.current.vaultTreeActions.onFolderRenamed("People", "Team")

    expect(s.folderRenamed).toHaveBeenCalledTimes(1)
  })

  it("saves an unsaved open note before the rename request, whichever note it is, since the rename may rewrite its links", async () => {
    const save = vi.fn(async () => true)
    setUnsavedGuard({ name: () => "n", isDirty: () => true, save, retarget: async () => {} })
    const s = setup({ selectedNote: "Elsewhere/Note.md" })

    expect(await s.result.current.vaultTreeActions.onBeforeFolderRename()).toBe(true)

    expect(save).toHaveBeenCalledTimes(1)
  })

  it("says to go ahead without saving when nothing is unsaved or no note is open", async () => {
    const save = vi.fn(async () => true)
    setUnsavedGuard({ name: () => "n", isDirty: () => false, save, retarget: async () => {} })
    const s = setup({ selectedNote: "People/Anna.md" })
    expect(await s.result.current.vaultTreeActions.onBeforeFolderRename()).toBe(true)
    expect(save).not.toHaveBeenCalled()

    setUnsavedGuard(null)
    expect(await s.result.current.vaultTreeActions.onBeforeFolderRename()).toBe(true)
  })

  it("holds the rename back when the unsaved note could not be saved", async () => {
    setUnsavedGuard({ name: () => "n", isDirty: () => true, save: async () => false, retarget: async () => {} })
    const s = setup({ selectedNote: "People/Anna.md" })

    expect(await s.result.current.vaultTreeActions.onBeforeFolderRename()).toBe(false)
  })
})

