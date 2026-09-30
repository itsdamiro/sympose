// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  fetchTrash: vi.fn(),
  restoreTrashNote: vi.fn(),
  purgeTrashNote: vi.fn(),
  emptyTrash: vi.fn(),
}))
vi.mock("@/lib/vault-trash-api", () => api)
const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))
vi.mock("@/lib/notify", () => ({ notify: { success: vi.fn(), error: vi.fn() } }))

import { TrashList } from "./trash-list"

const row = (path: string, extra: Record<string, unknown> = {}) => ({
  trash_path: path,
  original_path: path,
  deleted_at: Date.now() / 1000,
  size: 3,
  ...extra,
})

beforeEach(() => {
  api.fetchTrash.mockResolvedValue([row("Trip/Plan.md"), row("Trip/img/map.png"), row("Trip/board.canvas")])
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("TrashList", () => {
  it("lists a deleted folder's attachments beside its notes, counting them all as items", async () => {
    render(<TrashList persona="samantha" />)
    expect(await screen.findByText("3 items")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Restore Plan" })).toBeTruthy() // a note shows without .md
    expect(screen.getByRole("button", { name: "Restore map.png" })).toBeTruthy() // any other file by its name
    expect(screen.getByRole("button", { name: "Restore board.canvas" })).toBeTruthy()
  })

  it("says one item in the singular, and that notes and files land in an empty bin", async () => {
    api.fetchTrash.mockResolvedValue([row("map.png")])
    const { unmount } = render(<TrashList persona="samantha" />)
    expect(await screen.findByText("1 item")).toBeTruthy()
    unmount()
    api.fetchTrash.mockResolvedValue([])
    render(<TrashList persona="samantha" />)
    expect(await screen.findByText(/Deleted notes and files land here/)).toBeTruthy()
  })

  it("restores an attachment by its bin path and tells the shell where it went, even when the two differ", async () => {
    api.fetchTrash.mockResolvedValue([row("Trip-20260101000000/img/map.png", { original_path: "Trip/img/map.png" })])
    api.restoreTrashNote.mockResolvedValue({ ok: true, detail: "Restored to `Trip/img/map.png`" })
    const onRestored = vi.fn()
    render(<TrashList persona="samantha" onRestored={onRestored} />)
    fireEvent.click(await screen.findByRole("button", { name: "Restore map.png" }))
    await waitFor(() => expect(api.restoreTrashNote).toHaveBeenCalledWith("Trip-20260101000000/img/map.png", "samantha"))
    await waitFor(() => expect(onRestored).toHaveBeenCalledWith("Trip/img/map.png"))
  })

  it("names the file, whatever its kind, when asking before deleting one for good", async () => {
    render(<TrashList persona="samantha" />)
    fireEvent.click(await screen.findByRole("button", { name: "Delete map.png permanently" }))
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
})
