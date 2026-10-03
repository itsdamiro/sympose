// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  fetchBinnedSessions: vi.fn(),
  restoreSession: vi.fn(),
  purgeSession: vi.fn(),
  emptyBinnedSessions: vi.fn(),
}))
vi.mock("@/lib/sessions-api", () => api)
const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))
vi.mock("@/lib/notify", () => ({ notify: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import { ConversationBin } from "./conversation-bin"

const row = (id: string, title: string, turns = 3) => ({ id, title, turns, deleted_at: Date.now() / 1000 - 7200, pinned_at: null })

beforeEach(() => {
  api.fetchBinnedSessions.mockResolvedValue([row("a", "The movies"), row("b", "Garden plans", 1)])
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** Chooses an action from a row's `⋯` menu, as a user does. */
const pick = async (row: string, item: string) => {
  fireEvent.click(await screen.findByRole("button", { name: `Actions for ${row}` }))
  fireEvent.click(await screen.findByRole("menuitem", { name: item }))
}

describe("ConversationBin", () => {
  it("lists the deleted conversations with their turns and when they were deleted", async () => {
    render(<ConversationBin persona="samantha" />)
    expect(await screen.findByText("The movies")).toBeTruthy()
    expect(screen.getByText("3 turns · deleted 2h ago")).toBeTruthy()
    expect(screen.getByText("1 turn · deleted 2h ago")).toBeTruthy()
    expect(screen.getByText("2 conversations")).toBeTruthy()
  })

  it("does not show one persona's deleted conversations under another, while the other's load or when they fail to", async () => {
    const { rerender } = render(<ConversationBin persona="samantha" />)
    expect(await screen.findByText("The movies")).toBeTruthy()
    api.fetchBinnedSessions.mockResolvedValue(null) // the other persona's list cannot be read
    rerender(<ConversationBin persona="aria" />)
    await waitFor(() => expect(api.fetchBinnedSessions).toHaveBeenCalledWith("aria"))
    expect(screen.queryByText("The movies")).toBeNull()
    expect(screen.queryByText("2 conversations")).toBeNull()
  })

  it("draws each row as a search result is drawn: an icon, the title and a detail line beneath it", async () => {
    render(<ConversationBin persona="samantha" />)
    await screen.findByText("The movies")
    const blocks = document.querySelectorAll('[data-slot="result-text"]')
    expect(blocks).toHaveLength(2)
    expect(blocks[0].textContent).toContain("The movies")
    expect(blocks[0].textContent).toContain("3 turns · deleted 2h ago")
    expect(blocks[0].querySelector("svg")).toBeTruthy()
  })

  it("is not dressed as clickable: its title does not react to the pointer, and its actions are the shared row menu", async () => {
    render(<ConversationBin persona="samantha" />)
    await screen.findByText("The movies")
    const row = screen.getByText("The movies").closest('[data-slot="result-text"]')?.parentElement?.parentElement as HTMLElement
    expect(row.className).not.toContain("group/result")
    const dots = screen.getByRole("button", { name: "Actions for The movies" })
    expect(dots.className).toContain("group-hover/row:opacity-100")
    expect(dots.className).toContain("hover:bg-accent")
  })

  it("offers Restore and Delete permanently from a right click as well as from the button", async () => {
    render(<ConversationBin persona="samantha" />)
    fireEvent.contextMenu(await screen.findByText("The movies"))
    expect(await screen.findByRole("menuitem", { name: "Restore" })).toBeTruthy()
    expect(screen.getByRole("menuitem", { name: "Delete permanently" })).toBeTruthy()
  })

  it("says when there are none", async () => {
    api.fetchBinnedSessions.mockResolvedValue([])
    render(<ConversationBin persona="samantha" />)
    expect(await screen.findByText("No deleted conversations")).toBeTruthy()
  })

  it("restores one by its name in the bin, tells the shell and reads the list again", async () => {
    api.restoreSession.mockResolvedValue({ ok: true, value: undefined })
    const onRestored = vi.fn()
    render(<ConversationBin persona="samantha" onRestored={onRestored} />)
    await pick("The movies", "Restore")
    await waitFor(() => expect(api.restoreSession).toHaveBeenCalledWith("samantha", "a"))
    await waitFor(() => expect(onRestored).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(api.fetchBinnedSessions).toHaveBeenCalledTimes(2))
  })

  it("says why a restore was refused and leaves the shell alone", async () => {
    api.restoreSession.mockResolvedValue({ ok: false, error: "A conversation with that id is already there." })
    const onRestored = vi.fn()
    render(<ConversationBin persona="samantha" onRestored={onRestored} />)
    await pick("The movies", "Restore")
    const { notify } = await import("@/lib/notify")
    await waitFor(() => expect(notify.error).toHaveBeenCalledWith("A conversation with that id is already there."))
    expect(onRestored).not.toHaveBeenCalled()
  })

  it("always asks before deleting for good, and deletes only on the answer", async () => {
    api.purgeSession.mockResolvedValue({ ok: true, value: undefined })
    render(<ConversationBin persona="samantha" />)
    await pick("The movies", "Delete permanently")
    const request = confirmMock.mock.calls[0][0]
    expect(request.permanent).toBe(true)
    expect(request.message).toBe("Delete “The movies” forever?")
    expect(api.purgeSession).not.toHaveBeenCalled()
    await request.onConfirm()
    expect(api.purgeSession).toHaveBeenCalledWith("samantha", "a")
  })

  it("always asks before emptying, and says how many it deleted", async () => {
    api.emptyBinnedSessions.mockResolvedValue({ ok: true, value: 2 })
    render(<ConversationBin persona="samantha" />)
    fireEvent.click(await screen.findByRole("button", { name: "Empty" }))
    const request = confirmMock.mock.calls[0][0]
    expect(request.permanent).toBe(true)
    expect(request.description).toContain("2 conversations")
    await request.onConfirm()
    const { notify } = await import("@/lib/notify")
    expect(notify.success).toHaveBeenCalledWith("Deleted 2 conversations for good")
  })

  it("says so, and offers to try again, when the list cannot be loaded", async () => {
    api.fetchBinnedSessions.mockResolvedValueOnce(null).mockResolvedValue([row("a", "The movies")])
    render(<ConversationBin persona="samantha" />)
    expect(await screen.findByText(/Couldn.t load the deleted conversations/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Try again" }))
    expect(await screen.findByText("The movies")).toBeTruthy()
  })

  it("reads the list again when the shell says a conversation was deleted from the list", async () => {
    const { rerender } = render(<ConversationBin persona="samantha" refreshKey={0} />)
    await screen.findByText("The movies")
    rerender(<ConversationBin persona="samantha" refreshKey={1} />)
    await waitFor(() => expect(api.fetchBinnedSessions).toHaveBeenCalledTimes(2))
  })
})
