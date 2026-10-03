// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useCreateField, useCreateSubmit } from "./use-create-flow"

const createVaultNote = vi.fn()
const createVaultFolder = vi.fn()
const fetchNoteTemplate = vi.fn()
const notify = { error: vi.fn(), success: vi.fn(), info: vi.fn() }
vi.mock("./vault-note-api", () => ({
  createVaultNote: (...a: unknown[]) => createVaultNote(...a),
  createVaultFolder: (...a: unknown[]) => createVaultFolder(...a),
}))
vi.mock("./vault-definition-api", () => ({ fetchNoteTemplate: (...a: unknown[]) => fetchNoteTemplate(...a) }))
vi.mock("./notify", () => ({ notify: { error: (...a: unknown[]) => notify.error(...a), success: (...a: unknown[]) => notify.success(...a), info: (...a: unknown[]) => notify.info(...a) } }))

beforeEach(() => {
  vi.resetAllMocks()
  createVaultNote.mockResolvedValue({ ok: true })
  createVaultFolder.mockResolvedValue({ ok: true })
  fetchNoteTemplate.mockResolvedValue(null)
})

describe("useCreateField", () => {
  it("starts with no field open and nothing typed", () => {
    const { result } = renderHook(() => useCreateField())
    expect(result.current.pendingCreate).toBeNull()
    expect(result.current.createName).toBe("")
    expect(result.current.creating).toBe(false)
  })

  it("opens a field blank from its icon, and closes it from the same icon", () => {
    const { result } = renderHook(() => useCreateField())
    act(() => result.current.toggleCreate("note"))
    expect(result.current.pendingCreate).toBe("note")
    act(() => result.current.setCreateName("half typed"))
    act(() => result.current.toggleCreate("note"))
    expect(result.current.pendingCreate).toBeNull()
    expect(result.current.createName).toBe("")
  })

  it("switches to the other field with the typed name cleared", () => {
    const { result } = renderHook(() => useCreateField())
    act(() => result.current.toggleCreate("note"))
    act(() => result.current.setCreateName("abc"))
    act(() => result.current.toggleCreate("folder"))
    expect(result.current.pendingCreate).toBe("folder")
    expect(result.current.createName).toBe("")
  })

  it("closes and clears on demand", () => {
    const { result } = renderHook(() => useCreateField())
    act(() => result.current.toggleCreate("folder"))
    act(() => result.current.setCreateName("abc"))
    act(() => result.current.closeCreate())
    expect(result.current.pendingCreate).toBeNull()
    expect(result.current.createName).toBe("")
  })

  it("focuses the field that opens, and only that one", () => {
    const { result } = renderHook(() => useCreateField())
    const note = document.createElement("input")
    const folder = document.createElement("input")
    document.body.append(note, folder)
    result.current.noteInputRef.current = note
    result.current.folderInputRef.current = folder
    act(() => result.current.toggleCreate("note"))
    expect(document.activeElement).toBe(note)
    act(() => result.current.toggleCreate("folder"))
    expect(document.activeElement).toBe(folder)
    note.remove()
    folder.remove()
  })
})

function setup(
  over: { kind?: "note" | "folder" | null; name?: string; creating?: boolean; folder?: string } = {}
) {
  const setCreating = vi.fn()
  const closeCreate = vi.fn()
  const refreshVault = vi.fn()
  const selectNote = vi.fn()
  const openEditor = vi.fn()
  const hook = renderHook(
    (p: { name: string }) =>
      useCreateSubmit({
        field: {
          pendingCreate: over.kind === undefined ? "note" : over.kind,
          createName: p.name,
          creating: over.creating ?? false,
          setCreating,
          closeCreate,
        },
        folder: over.folder ?? "Notes",
        activePersona: "samantha",
        refreshVault,
        selectNote,
        openEditor,
      }),
    { initialProps: { name: over.name ?? "Fresh" } }
  )
  return { setCreating, closeCreate, refreshVault, selectNote, openEditor, ...hook }
}

