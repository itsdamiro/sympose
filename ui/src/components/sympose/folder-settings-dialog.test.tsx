// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { FolderSettingsDialog } from "./folder-settings-dialog"
import type { FolderSettings } from "@/lib/folder-settings-api"

const api = vi.hoisted(() => ({ saveFolderSettings: vi.fn() }))
vi.mock("@/lib/folder-settings-api", () => api)
const notify = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))

const LINES = ['title: "{{title}}"', "created: {{date}}", "tags: []"]
const NEW: FolderSettings = {
  editable: true,
  defined: false,
  purpose: "",
  template: LINES,
  templateSource: "settings",
  icon: null,
  accent: null,
  accentDark: null,
}
const DEFINED: FolderSettings = {
  ...NEW,
  defined: true,
  purpose: "Books I read.",
  template: ["title:", "author:"],
  templateSource: "note",
  icon: "book",
  accent: "#1d4ed8",
  accentDark: "#7aa7e0",
}
type Setup = { folder: string; settings: FolderSettings; manual?: boolean } | null

beforeEach(() => {
  api.saveFolderSettings.mockResolvedValue({ ok: true, created: true })
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function setup(setupArg: Setup = { folder: "Books", settings: NEW }) {
  const onClose = vi.fn()
  const onSaved = vi.fn()
  const props = { persona: "samantha", onClose, onSaved }
  const view = render(<FolderSettingsDialog setup={setupArg} {...props} />)
  return { onClose, onSaved, props, ...view }
}

const templateField = () => screen.getByLabelText(/Properties new notes start with/) as HTMLTextAreaElement
const purposeField = () => screen.getByLabelText(/What is this folder for/) as HTMLTextAreaElement
const iconField = () => screen.getByRole("combobox", { name: "Icon" }) as HTMLInputElement
const button = (name: string) => screen.getByRole("button", { name }) as HTMLButtonElement
const createButton = () => button("Create the description")

describe("FolderSettingsDialog: the step after a root folder is created", () => {
  it("shows nothing while no folder is open", () => {
    setup(null)
    expect(screen.queryByText(/Set up/)).toBeNull()
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("starts the template from the one it was given and says where it came from", () => {
    setup()
    expect(templateField().value).toBe(LINES.join("\n"))
    expect(screen.getByText(/Started from the default keys/)).toBeTruthy()
    expect(purposeField().value).toBe("")
    expect(iconField().value).toBe("")
  })

  it("says so when the lines are the vault's own note template", () => {
    setup({ folder: "Books", settings: { ...NEW, template: ["title:"], templateSource: "vault" } })
    expect(screen.getByText(/Started from your Templates\/Note template\.md/)).toBeTruthy()
    expect(templateField().value).toBe("title:")
  })

  it("starts empty for the next folder instead of carrying the last one's words over", () => {
    const { rerender, props } = setup()
    fireEvent.change(purposeField(), { target: { value: "Books I read." } })
    fireEvent.change(templateField(), { target: { value: "edited:" } })
    fireEvent.change(iconField(), { target: { value: "film" } })
    fireEvent.keyDown(iconField(), { key: "Enter" })
    rerender(<FolderSettingsDialog setup={{ folder: "Films", settings: NEW }} {...props} />)
    expect(screen.getByText("Set up Films")).toBeTruthy()
    expect(purposeField().value).toBe("")
    expect(templateField().value).toBe(LINES.join("\n"))
    expect(iconField().value).toBe("")
  })

  it("writes what the user typed, trimmed, and then closes and refreshes", async () => {
    const { onClose, onSaved } = setup()
    fireEvent.change(purposeField(), { target: { value: "  What I read.  " } })
    fireEvent.change(templateField(), { target: { value: "title:\nauthor:" } })
    fireEvent.click(createButton())
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1))
    expect(api.saveFolderSettings).toHaveBeenCalledExactlyOnceWith(
      "Books",
      { purpose: "What I read.", template: ["title:", "author:"], icon: null, accent: null, accentDark: null },
      "samantha"
    )
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Created the folder description for Books")
  })

  it("writes the template alone when the purpose is left empty", async () => {
    setup()
    fireEvent.click(createButton())
    await waitFor(() => expect(api.saveFolderSettings).toHaveBeenCalled())
    expect(api.saveFolderSettings.mock.calls[0][1]).toMatchObject({ purpose: "", template: LINES })
  })

  it("writes one picked colour as a pair, the other theme's worked out", async () => {
    setup()
    fireEvent.change(screen.getByLabelText("Light theme colour"), { target: { value: "#aa3355" } })
    fireEvent.click(createButton())
    await waitFor(() => expect(api.saveFolderSettings).toHaveBeenCalled())
    const sent = api.saveFolderSettings.mock.calls[0][1]
    expect(sent.accent).toBe("#aa3355")
    expect(sent.accentDark).toMatch(/^#[0-9a-f]{6}$/)
    expect(sent.accentDark).not.toBe("#aa3355")
  })

  it("writes an icon and a colour chosen in the dialog", async () => {
    setup()
    fireEvent.change(iconField(), { target: { value: "travel" } })
    fireEvent.click(screen.getByRole("option", { name: "airplane" }))
    fireEvent.click(screen.getByRole("button", { name: "Rose" }))
    fireEvent.click(createButton())
    await waitFor(() => expect(api.saveFolderSettings).toHaveBeenCalled())
    expect(api.saveFolderSettings.mock.calls[0][1]).toMatchObject({ icon: "airplane", accent: "#be123c", accentDark: "#f2889b" })
  })

  it("can write an icon alone, with the purpose and the template cleared", async () => {
    setup()
    fireEvent.change(templateField(), { target: { value: "" } })
    expect(createButton().disabled).toBe(true)
    fireEvent.change(iconField(), { target: { value: "film" } })
    fireEvent.keyDown(iconField(), { key: "Enter" })
    expect(createButton().disabled).toBe(false)
    fireEvent.click(createButton())
    await waitFor(() => expect(api.saveFolderSettings).toHaveBeenCalled())
    expect(api.saveFolderSettings.mock.calls[0][1]).toMatchObject({ purpose: "", template: [""], icon: "film-roll" })
  })

  it("does not offer to create a definition with nothing in it", () => {
    setup()
    fireEvent.change(templateField(), { target: { value: " \n " } })
    expect(createButton().disabled).toBe(true)
    fireEvent.change(purposeField(), { target: { value: "Books." } })
    expect(createButton().disabled).toBe(false)
  })

  it("does not write twice when Create is clicked again while the first is in flight", async () => {
    api.saveFolderSettings.mockReturnValue(new Promise(() => {}))
    setup()
    fireEvent.click(createButton())
    await waitFor(() => expect(createButton().disabled).toBe(true))
    fireEvent.click(createButton())
    expect(api.saveFolderSettings).toHaveBeenCalledTimes(1)
  })

  it("keeps the dialog open with the reason when the server refuses", async () => {
    api.saveFolderSettings.mockResolvedValue({ ok: false, error: "A template line cannot start a code fence." })
    const { onClose, onSaved } = setup()
    fireEvent.click(createButton())
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith("A template line cannot start a code fence."))
    expect(onClose).not.toHaveBeenCalled()
    expect(onSaved).not.toHaveBeenCalled()
    expect(templateField().value).toBe(LINES.join("\n"))
    expect(createButton().disabled).toBe(false)
  })

  it("writes nothing on Skip", async () => {
    const { onClose, onSaved } = setup()
    fireEvent.click(button("Skip"))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.saveFolderSettings).not.toHaveBeenCalled()
    expect(onSaved).not.toHaveBeenCalled()
  })
})

describe("FolderSettingsDialog: opened by hand from a folder's menu", () => {
  const manual = (settings: FolderSettings) => setup({ folder: "Books", settings, manual: true })

  it("reads Cancel and Save, not Skip, and names the folder", () => {
    manual(NEW)
    expect(screen.getByText("Settings for Books")).toBeTruthy()
    expect(button("Cancel")).toBeTruthy()
    expect(button("Save")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Skip" })).toBeNull()
  })

  it("starts from the note's own values, with no word about where the template came from", () => {
    manual(DEFINED)
    expect(purposeField().value).toBe("Books I read.")
    expect(templateField().value).toBe("title:\nauthor:")
    expect(iconField().value).toBe("book")
    expect(screen.queryByText(/Started from/)).toBeNull()
    expect((screen.getByLabelText("Light theme colour") as HTMLInputElement).value).toBe("#1d4ed8")
    expect((screen.getByLabelText("Dark theme colour") as HTMLInputElement).value).toMatch(/^#[0-9a-f]{6}$/)
  })

  it("keeps Save off until something differs from the note", () => {
    manual(DEFINED)
    expect(button("Save").disabled).toBe(true)
    fireEvent.change(purposeField(), { target: { value: "Books I read.  " } })
    expect(button("Save").disabled).toBe(true) // trailing space is not a change
    fireEvent.change(purposeField(), { target: { value: "Books and papers." } })
    expect(button("Save").disabled).toBe(false)
    fireEvent.change(purposeField(), { target: { value: "Books I read." } })
    expect(button("Save").disabled).toBe(true)
  })

  it("offers Save when only the icon, or only a colour, differs from the note", () => {
    manual(DEFINED)
    fireEvent.change(iconField(), { target: { value: "film" } })
    fireEvent.keyDown(iconField(), { key: "Enter" })
    expect(button("Save").disabled).toBe(false)
    cleanup()
    manual(DEFINED)
    fireEvent.click(screen.getByRole("button", { name: "Rose" }))
    expect(button("Save").disabled).toBe(false)
  })

  it("lets a note's whole look be cleared and sends nulls for it", async () => {
    const { onSaved } = manual(DEFINED)
    fireEvent.click(screen.getByRole("button", { name: "Clear the icon" }))
    fireEvent.click(screen.getByRole("button", { name: "No colour" }))
    fireEvent.click(button("Save"))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.saveFolderSettings.mock.calls[0][1]).toEqual({
      purpose: "Books I read.",
      template: ["title:", "author:"],
      icon: null,
      accent: null,
      accentDark: null,
    })
  })

  it("says it saved, not created, when the note already existed", async () => {
    api.saveFolderSettings.mockResolvedValue({ ok: true, created: false })
    manual(DEFINED)
    fireEvent.change(purposeField(), { target: { value: "New." } })
    fireEvent.click(button("Save"))
    await waitFor(() => expect(notify.success).toHaveBeenCalledWith("Saved the settings for Books"))
  })

  it("lets a folder with no definition yet be saved by hand with just words", async () => {
    manual(NEW)
    expect(button("Save").disabled).toBe(false)
    fireEvent.click(button("Save"))
    await waitFor(() => expect(api.saveFolderSettings).toHaveBeenCalled())
  })

  it("keeps an icon name the set does not have, and writes it back unchanged", async () => {
    manual({ ...DEFINED, icon: "old-name" })
    expect(iconField().value).toBe("old-name")
    fireEvent.change(purposeField(), { target: { value: "Changed." } })
    fireEvent.click(button("Save"))
    await waitFor(() => expect(api.saveFolderSettings).toHaveBeenCalled())
    expect(api.saveFolderSettings.mock.calls[0][1]).toMatchObject({ icon: "old-name" })
  })
})
