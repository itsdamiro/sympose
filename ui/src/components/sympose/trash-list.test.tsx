// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  fetchTrash: vi.fn(),
  restoreTrashFolder: vi.fn(),
  restoreTrashNote: vi.fn(),
  purgeTrashNote: vi.fn(),
  emptyTrash: vi.fn(),
}))
vi.mock("@/lib/vault-trash-api", () => api)
const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))
vi.mock("@/lib/notify", () => ({ notify: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import { TrashList } from "./trash-list"

/** Chooses an action from a row's `⋯` menu, as a user does. */
const pick = async (row: string, item: string) => {
  fireEvent.click(await screen.findByRole("button", { name: `Actions for ${row}` }))
  fireEvent.click(await screen.findByRole("menuitem", { name: item }))
}

const row = (path: string, extra: Record<string, unknown> = {}) => ({
  trash_path: path,
  original_path: path,
  deleted_at: Date.now() / 1000,
  size: 3,
  ...extra,
})

const bin = (items: ReturnType<typeof row>[], folders: unknown[] = []) => ({ items, folders })

beforeEach(() => {
  api.fetchTrash.mockResolvedValue(bin([row("Trip/Plan.md"), row("Trip/img/map.png"), row("Trip/board.canvas")]))
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("TrashList", () => {
  it("offers Restore and Delete permanently from a right click as well as from the button", async () => {
    render(<TrashList persona="samantha" />)
    fireEvent.contextMenu(await screen.findByText("map.png"))
    expect(await screen.findByRole("menuitem", { name: "Restore" })).toBeTruthy()
    expect(screen.getByRole("menuitem", { name: "Delete permanently" })).toBeTruthy()
  })

  it("lists a deleted folder's attachments beside its notes, counting them all as items", async () => {
    render(<TrashList persona="samantha" />)
    expect(await screen.findByText("3 items")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Actions for Plan" })).toBeTruthy() // a note shows without .md
    expect(screen.getByRole("button", { name: "Actions for map.png" })).toBeTruthy() // any other file by its name
    expect(screen.getByRole("button", { name: "Actions for board.canvas" })).toBeTruthy()
  })

  it("says one item in the singular, and that notes and files land in an empty bin", async () => {
    api.fetchTrash.mockResolvedValue(bin([row("map.png")]))
    const { unmount } = render(<TrashList persona="samantha" />)
    expect(await screen.findByText("1 item")).toBeTruthy()
    unmount()
    api.fetchTrash.mockResolvedValue(bin([]))
    render(<TrashList persona="samantha" />)
    expect(await screen.findByText(/Deleted notes and files land here/)).toBeTruthy()
  })

  it("restores an attachment by its bin path and tells the shell where it went, even when the two differ", async () => {
    api.fetchTrash.mockResolvedValue(bin([row("Trip-20260101000000/img/map.png", { original_path: "Trip/img/map.png" })]))
    api.restoreTrashNote.mockResolvedValue({ ok: true, detail: "Restored to `Trip/img/map.png`" })
    const onRestored = vi.fn()
    render(<TrashList persona="samantha" onRestored={onRestored} />)
    await pick("map.png", "Restore")
    await waitFor(() => expect(api.restoreTrashNote).toHaveBeenCalledWith("Trip-20260101000000/img/map.png", "samantha"))
    await waitFor(() => expect(onRestored).toHaveBeenCalledWith("Trip/img/map.png"))
  })

  it("names the file, whatever its kind, when asking before deleting one for good", async () => {
    render(<TrashList persona="samantha" />)
    await pick("map.png", "Delete permanently")
    expect(confirmMock.mock.calls[0][0].message).toBe("Delete “map.png” forever?")
    expect(confirmMock.mock.calls[0][0].permanent).toBe(true)
  })

  it("asks before emptying that everything in the bin, not only notes, goes for good", async () => {
    render(<TrashList persona="samantha" />)
    fireEvent.click(await screen.findByRole("button", { name: "Empty bin" }))
    const request = confirmMock.mock.calls[0][0]
    expect(request.description).toBe("Permanently deletes everything in the bin (3 items) from disk. This cannot be undone.")
    expect(request.permanent).toBe(true)
  })

  describe("a folder deleted as a unit (docs/decisions/050)", () => {
    const folder = { trash_dir: "Trip", original_path: "Trip", deleted_at: Date.now() / 1000, count: 2 }
    const inTrip = [row("Trip/a.md", { folder: "Trip" }), row("Trip/img/b.png", { folder: "Trip" })]

    it("shows it as one row with its file count, the files inside only once it is opened, and loose files beside it", async () => {
      api.fetchTrash.mockResolvedValue(bin([...inTrip, row("Loose.md")], [folder]))
      render(<TrashList persona="samantha" />)
      expect(await screen.findByText("Trip/")).toBeTruthy()
      expect(screen.getByText(/2 files, deleted/)).toBeTruthy()
      expect(screen.getByRole("button", { name: "Actions for Loose" })).toBeTruthy()
      expect(screen.queryByRole("button", { name: "Actions for a" })).toBeNull() // folded away
      fireEvent.click(screen.getByRole("button", { name: /Trip\// }))
      expect(screen.getByRole("button", { name: "Actions for a" })).toBeTruthy()
      expect(screen.getByRole("button", { name: "Actions for b.png" })).toBeTruthy()
    })

    it("restores the folder whole and tells the shell, saying plainly when something was skipped", async () => {
      api.fetchTrash.mockResolvedValue(bin(inTrip, [folder]))
      api.restoreTrashFolder.mockResolvedValue({ ok: true, detail: "Restored 1 of 2 files. Skipped 1: a.md.", restored: ["Trip/img/b.png"], skipped: [{ path: "Trip/a.md", reason: "already exists" }] })
      const onRestored = vi.fn()
      render(<TrashList persona="samantha" onRestored={onRestored} />)
      await pick("folder Trip", "Restore folder")
      await waitFor(() => expect(api.restoreTrashFolder).toHaveBeenCalledWith("Trip", "samantha"))
      const { notify } = await import("@/lib/notify")
      await waitFor(() => expect(notify.warning).toHaveBeenCalledWith("Restored 1 of 2 files. Skipped 1: a.md."))
      expect(onRestored).toHaveBeenCalledWith("Trip/img/b.png")
    })

    it("shows the error and changes nothing when the folder could not be restored", async () => {
      api.fetchTrash.mockResolvedValue(bin(inTrip, [folder]))
      api.restoreTrashFolder.mockResolvedValue({ ok: false, error: "boom" })
      render(<TrashList persona="samantha" />)
      await pick("folder Trip", "Restore folder")
      const { notify } = await import("@/lib/notify")
      await waitFor(() => expect(notify.error).toHaveBeenCalledWith("boom"))
    })
  })

  describe("when the bin cannot be loaded (#90)", () => {
    it("says so and offers to try again, instead of showing an empty bin", async () => {
      api.fetchTrash.mockResolvedValueOnce(null).mockResolvedValue(bin([row("a.md")]))
      render(<TrashList persona="samantha" />)
      expect(await screen.findByText(/Couldn.t load the bin/)).toBeTruthy()
      expect(screen.queryByText(/No deleted notes/)).toBeNull()
      fireEvent.click(screen.getByRole("button", { name: "Try again" }))
      expect(await screen.findByText("1 item")).toBeTruthy()
    })

    it("keeps the bin it had, with a line saying the refresh failed", async () => {
      api.fetchTrash.mockResolvedValueOnce(bin([row("a.md")])).mockResolvedValue(null)
      const { rerender } = render(<TrashList persona="samantha" refreshKey={0} />)
      expect(await screen.findByText("1 item")).toBeTruthy()
      rerender(<TrashList persona="samantha" refreshKey={1} />)
      expect(await screen.findByText(/Couldn.t refresh the bin/)).toBeTruthy()
      expect(screen.getByText("1 item")).toBeTruthy()
    })
  })
})
