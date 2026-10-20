// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { FolderColorDialog } from "./folder-color-dialog"

const api = vi.hoisted(() => ({ saveFolderColor: vi.fn() }))
vi.mock("@/lib/folder-color-api", () => api)
const notify = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))

type Colors = { accent: string | null; accentDark: string | null }
const NONE: Colors = { accent: null, accentDark: null }
const VIOLET = { accent: "#7c3aed", accentDark: "#b98cff" }

beforeEach(() => {
  api.saveFolderColor.mockResolvedValue({ ok: true, created: false })
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function open(start: Colors = NONE, path = "Projects/sympose") {
  const onClose = vi.fn()
  const onSaved = vi.fn()
  render(<FolderColorDialog setup={{ path, start }} persona="samantha" onClose={onClose} onSaved={onSaved} />)
  return { onClose, onSaved }
}
const button = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement

describe("FolderColorDialog (docs/decisions/090)", () => {
  it("shows nothing while no folder is open", () => {
    render(<FolderColorDialog setup={null} persona="samantha" onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("names the folder and the note the colour is saved in", () => {
    open()
    expect(screen.getByText("Colour for sympose")).toBeTruthy()
    expect(screen.getByText(/properties of Projects\/Projects\.md/)).toBeTruthy()
  })

  it("names a deeper folder by its path below the top-level one", () => {
    open(NONE, "Projects/sympose/decisions")
    expect(screen.getByText("Colour for sympose/decisions")).toBeTruthy()
    expect(screen.getByText(/properties of Projects\/Projects\.md/)).toBeTruthy()
  })

  it("starts on the folder's own colour and keeps Save off until something changes", () => {
    open(VIOLET)
    expect(button("Violet").getAttribute("aria-pressed")).toBe("true")
    expect(button("Save").disabled).toBe(true)
  })

  it("saves a preset for both themes, then closes and says the parent can refresh", async () => {
    const { onClose, onSaved } = open()
    fireEvent.click(button("Rose"))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.saveFolderColor).toHaveBeenCalledWith("Projects/sympose", { accent: "#be123c", accentDark: "#f2889b" }, "samantha")
    expect(onClose).toHaveBeenCalled()
    expect(notify.success).toHaveBeenCalledWith("Saved the colour of sympose")
  })

  it("clears the colour with the cross", async () => {
    const { onSaved } = open(VIOLET)
    fireEvent.click(button("No colour"))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.saveFolderColor).toHaveBeenCalledWith("Projects/sympose", NONE, "samantha")
    expect(notify.success).toHaveBeenCalledWith("Cleared the colour of sympose")
  })

  it("keeps the dialog open and says why when the save is refused", async () => {
    api.saveFolderColor.mockResolvedValue({ ok: false, error: "The note changed." })
    const { onClose, onSaved } = open()
    fireEvent.click(button("Rose"))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith("The note changed."))
    expect(onClose).not.toHaveBeenCalled()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it("writes nothing on Cancel", () => {
    const { onClose } = open()
    fireEvent.click(button("Cancel"))
    expect(api.saveFolderColor).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })
})