describe("useCreateSubmit: a note", () => {
  it("creates it in the folder in view, opens it in the editor, refreshes and says so", async () => {
    const s = setup()
    await act(async () => s.result.current.submitCreate())
    expect(createVaultNote).toHaveBeenCalledWith("Notes/Fresh", "samantha")
    expect(s.selectNote).toHaveBeenCalledWith("Notes/Fresh.md")
    expect(s.openEditor).toHaveBeenCalledTimes(1)
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
    expect(s.closeCreate).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Created Fresh")
    expect(createVaultFolder).not.toHaveBeenCalled()
  })

  it("creates it at the vault root when no folder is in view", async () => {
    const s = setup({ folder: "" })
    await act(async () => s.result.current.submitCreate())
    expect(createVaultNote).toHaveBeenCalledWith("Fresh", "samantha")
    expect(s.selectNote).toHaveBeenCalledWith("Fresh.md")
  })

  it("tidies the typed name: spaces, a .md ending in any case, and slashes at either end", async () => {
    for (const [typed, made] of [["  Plan.md ", "Plan"], ["Plan.MD", "Plan"], ["/Plan/", "Plan"], ["//a/b//", "a/b"], ["x.md.md", "x.md"]]) {
      createVaultNote.mockClear()
      const s = setup({ name: typed })
      await act(async () => s.result.current.submitCreate())
      expect(createVaultNote).toHaveBeenCalledWith(`Notes/${made}`, "samantha")
    }
  })

  it("keeps the typed name, and says why, when the server refuses", async () => {
    createVaultNote.mockResolvedValue({ ok: false, error: "exists" })
    const s = setup()
    await act(async () => s.result.current.submitCreate())
    expect(notify.error).toHaveBeenCalledWith("exists")
    expect(notify.success).not.toHaveBeenCalled()
    expect(s.closeCreate).not.toHaveBeenCalled()
    expect(s.refreshVault).not.toHaveBeenCalled()
    expect(s.selectNote).not.toHaveBeenCalled()
    expect(s.setCreating.mock.calls).toEqual([[true], [false]])
  })

  it("marks itself busy while it works", async () => {
    const s = setup()
    await act(async () => s.result.current.submitCreate())
    expect(s.setCreating.mock.calls).toEqual([[true], [false]])
  })

  it("does nothing with no field open, an empty name, or a create already running", async () => {
    for (const over of [{ kind: null }, { name: "   " }, { name: ".md" }, { name: "/" }, { creating: true }] as const) {
      const s = setup(over)
      await act(async () => s.result.current.submitCreate())
      expect(createVaultNote).not.toHaveBeenCalled()
      expect(createVaultFolder).not.toHaveBeenCalled()
      expect(s.setCreating).not.toHaveBeenCalled()
    }
  })
})

describe("useCreateSubmit: a folder", () => {
  it("creates it without opening anything in the editor", async () => {
    const s = setup({ kind: "folder", name: "Box" })
    await act(async () => s.result.current.submitCreate())
    expect(createVaultFolder).toHaveBeenCalledWith("Notes/Box", "samantha")
    expect(createVaultNote).not.toHaveBeenCalled()
    expect(s.selectNote).not.toHaveBeenCalled()
    expect(s.openEditor).not.toHaveBeenCalled()
    expect(s.refreshVault).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Created Box")
  })

  it("offers to set up a new root folder when the server says it can have a definition", async () => {
    const template = { lines: ["title:"], source: "settings", definable: true }
    fetchNoteTemplate.mockResolvedValue(template)
    const s = setup({ kind: "folder", name: "Projects", folder: "" })
    await act(async () => s.result.current.submitCreate())
    expect(fetchNoteTemplate).toHaveBeenCalledWith("Projects", "samantha")
    expect(s.result.current.folderSetup).toEqual({ folder: "Projects", template })
    act(() => s.result.current.closeFolderSetup())
    expect(s.result.current.folderSetup).toBeNull()
  })

  it("does not offer it when the folder cannot have a definition, or the server cannot be reached", async () => {
    fetchNoteTemplate.mockResolvedValue({ lines: [], source: "settings", definable: false })
    const a = setup({ kind: "folder", name: "Templates", folder: "" })
    await act(async () => a.result.current.submitCreate())
    expect(a.result.current.folderSetup).toBeNull()
    fetchNoteTemplate.mockResolvedValue(null)
    const b = setup({ kind: "folder", name: "Other", folder: "" })
    await act(async () => b.result.current.submitCreate())
    expect(b.result.current.folderSetup).toBeNull()
  })

  it("does not ask about a definition for a folder made inside another, or typed with a slash", async () => {
    const inside = setup({ kind: "folder", name: "Sub", folder: "Notes" })
    await act(async () => inside.result.current.submitCreate())
    const slashed = setup({ kind: "folder", name: "a/b", folder: "" })
    await act(async () => slashed.result.current.submitCreate())
    const back = setup({ kind: "folder", name: "a\\b", folder: "" })
    await act(async () => back.result.current.submitCreate())
    expect(fetchNoteTemplate).not.toHaveBeenCalled()
  })

  it("does not ask about a definition for a note, or when the create failed", async () => {
    const note = setup({ kind: "note", name: "Top", folder: "" })
    await act(async () => note.result.current.submitCreate())
    createVaultFolder.mockResolvedValue({ ok: false, error: "no" })
    const failed = setup({ kind: "folder", name: "Projects", folder: "" })
    await act(async () => failed.result.current.submitCreate())
    expect(fetchNoteTemplate).not.toHaveBeenCalled()
  })
})

