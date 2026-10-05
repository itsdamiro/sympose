// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { Folder01Icon, File01Icon } from "@hugeicons/core-free-icons"

const api = vi.hoisted(() => ({ renameVaultFolder: vi.fn(), renameVaultNote: vi.fn(), deleteVaultNote: vi.fn() }))
vi.mock("@/lib/vault-note-api", () => api)
vi.mock("@/lib/notify", () => ({ notify: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import { MainMenu, type MainMenuItem } from "./main-menu"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const items: MainMenuItem[] = [
  { id: "People", label: "People", icon: Folder01Icon, type: "folder" },
  { id: "README.md", label: "README", icon: File01Icon, type: "note" },
]

function setup(extra: Partial<React.ComponentProps<typeof MainMenu>> = {}) {
  const handlers = { onDeleteItem: vi.fn(), onDefineItem: vi.fn(), onHideItem: vi.fn(), onRenameFolder: vi.fn() }
  render(<MainMenu items={items} persona="samantha" defaultCollapsed={false} {...handlers} {...extra} />)
  return handlers
}

describe("MainMenu: renaming a root folder (docs/decisions/073)", () => {
  it("adds Rename folder to a folder row's menu, after Define folder, once the shell wires it", async () => {
    setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))

    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual([
      "Define folder",
      "Rename folder",
      "Hide from view",
      "Delete folder",
    ])
  })

  it("does not offer it on a note's row, nor when the shell has not wired it", async () => {
    setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "README" }))
    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual(["Hide from view"])
    cleanup()

    setup({ onRenameFolder: undefined })
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).not.toContain("Rename folder")
  })

  it("is not offered on the collapsed rail, which has no room for the field", async () => {
    setup({ defaultCollapsed: true })
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))

    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).not.toContain("Rename folder")
  })

  it("is not offered without a persona to rename as", async () => {
    setup({ persona: undefined })
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))

    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).not.toContain("Rename folder")
  })

  it("is the only item when it is the only thing wired, and with no persona the row has no menu at all", async () => {
    render(<MainMenu items={items} persona="samantha" onRenameFolder={vi.fn()} />)
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    expect((await screen.findAllByRole("menuitem")).map((m) => m.textContent)).toEqual(["Rename folder"])
    cleanup()

    render(<MainMenu items={items} onRenameFolder={vi.fn()} />)
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.queryAllByRole("menuitem")).toEqual([])
  })

  it("opens a field on the folder's name, and Enter sends the new name to the folder route and tells the shell", async () => {
    api.renameVaultFolder.mockResolvedValue({ ok: true, path: "Team", detail: "Renamed to `Team`", personas: [], personasUnchanged: [], relinkFailed: 0 })
    const h = setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename folder" }))

    const input = (await screen.findByRole("textbox", { name: "Rename People" })) as HTMLInputElement
    expect(input.value).toBe("People")
    fireEvent.change(input, { target: { value: "Team" } })
    fireEvent.keyDown(input, { key: "Enter" })

    await waitFor(() => expect(api.renameVaultFolder).toHaveBeenCalledWith("People", "Team", "samantha"))
    await waitFor(() => expect(h.onRenameFolder).toHaveBeenCalledWith("People", "Team"))
  })

  it("waits for the shell to save what is unsaved, and sends nothing when that fails", async () => {
    const onBeforeRenameFolder = vi.fn(async () => false)
    const h = setup({ onBeforeRenameFolder })
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename folder" }))
    const input = await screen.findByRole("textbox", { name: "Rename People" })
    fireEvent.change(input, { target: { value: "Team" } })
    fireEvent.keyDown(input, { key: "Enter" })

    await waitFor(() => expect(onBeforeRenameFolder).toHaveBeenCalledTimes(1))
    await new Promise((r) => setTimeout(r, 30))
    expect(api.renameVaultFolder).not.toHaveBeenCalled()
    expect(h.onRenameFolder).not.toHaveBeenCalled()
  })

  it("leaves the folder alone when the field is cancelled with Escape", async () => {
    const h = setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename folder" }))
    const input = await screen.findByRole("textbox", { name: "Rename People" })
    fireEvent.change(input, { target: { value: "Team" } })

    fireEvent.keyDown(input, { key: "Escape" })

    expect(screen.queryByRole("textbox")).toBeNull()
    expect(api.renameVaultFolder).not.toHaveBeenCalled()
    expect(h.onRenameFolder).not.toHaveBeenCalled()
  })

  it("keeps its other items acting on their own row", async () => {
    const h = setup()
    fireEvent.contextMenu(screen.getByRole("button", { name: "People" }))
    fireEvent.click(await screen.findByRole("menuitem", { name: "Delete folder" }))

    expect(h.onDeleteItem).toHaveBeenCalledWith(items[0])
  })
})
