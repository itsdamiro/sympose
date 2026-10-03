// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchVaultNote: vi.fn(), saveVaultNote: vi.fn() }))

vi.mock("@damiro/stylo", () => ({
  splitFrontmatter: (text: string) => ({ frontmatter: "", body: text, prefix: "" }),
  Stylo: ({ value, onChange, mode }: { value: string; onChange: (v: string) => void; mode?: string }) => (
    <textarea aria-label="editor" data-mode={mode} value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}))
vi.mock("@damiro/stylo/styles.css", () => ({}))
vi.mock("@damiro/stylo/katex.css", () => ({}))
vi.mock("@/lib/vault-note-api", () => api)
const notify = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))
vi.mock("@/components/sympose/note-actions-menu", () => ({
  NoteActionsMenu: ({ onRenamed, onDeleted }: { onRenamed: (p: string) => void; onDeleted: () => void }) => (
    <>
      <button onClick={() => onRenamed("Renamed.md")}>rename</button>
      <button onClick={onDeleted}>delete</button>
    </>
  ),
}))

import type { EditorPreferences } from "@/lib/use-editor-preferences"
import { getUnsavedGuard } from "@/lib/unsaved-guard"
import { MarkdownPanel } from "./markdown-panel"

const PREFERENCES: EditorPreferences = {
  surface: "in-place", reveal: "never", selectionUI: "bar", tableEditing: "source",
  focusOutline: "on", autosave: "off", hideExtension: "on",
} as EditorPreferences

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} })
  api.fetchVaultNote.mockResolvedValue({ path: "Old.md", content: "old", mtime: 100 })
  api.saveVaultNote.mockResolvedValue({ ok: true, mtime: 200 })
})
afterEach(() => {
  document.cookie = "sympose:pref.noteReadOnly=; max-age=0"
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

async function openAndEdit(onRenamed = vi.fn(), onDeleted = vi.fn()) {
  const view = render(
    <MarkdownPanel path="Old.md" preferences={PREFERENCES} toolbarItems={[]} onRenamed={onRenamed} onDeleted={onDeleted} />
  )
  const editor = await screen.findByLabelText("editor")
  fireEvent.change(editor, { target: { value: "edited" } })
  return { view, onRenamed, onDeleted }
}

describe("MarkdownPanel leaving a note with unsaved edits", () => {
  it("saves the edits to the new path when the note is renamed", async () => {
    const { onRenamed } = await openAndEdit()
    await act(async () => fireEvent.click(screen.getByText("rename")))
    await waitFor(() => expect(onRenamed).toHaveBeenCalledWith("Renamed.md"))
    expect(api.saveVaultNote).toHaveBeenCalledTimes(1)
    expect(api.saveVaultNote.mock.calls[0][0]).toBe("Renamed.md")
    expect(api.saveVaultNote.mock.calls[0][1]).toBe("edited")
  })

  it("saves the edits to the new path when the note is renamed from outside (a tree row, a drop), and never to the old one", async () => {
    const { view } = await openAndEdit()
    await act(async () => getUnsavedGuard()!.retarget("Old.md", "Renamed.md"))
    expect(api.saveVaultNote).toHaveBeenCalledTimes(1)
    expect(api.saveVaultNote.mock.calls[0][0]).toBe("Renamed.md")
    expect(api.saveVaultNote.mock.calls[0][1]).toBe("edited")
    // The shell then changes the path; the leave-note flush finds nothing left to save.
    api.fetchVaultNote.mockResolvedValue({ path: "Renamed.md", content: "edited", mtime: 200 })
    view.rerender(<MarkdownPanel path="Renamed.md" preferences={PREFERENCES} toolbarItems={[]} />)
    await screen.findByLabelText("editor")
    expect(api.saveVaultNote.mock.calls.map((c) => c[0])).toEqual(["Renamed.md"])
  })

  it("ignores a rename of some other note", async () => {
    await openAndEdit()
    await act(async () => getUnsavedGuard()!.retarget("Other.md", "Else.md"))
    expect(api.saveVaultNote).not.toHaveBeenCalled()
  })

  it("does not save a deleted note's edits anywhere", async () => {
    const { view, onDeleted } = await openAndEdit()
    await act(async () => fireEvent.click(screen.getByText("delete")))
    expect(onDeleted).toHaveBeenCalled()
    view.unmount()
    expect(api.saveVaultNote).not.toHaveBeenCalled()
  })

  it("presents the mtime it loaded when it saves", async () => {
    await openAndEdit()
    // Renaming saves through the same path as ⌘S and the leave-note flush.
    await act(async () => fireEvent.click(screen.getByText("rename")))
    expect(api.saveVaultNote.mock.calls[0][3]).toBe(100)
  })

  it("does not overwrite a note that changed elsewhere: it offers to discard the edits and reload", async () => {
    api.saveVaultNote.mockResolvedValue({ ok: false, error: "changed on disk", conflict: true })
    await openAndEdit()
    await act(async () => fireEvent.click(screen.getByText("rename")))
    const [message, options] = notify.error.mock.calls[0]
    expect(message).toBe("changed on disk")
    const fetches = api.fetchVaultNote.mock.calls.length
    await act(async () => options.action.onClick())
    expect(api.fetchVaultNote.mock.calls.length).toBe(fetches + 1)
  })

  it("does not let a save of the note just left overwrite what it knows of the note opened next", async () => {
    const { view } = await openAndEdit()
    let landOld!: (r: unknown) => void
    api.saveVaultNote.mockImplementationOnce(() => new Promise((resolve) => (landOld = resolve)))
    api.fetchVaultNote.mockResolvedValueOnce({ path: "New.md", content: "newer", mtime: 300 })
    // Leaving Old.md flushes its edit; the next note loads before that save is answered.
    view.rerender(<MarkdownPanel path="New.md" preferences={PREFERENCES} toolbarItems={[]} onRenamed={vi.fn()} onDeleted={vi.fn()} />)
    await waitFor(() => expect(getUnsavedGuard()!.name()).toBe("New"))
    expect(getUnsavedGuard()!.isDirty()).toBe(false)
    await act(async () => landOld({ ok: true, mtime: 200 }))
    // The old note's text and mtime are not the new note's: it must still read as exactly what was loaded.
    expect(getUnsavedGuard()!.isDirty()).toBe(false)
  })

  it("shows a note opened from the chat in preview mode, and only when asked to", async () => {
    const props = { path: "Old.md", preferences: PREFERENCES, toolbarItems: [] }
    const view = render(<MarkdownPanel {...props} previewRequest={0} />)
    expect((await screen.findByLabelText("editor")).getAttribute("data-mode")).toBe("in-place")
    view.rerender(<MarkdownPanel {...props} previewRequest={0} />)
    expect(screen.getByLabelText("editor").getAttribute("data-mode")).toBe("in-place")
    view.rerender(<MarkdownPanel {...props} previewRequest={1} />)
    await waitFor(() => expect(screen.getByLabelText("editor").getAttribute("data-mode")).toBe("preview"))
  })

  describe("the collapse button", () => {
    const base = { preferences: PREFERENCES, toolbarItems: [] }

    it("is the far-left icon of the editor's toolbar, and collapses the editor", async () => {
      const onCollapse = vi.fn()
      render(<MarkdownPanel {...base} path="Old.md" onCollapse={onCollapse} />)
      await screen.findByLabelText("editor")
      const button = screen.getByRole("button", { name: "Collapse the editor" })
      expect(button.parentElement?.className).toContain("left-1.5") // the far left, as the note's own buttons are the far right
      fireEvent.click(button)
      expect(onCollapse).toHaveBeenCalledTimes(1)
    })

    it("is there when no note is open, so an empty editor can be collapsed too", () => {
      render(<MarkdownPanel {...base} path={undefined} onCollapse={() => {}} />)
      expect(screen.getByRole("button", { name: "Collapse the editor" })).toBeTruthy()
    })

    it("is left out when the panel cannot be collapsed", async () => {
      render(<MarkdownPanel {...base} path="Old.md" />)
      await screen.findByLabelText("editor")
      expect(screen.queryByRole("button", { name: "Collapse the editor" })).toBeNull()
    })

    it("makes room for itself in the read-mode path row, which has no toolbar of stylo's", async () => {
      const view = render(<MarkdownPanel {...base} path="Old.md" previewRequest={0} onCollapse={() => {}} />)
      await screen.findByLabelText("editor")
      view.rerender(<MarkdownPanel {...base} path="Old.md" previewRequest={1} onCollapse={() => {}} />)
      await waitFor(() => expect(screen.getByLabelText("editor").getAttribute("data-mode")).toBe("preview"))
      const row = document.querySelector(".sy-note-chrome")?.parentElement as HTMLElement
      expect(row.className).toContain("pl-9")
      expect(row.className).not.toContain("pl-1.5")
    })
  })

  describe("a file that is not a vault note (a persona's own file, docs/decisions/061)", () => {
    const base = { preferences: PREFERENCES, toolbarItems: [] }
    const makeFile = () => ({
      load: vi.fn().mockResolvedValue({ content: "She speaks plainly.", mtime: 40 }),
      save: vi.fn().mockResolvedValue({ ok: true, mtime: 41 }),
      title: "Samantha · soul.md",
    })

    it("loads and saves through the file's own functions, never the vault's", async () => {
      const file = makeFile()
      render(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} />)
      const editor = (await screen.findByLabelText("editor")) as HTMLTextAreaElement
      expect(editor.value).toBe("She speaks plainly.")
      expect(file.load).toHaveBeenCalledWith("persona:samantha/soul.md")
      fireEvent.change(editor, { target: { value: "She speaks plainly, and warmly." } })
      await act(async () => {
        await getUnsavedGuard()!.save()
      })
      expect(file.save).toHaveBeenCalledWith("persona:samantha/soul.md", "She speaks plainly, and warmly.", 40)
      expect(api.fetchVaultNote).not.toHaveBeenCalled()
      expect(api.saveVaultNote).not.toHaveBeenCalled()
    })

    it("has no note actions: a persona's file is not renamed or deleted as a note is", async () => {
      render(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={makeFile()} />)
      await screen.findByLabelText("editor")
      expect(screen.queryByText("rename")).toBeNull()
      expect(screen.queryByText("delete")).toBeNull()
    })

    it("names itself by the file's title in read mode, not by a vault path", async () => {
      const file = makeFile()
      const view = render(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} previewRequest={0} vaultName="Notes" />)
      await screen.findByLabelText("editor")
      view.rerender(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} previewRequest={1} vaultName="Notes" />)
      await waitFor(() => expect(screen.getByLabelText("editor").getAttribute("data-mode")).toBe("preview"))
      expect(screen.getByText("Samantha · soul.md")).toBeTruthy()
      expect(screen.queryByText("Notes")).toBeNull()
    })

    it("shows the file's banner at the top of the document", async () => {
      const file = { ...makeFile(), banner: <p>Your own copy is in use.</p> }
      const view = render(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} previewRequest={0} />)
      await screen.findByLabelText("editor")
      view.rerender(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} previewRequest={1} />)
      expect(await screen.findByText("Your own copy is in use.")).toBeTruthy()
    })

    it("saves what was typed exactly: a #word in a persona's file is not turned into a frontmatter tag", async () => {
      const file = { ...makeFile(), load: vi.fn().mockResolvedValue({ content: "She likes #focus", mtime: 40 }) }
      render(<MarkdownPanel {...base} path="persona:samantha/profile.md" file={file} />)
      const editor = (await screen.findByLabelText("editor")) as HTMLTextAreaElement
      fireEvent.change(editor, { target: { value: "She likes #focus and #rest" } })
      await act(async () => {
        await getUnsavedGuard()!.save()
      })
      expect(file.save.mock.calls[0][1]).toBe("She likes #focus and #rest")
    })

    it("reads the file again when told to from outside, as after a reset or an accepted rewrite", async () => {
      const file = makeFile()
      const view = render(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} reloadToken={0} />)
      await screen.findByLabelText("editor")
      expect(file.load).toHaveBeenCalledTimes(1)
      view.rerender(<MarkdownPanel {...base} path="persona:samantha/soul.md" file={file} reloadToken={1} />)
      await waitFor(() => expect(file.load).toHaveBeenCalledTimes(2))
    })
  })
})

