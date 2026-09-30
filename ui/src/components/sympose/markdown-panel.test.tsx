// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchVaultNote: vi.fn(), saveVaultNote: vi.fn() }))

vi.mock("@damiro/stylo", () => ({
  splitFrontmatter: (text: string) => ({ frontmatter: "", body: text, prefix: "" }),
  Stylo: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="editor" value={value} onChange={(e) => onChange(e.target.value)} />
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
})