describe("useCreateSubmit: from the main menu's own menu", () => {
  it("makes a note at the vault root whatever folder is in view, and opens it", async () => {
    const s = setup({ folder: "Notes" })
    let ok = false
    await act(async () => {
      ok = await s.result.current.createAtRoot("note", " Ideas.md ")
    })
    expect(ok).toBe(true)
    expect(createVaultNote).toHaveBeenCalledWith("Ideas", "samantha")
    expect(s.selectNote).toHaveBeenCalledWith("Ideas.md")
    expect(s.openEditor).toHaveBeenCalled()
  })

  it("makes a folder at the root and offers its setup, and reports a refusal without closing", async () => {
    const template = { lines: ["title:"], source: "settings", definable: true }
    fetchNoteTemplate.mockResolvedValue(template)
    const s = setup({ folder: "Notes" })
    await act(async () => {
      await s.result.current.createAtRoot("folder", "Projects")
    })
    expect(createVaultFolder).toHaveBeenCalledWith("Projects", "samantha")
    expect(s.result.current.folderSetup).toEqual({ folder: "Projects", template })
    createVaultFolder.mockResolvedValue({ ok: false, error: "exists" })
    let ok = true
    await act(async () => {
      ok = await s.result.current.createAtRoot("folder", "Projects")
    })
    expect(ok).toBe(false)
    expect(notify.error).toHaveBeenCalledWith("exists")
  })

  it("does nothing for a blank name", async () => {
    const s = setup()
    await act(async () => {
      expect(await s.result.current.createAtRoot("note", "  ")).toBe(false)
    })
    expect(createVaultNote).not.toHaveBeenCalled()
  })
})

describe("useCreateSubmit: define a folder by hand", () => {
  it("opens the setup dialog by hand for a folder that can be defined", async () => {
    const template = { lines: ["title:"], source: "settings", definable: true }
    fetchNoteTemplate.mockResolvedValue(template)
    const s = setup()
    await act(async () => s.result.current.openDefinition("People"))
    expect(s.result.current.folderSetup).toEqual({ folder: "People", template, manual: true })
  })

  it("says so, and opens nothing, for a folder that has one or cannot have one, or when it cannot be read", async () => {
    const s = setup()
    fetchNoteTemplate.mockResolvedValue({ lines: [], source: "settings", definable: false })
    await act(async () => s.result.current.openDefinition("Movies"))
    expect(notify.info).toHaveBeenCalledWith(expect.stringContaining("Movies cannot be given a definition"))
    fetchNoteTemplate.mockResolvedValue(null)
    await act(async () => s.result.current.openDefinition("Movies"))
    expect(notify.error).toHaveBeenCalled()
    expect(s.result.current.folderSetup).toBeNull()
  })
})
