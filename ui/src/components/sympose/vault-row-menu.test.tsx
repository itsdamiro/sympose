// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"

const api = vi.hoisted(() => ({
  createVaultNote: vi.fn(),
  deleteVaultFolder: vi.fn(),
  deleteVaultNote: vi.fn(),
  renameVaultFolder: vi.fn(),
  renameVaultNote: vi.fn(),
}))
vi.mock("@/lib/vault-note-api", () => api)
vi.mock("@/lib/notify", () => ({ notify: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import type { VaultNode } from "@/components/sympose/vault-tree"
import { VaultRowMenu } from "./vault-row-menu"

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const folder: VaultNode = { name: "People", path: "People", type: "folder", children: [{ name: "Anna.md", path: "People/Anna.md", type: "note" }] }
const note: VaultNode = { name: "Anna.md", path: "People/Anna.md", type: "note" }

function show(node: VaultNode, over: Partial<React.ComponentProps<typeof VaultRowMenu>> = {}) {
  render(
    <VaultRowMenu node={node} persona="samantha" paddingLeft={8} onRenamed={vi.fn()} onDeleted={vi.fn()} onCreated={vi.fn()} {...over}>
      <button type="button">{node.name}</button>
    </VaultRowMenu>
  )
  fireEvent.contextMenu(screen.getByText(node.name))
}

describe("VaultRowMenu: renaming a folder (docs/decisions/073)", () => {
  it("offers Rename on a folder row, beside New note here and Delete, once the app wires it", async () => {
    show(folder, { onFolderRenamed: vi.fn() })

    expect(await screen.findByRole("menuitem", { name: "Rename" })).toBeTruthy()
    expect(screen.getByRole("menuitem", { name: "New note here" })).toBeTruthy()
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeTruthy()
  })

  it("does not offer it on a folder row where the app has not wired it (a bare tree)", async () => {
    show(folder)

    expect(await screen.findByRole("menuitem", { name: "New note here" })).toBeTruthy()
    expect(screen.queryByRole("menuitem", { name: "Rename" })).toBeNull()
  })

  it("still offers a note's own Rename, whether or not folders are wired", async () => {
    show(note)

    expect(await screen.findByRole("menuitem", { name: "Rename" })).toBeTruthy()
  })
})

describe("VaultRowMenu: the rename field on a folder row", () => {
  async function renameThrough(node: VaultNode, text: string, props: Partial<React.ComponentProps<typeof VaultRowMenu>>) {
    show(node, props)
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))
    const input = (await screen.findByRole("textbox")) as HTMLInputElement
    fireEvent.change(input, { target: { value: text } })
    fireEvent.keyDown(input, { key: "Enter" })
  }

  it("opens on the folder's own name, sends the new one to the folder route, and tells the folder callback, not the note's", async () => {
    api.renameVaultFolder.mockResolvedValue({ ok: true, path: "Team", detail: "Renamed to `Team`", personas: [], personasUnchanged: [], relinkFailed: 0 })
    const onFolderRenamed = vi.fn()
    const onRenamed = vi.fn()

    await renameThrough(folder, "Team", { onFolderRenamed, onRenamed })

    await waitFor(() => expect(api.renameVaultFolder).toHaveBeenCalledWith("People", "Team", "samantha"))
    await waitFor(() => expect(onFolderRenamed).toHaveBeenCalledWith("People", "Team"))
    expect(onRenamed).not.toHaveBeenCalled()
    expect(api.renameVaultNote).not.toHaveBeenCalled()
  })

  it("starts from the folder's name as it is, including a dot in it (a folder is not a note)", async () => {
    show({ ...folder, name: "v1.md", path: "v1.md" }, { onFolderRenamed: vi.fn() })
    fireEvent.click(await screen.findByRole("menuitem", { name: "Rename" }))

    expect(((await screen.findByRole("textbox")) as HTMLInputElement).value).toBe("v1.md")
  })

  it("renames a note through the note route and tells the note callback", async () => {
    api.renameVaultNote.mockResolvedValue({ ok: true, path: "People/Ann.md", detail: "Renamed" })
    const onRenamed = vi.fn()
    const onFolderRenamed = vi.fn()

    await renameThrough(note, "Ann", { onRenamed, onFolderRenamed })

    await waitFor(() => expect(onRenamed).toHaveBeenCalledWith("People/Anna.md", "People/Ann.md"))
    expect(api.renameVaultFolder).not.toHaveBeenCalled()
    expect(onFolderRenamed).not.toHaveBeenCalled()
  })

  it("waits for the app to save what is unsaved before it sends the folder's rename, and sends nothing when that fails", async () => {
    api.renameVaultFolder.mockResolvedValue({ ok: true, path: "Team", detail: "Renamed", personas: [], personasUnchanged: [], relinkFailed: 0 })
    const onBeforeFolderRename = vi.fn(async () => false)
    const onFolderRenamed = vi.fn()

    await renameThrough(folder, "Team", { onFolderRenamed, onBeforeFolderRename })

    await waitFor(() => expect(onBeforeFolderRename).toHaveBeenCalledTimes(1))
    await new Promise((r) => setTimeout(r, 30))
    expect(api.renameVaultFolder).not.toHaveBeenCalled()
    expect(onFolderRenamed).not.toHaveBeenCalled()
  })

  it("sends it once the save has gone through", async () => {
    api.renameVaultFolder.mockResolvedValue({ ok: true, path: "Team", detail: "Renamed", personas: [], personasUnchanged: [], relinkFailed: 0 })
    const onBeforeFolderRename = vi.fn(async () => true)

    await renameThrough(folder, "Team", { onFolderRenamed: vi.fn(), onBeforeFolderRename })

    await waitFor(() => expect(api.renameVaultFolder).toHaveBeenCalledWith("People", "Team", "samantha"))
    expect(onBeforeFolderRename).toHaveBeenCalledTimes(1)
  })
})

