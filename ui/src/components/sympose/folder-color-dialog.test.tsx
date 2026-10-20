// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { FolderColorDialog } from "./folder-color-dialog"

const api = vi.hoisted(() => ({ saveFolderColor: vi.fn() }))
vi.mock("@/lib/folder-color-api", () => api)
const notify = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))

type Look = { accent: string | null; accentDark: string | null; icon: string | null }
const NONE: Look = { accent: null, accentDark: null, icon: null }
const VIOLET: Look = { accent: "#7c3aed", accentDark: "#b98cff", icon: null }

beforeEach(() => {
  api.saveFolderColor.mockResolvedValue({ ok: true, created: false })
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function open(start: Look = NONE, path = "Projects/sympose") {
  const onClose = vi.fn()
  const onSaved = vi.fn()
  render(<FolderColorDialog setup={{ path, start }} persona="samantha" onClose={onClose} onSaved={onSaved} />)
  return { onClose, onSaved }
}
const iconField = () => screen.getByRole("combobox", { name: "Icon" }) as HTMLInputElement
const button = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement

describe("FolderColorDialog (docs/decisions/090)", () => {
  it("shows nothing while no folder is open", () => {
    render(<FolderColorDialog setup={null} persona="samantha" onClose={vi.fn()} onSaved={vi.fn()} />)
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("names the folder and the note the look is saved in", () => {
    open()
    expect(screen.getByText("Look of sympose")).toBeTruthy()
    expect(screen.getByText(/properties of Projects\/Projects\.md/)).toBeTruthy()
  })

  it("names a deeper folder by its path below the top-level one", () => {
    open(NONE, "Projects/sympose/decisions")
    expect(screen.getByText("Look of sympose/decisions")).toBeTruthy()
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
    expect(api.saveFolderColor).toHaveBeenCalledWith(
      "Projects/sympose",
      { accent: "#be123c", accentDark: "#f2889b", icon: null },
      "samantha"
    )
    expect(onClose).toHaveBeenCalled()
    expect(notify.success).toHaveBeenCalledWith("Saved the look of sympose")
  })

  it("starts on the folder's own icon and saves a chosen one with the colours it already has", async () => {
    const { onSaved } = open({ ...VIOLET, icon: "rocket" })
    expect(iconField().value).toBe("rocket")
    expect(button("Save").disabled).toBe(true)
    fireEvent.focus(iconField())
    fireEvent.change(iconField(), { target: { value: "airplane" } })
    fireEvent.click(screen.getByRole("option", { name: "airplane" }))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.saveFolderColor).toHaveBeenCalledWith("Projects/sympose", { ...VIOLET, icon: "airplane" }, "samantha")
  })

  it("saves an icon alone, and clearing the last of the look says it was cleared", async () => {
    open()
    fireEvent.focus(iconField())
    fireEvent.change(iconField(), { target: { value: "airplane" } })
    fireEvent.click(screen.getByRole("option", { name: "airplane" }))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(notify.success).toHaveBeenCalledWith("Saved the look of sympose"))
    expect(api.saveFolderColor).toHaveBeenCalledWith("Projects/sympose", { ...NONE, icon: "airplane" }, "samantha")
    cleanup()
    vi.clearAllMocks()
    api.saveFolderColor.mockResolvedValue({ ok: true, created: false })
    open({ ...NONE, icon: "airplane" })
    fireEvent.click(button("Clear the icon"))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(notify.success).toHaveBeenCalledWith("Cleared the look of sympose"))
    expect(api.saveFolderColor).toHaveBeenCalledWith("Projects/sympose", NONE, "samantha")
  })

  it("clears the colour with the cross", async () => {
    const { onSaved } = open(VIOLET)
    fireEvent.click(button("No colour"))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.saveFolderColor).toHaveBeenCalledWith("Projects/sympose", NONE, "samantha")
    expect(notify.success).toHaveBeenCalledWith("Cleared the look of sympose")
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
