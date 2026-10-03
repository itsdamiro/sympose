// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { FolderSetupDialog } from "./folder-setup-dialog"
import type { NoteTemplate } from "@/lib/vault-definition-api"

const api = vi.hoisted(() => ({ createFolderDefinition: vi.fn() }))
vi.mock("@/lib/vault-definition-api", () => api)
const notify = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock("@/lib/notify", () => ({ notify }))

const LINES = ['title: "{{title}}"', "created: {{date}}", "tags: []"]
const SETTINGS: NoteTemplate = { lines: LINES, source: "settings", definable: true }
type Setup = { folder: string; template: NoteTemplate } | null

beforeEach(() => {
  api.createFolderDefinition.mockResolvedValue({ ok: true, path: "Books" })
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function setup(setupArg: Setup = { folder: "Books", template: SETTINGS }) {
  const onClose = vi.fn()
  const onCreated = vi.fn()
  const props = { persona: "samantha", onClose, onCreated }
  const view = render(<FolderSetupDialog setup={setupArg} {...props} />)
  return { onClose, onCreated, props, ...view }
}

const templateField = () =>
  screen.getByLabelText(/Properties new notes start with/) as HTMLTextAreaElement
const purposeField = () =>
  screen.getByLabelText(/What is this folder for/) as HTMLTextAreaElement
const createButton = () =>
  screen.getByRole("button", { name: "Create the definition" }) as HTMLButtonElement

describe("FolderSetupDialog", () => {
  it("shows nothing while no folder was just created", () => {
    setup(null)
    expect(screen.queryByText(/Set up/)).toBeNull()
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("starts the template from the one it was given and says where it came from", () => {
    setup()
    expect(templateField().value).toBe(LINES.join("\n"))
    expect(screen.getByText(/Started from the default keys/)).toBeTruthy()
    expect(purposeField().value).toBe("")
  })

  it("says so when the lines are the vault's own note template", () => {
    setup({ folder: "Books", template: { lines: ["title:"], source: "vault" } })
    expect(screen.getByText(/Started from your Templates\/Note template\.md/)).toBeTruthy()
    expect(templateField().value).toBe("title:")
  })

  it("starts empty for the next folder instead of carrying the last one's words over", () => {
    const { rerender, props } = setup()
    fireEvent.change(purposeField(), { target: { value: "Books I read." } })
    fireEvent.change(templateField(), { target: { value: "edited:" } })
    rerender(
      <FolderSetupDialog
        setup={{ folder: "Films", template: SETTINGS }}
        {...props}
      />
    )
    expect(screen.getByText("Set up Films")).toBeTruthy()
    expect(purposeField().value).toBe("")
    expect(templateField().value).toBe(LINES.join("\n"))
  })

  it("writes what the user typed, trimmed, and then closes and refreshes", async () => {
    const { onClose, onCreated } = setup()
    fireEvent.change(purposeField(), { target: { value: "  What I read.  " } })
    fireEvent.change(templateField(), { target: { value: "title:\nauthor:" } })
    fireEvent.click(createButton())
    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1))
    expect(api.createFolderDefinition).toHaveBeenCalledExactlyOnceWith(
      "Books",
      "What I read.",
      ["title:", "author:"],
      "samantha"
    )
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(notify.success).toHaveBeenCalledWith("Created Books/Books.md")
  })

  it("writes the template alone when the purpose is left empty", async () => {
    setup()
    fireEvent.click(createButton())
    await waitFor(() => expect(api.createFolderDefinition).toHaveBeenCalled())
    expect(api.createFolderDefinition.mock.calls[0].slice(1, 3)).toEqual(["", LINES])
  })

  it("writes the purpose alone when the template is cleared", async () => {
    setup()
    fireEvent.change(purposeField(), { target: { value: "Books." } })
    fireEvent.change(templateField(), { target: { value: "" } })
    fireEvent.click(createButton())
    await waitFor(() => expect(api.createFolderDefinition).toHaveBeenCalled())
    expect(api.createFolderDefinition.mock.calls[0].slice(1, 3)).toEqual(["Books.", [""]])
  })

  it("does not offer to create a definition with nothing in it", () => {
    setup()
    fireEvent.change(templateField(), { target: { value: " \n " } })
    expect(createButton().disabled).toBe(true)
    fireEvent.change(purposeField(), { target: { value: "Books." } })
    expect(createButton().disabled).toBe(false)
  })

  it("does not write twice when Create is clicked again while the first is in flight", async () => {
    api.createFolderDefinition.mockReturnValue(new Promise(() => {}))
    setup()
    fireEvent.click(createButton())
    await waitFor(() => expect(createButton().disabled).toBe(true))
    fireEvent.click(createButton())
    expect(api.createFolderDefinition).toHaveBeenCalledTimes(1)
  })

  it("keeps the dialog open with the reason when the server refuses", async () => {
    api.createFolderDefinition.mockResolvedValue({
      ok: false,
      error: "A template line cannot start a code fence.",
    })
    const { onClose, onCreated } = setup()
    fireEvent.click(createButton())
    await waitFor(() =>
      expect(notify.error).toHaveBeenCalledWith("A template line cannot start a code fence.")
    )
    expect(onClose).not.toHaveBeenCalled()
    expect(onCreated).not.toHaveBeenCalled()
    expect(templateField().value).toBe(LINES.join("\n"))
    expect(createButton().disabled).toBe(false)
  })

  it("writes nothing on Skip", async () => {
    const { onClose, onCreated } = setup()
    fireEvent.click(screen.getByRole("button", { name: "Skip" }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.createFolderDefinition).not.toHaveBeenCalled()
    expect(onCreated).not.toHaveBeenCalled()
  })

  it("reads Define, Cancel and Save when opened by hand from a folder's menu", () => {
    render(<FolderSetupDialog setup={{ folder: "Books", template: SETTINGS, manual: true }} persona="samantha" onClose={vi.fn()} onCreated={vi.fn()} />)
    expect(screen.getByText("Define Books")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Cancel" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Save" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Skip" })).toBeNull()
  })
})
