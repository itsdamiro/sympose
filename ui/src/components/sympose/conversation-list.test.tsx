// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ListedSession } from "@/lib/use-session-list"
import { ConversationList } from "./conversation-list"

const row = (id: string, extra: Partial<ListedSession> = {}): ListedSession => ({
  id,
  title: `Title ${id}`,
  turns: 2,
  created_at: null,
  updated_at: new Date(Date.now() - 3 * 3600 * 1000).toISOString(),
  pinned_at: null,
  replying: false,
  unread: false,
  current: false,
  ...extra,
})

function setup(sessions: ListedSession[]) {
  const spies = {
    onOpen: vi.fn(),
    onRename: vi.fn().mockResolvedValue(true),
    onPin: vi.fn(),
    onDelete: vi.fn(),
  }
  render(<ConversationList sessions={sessions} {...spies} />)
  return spies
}

afterEach(cleanup)

describe("ConversationList", () => {
  it("lists each conversation with its turns and age, and opens one on a click", () => {
    const spies = setup([row("a"), row("b", { turns: 1 })])
    expect(screen.getByText("2 turns · 3h ago")).toBeTruthy()
    expect(screen.getByText("1 turn · 3h ago")).toBeTruthy()
    fireEvent.click(screen.getByText("Title b"))
    expect(spies.onOpen).toHaveBeenCalledWith("b")
  })

  it("draws each row as a search result is drawn: an icon, the title and a detail line beneath it", () => {
    setup([row("b", { pinned_at: "2026-10-01T00:00:00Z" }), row("a")]) // the list comes pinned first
    const blocks = document.querySelectorAll('[data-slot="result-text"]')
    expect(blocks).toHaveLength(2)
    expect(blocks[0].querySelector('svg[aria-label="Pinned"]')).toBeTruthy() // a pinned one shows the pin in the icon's place
    expect(blocks[1].textContent).toContain("Title a")
    expect(blocks[1].textContent).toContain("2 turns · 3h ago")
    expect(blocks[1].querySelector("svg")).toBeTruthy()
  })

  it("separates pinned from recent conversations with the folder list's captions, only when there are both", () => {
    setup([row("a", { pinned_at: "2026-10-01T00:00:00Z" }), row("b"), row("c")])
    const captions = Array.from(document.querySelectorAll('[data-slot="group-caption"]')).map((c) => c.textContent)
    expect(captions).toEqual(["Pinned", "All conversations"])
    cleanup()
    setup([row("a"), row("b")])
    expect(document.querySelectorAll('[data-slot="group-caption"]')).toHaveLength(0)
    cleanup()
    setup([row("a", { pinned_at: "2026-10-01T00:00:00Z" })]) // nothing recent to separate it from
    expect(screen.queryByText("All conversations")).toBeNull()
  })

  it("sets the recent conversations well apart from the pinned: about three times the space between two rows", () => {
    setup([row("a", { pinned_at: "2026-10-01T00:00:00Z" }), row("b")])
    const [pinned, recent] = Array.from(document.querySelectorAll('[data-slot="group-caption"]')) as HTMLElement[]
    expect(recent.className).toContain("pt-8") // 32 px above it; two rows are 10 px apart, a folder list's groups 12 px
    expect(pinned.className).not.toContain("pt-8") // the first caption opens the list
  })

  it("sits flush with its heading and has no box, as a folder item does: the open one is marked by its title", () => {
    setup([row("a", { current: true }), row("b")])
    const open = screen.getByText("Title a").closest("button") as HTMLElement
    const other = screen.getByText("Title b").closest("button") as HTMLElement
    for (const button of [open, other]) {
      expect(button.className).not.toContain("px-2")
      expect(button.className).not.toContain("bg-accent")
    }
    expect(open.getAttribute("aria-current")).toBe("true")
    expect(screen.getByText("Title a").parentElement?.className).toContain("font-medium")
    expect(screen.getByText("Title b").parentElement?.className).not.toContain("font-medium")
  })

  it("has the same hover control as a folder item: one shared look for the three-dots button", () => {
    setup([row("a")])
    const dots = screen.getByRole("button", { name: "Actions for Title a" })
    expect(dots.className).toContain("hover:bg-accent")
    expect(dots.className).not.toContain("hover:bg-background")
    expect(dots.className).toContain("group-hover/row:opacity-100")
  })

  it("names a conversation with no title and says when there are none", () => {
    setup([row("a", { title: "" })])
    expect(screen.getByText("New conversation")).toBeTruthy()
    cleanup()
    setup([])
    expect(screen.getByText("No conversations yet")).toBeTruthy()
  })

  it("marks the one on screen, the pinned, the replying and the unread", () => {
    setup([
      row("a", { current: true }),
      row("b", { pinned_at: "2026-10-01T10:00:00+00:00" }),
      row("c", { replying: true, unread: true }),
      row("d", { unread: true }),
    ])
    expect(screen.getByText("Title a").closest("button")?.getAttribute("aria-current")).toBe("true")
    expect(screen.getByLabelText("Pinned")).toBeTruthy()
    expect(screen.getByText("replying…")).toBeTruthy()
    expect(screen.getAllByLabelText("New reply")).toHaveLength(1) // one that is replying does not also show the dot
  })

  it("has no title line and no New button: the list is only its conversations (a new one starts from the chat)", () => {
    setup([row("a"), row("b")])
    expect(screen.queryByText("Conversations")).toBeNull()
    expect(screen.queryByRole("button", { name: "New" })).toBeNull()
    expect(screen.getByRole("region", { name: "Conversations" })).toBeTruthy() // still named for a screen reader
  })

  it("pins and unpins from the row's menu", async () => {
    const spies = setup([row("a"), row("b", { pinned_at: "2026-10-01T10:00:00+00:00" })])
    fireEvent.click(screen.getByRole("button", { name: "Actions for Title a" }))
    fireEvent.click(await screen.findByText("Pin conversation"))
    expect(spies.onPin).toHaveBeenCalledWith("a", true)
    cleanup()
    const again = setup([row("b", { pinned_at: "2026-10-01T10:00:00+00:00" })])
    fireEvent.click(screen.getByRole("button", { name: "Actions for Title b" }))
    fireEvent.click(await screen.findByText("Unpin conversation"))
    expect(again.onPin).toHaveBeenCalledWith("b", false)
  })

  it("renames in the row: Enter saves, Escape leaves it, and a name left as it was is not sent", async () => {
    const spies = setup([row("a")])
    fireEvent.click(screen.getByRole("button", { name: "Actions for Title a" }))
    fireEvent.click(await screen.findByText("Rename"))
    const field = await screen.findByLabelText("Rename Title a")
    fireEvent.change(field, { target: { value: "  Movie night  " } })
    fireEvent.keyDown(field, { key: "Enter" })
    await waitFor(() => expect(spies.onRename).toHaveBeenCalledWith("a", "Movie night"))
    expect(screen.queryByLabelText("Rename Title a")).toBeNull()

    spies.onRename.mockClear()
    fireEvent.click(screen.getByRole("button", { name: "Actions for Title a" }))
    fireEvent.click(await screen.findByText("Rename"))
    const second = await screen.findByLabelText("Rename Title a")
    fireEvent.change(second, { target: { value: "Something else" } })
    fireEvent.keyDown(second, { key: "Escape" })
    expect(spies.onRename).not.toHaveBeenCalled()
    expect(screen.queryByLabelText("Rename Title a")).toBeNull() // Escape closed the field

    fireEvent.click(screen.getByRole("button", { name: "Actions for Title a" }))
    fireEvent.click(await screen.findByText("Rename"))
    fireEvent.keyDown(await screen.findByLabelText("Rename Title a"), { key: "Enter" }) // the name as it was
    expect(spies.onRename).not.toHaveBeenCalled()
    expect(screen.queryByLabelText("Rename Title a")).toBeNull()
  })

  it("asks to delete through the row's menu, and not for one that is replying", async () => {
    const spies = setup([row("a"), row("b", { replying: true })])
    fireEvent.click(screen.getByRole("button", { name: "Actions for Title a" }))
    fireEvent.click(await screen.findByText("Delete"))
    expect(spies.onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: "a" }))
    spies.onDelete.mockClear()
    fireEvent.click(screen.getByRole("button", { name: "Actions for Title b" }))
    const del = await screen.findAllByText("Delete")
    fireEvent.click(del[del.length - 1])
    expect(spies.onDelete).not.toHaveBeenCalled()
  })
})
