// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ChatTurn } from "@/lib/chat-types"
import { ChatPanel } from "./chat-panel"

afterEach(cleanup)

function setup(props: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const onSubmit = vi.fn()
  render(<ChatPanel turns={[]} draft="hello" onDraftChange={() => {}} onSubmit={onSubmit} {...props} />)
  return { onSubmit }
}

function withScroller(props: Partial<Parameters<typeof ChatPanel>[0]>) {
  const view = render(<ChatPanel turns={[]} draft="" onDraftChange={() => {}} onSubmit={() => {}} {...props} />)
  return { scroller: () => view.container.querySelector<HTMLElement>(".overflow-y-auto")! }
}

const enter = () => fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" })

describe("ChatPanel", () => {
  it("sends the draft on Enter", () => {
    const { onSubmit } = setup()
    enter()
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it("does not send while a reply is in flight", () => {
    const { onSubmit } = setup({ sending: true })
    enter()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("says what the reply in flight is doing, in the terminal's own words", () => {
    setup({ sending: true, phase: "searching" })
    expect(screen.getByText("Searching your notes…")).toBeTruthy()
  })

  it("says it is thinking when the backend has not named a phase yet", () => {
    setup({ sending: true, phase: null })
    expect(screen.getByText("Thinking about your message…")).toBeTruthy()
  })

  it("shows no status line when nothing is in flight", () => {
    setup()
    expect(screen.queryByText(/Searching|Reading|Thinking/)).toBeNull()
  })

  it("draws a system turn as a system line between the conversation", () => {
    const turns: ChatTurn[] = [
      { id: "1", role: "user", body: "hi" },
      { id: "2", role: "system", kind: "error", body: "@samantha couldn't reply: offline" },
    ]
    setup({ turns })
    expect(screen.getByRole("alert").textContent).toBe("@samantha couldn't reply: offline")
  })

  it("loads older turns when the user scrolls to the top and there are some", () => {
    const onLoadOlder = vi.fn()
    const { scroller } = withScroller({ hasMore: true, onLoadOlder })
    scroller().scrollTop = 10
    fireEvent.scroll(scroller())
    expect(onLoadOlder).toHaveBeenCalledTimes(1)
  })

  it("does not ask for older turns from the middle of the conversation, when none exist, or while loading", () => {
    const onLoadOlder = vi.fn()
    const first = withScroller({ hasMore: true, onLoadOlder })
    first.scroller().scrollTop = 500
    fireEvent.scroll(first.scroller())
    cleanup()
    const none = withScroller({ hasMore: false, onLoadOlder })
    none.scroller().scrollTop = 0
    fireEvent.scroll(none.scroller())
    cleanup()
    const busy = withScroller({ hasMore: true, loadingOlder: true, onLoadOlder })
    busy.scroller().scrollTop = 0
    fireEvent.scroll(busy.scroller())
    expect(onLoadOlder).not.toHaveBeenCalled()
  })

  it("says it is loading earlier messages", () => {
    setup({ loadingOlder: true, hasMore: true })
    expect(screen.getByText("Loading earlier messages…")).toBeTruthy()
  })

  it("keeps the reader's place when older turns are added above", () => {
    const turns = [
      { id: "b", role: "user", body: "recent" },
      { id: "c", role: "persona", body: "reply" },
    ] as ChatTurn[]
    const props = { draft: "", onDraftChange: () => {}, onSubmit: () => {}, hasMore: true, onLoadOlder: vi.fn() }
    const view = render(<ChatPanel turns={turns} {...props} />)
    const box = view.container.querySelector<HTMLElement>(".overflow-y-auto")!
    let height = 600
    Object.defineProperty(box, "scrollHeight", { configurable: true, get: () => height })
    box.scrollTop = 0
    fireEvent.scroll(box) // near the top with older turns waiting: asks for them, noting the height
    expect(props.onLoadOlder).toHaveBeenCalledTimes(1)
    height = 1000 // 400px of older turns arrive above
    view.rerender(<ChatPanel turns={[{ id: "a", role: "user", body: "older" } as ChatTurn, ...turns]} {...props} />)
    expect(box.scrollTop).toBe(400)
  })

  it("goes to the newest turn, not to the old place, when a new turn is added", () => {
    const turns = [{ id: "b", role: "user", body: "recent" }] as ChatTurn[]
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const props = { draft: "", onDraftChange: () => {}, onSubmit: () => {} }
    const view = render(<ChatPanel turns={turns} {...props} />)
    scrollIntoView.mockClear()
    view.rerender(<ChatPanel turns={[...turns, { id: "c", role: "persona", body: "reply" } as ChatTurn]} {...props} />)
    expect(scrollIntoView).toHaveBeenCalled()
  })

  it("offers a new conversation once there is one to leave, and not while a reply is in flight", () => {
    const onNewConversation = vi.fn()
    const turns: ChatTurn[] = [{ id: "1", role: "user", body: "hi" }]
    setup({ turns, onNewConversation })
    fireEvent.click(screen.getByText("New conversation"))
    expect(onNewConversation).toHaveBeenCalledTimes(1)
    cleanup()
    setup({ turns, onNewConversation, sending: true })
    expect(screen.queryByText("New conversation")).toBeNull()
    cleanup()
    setup({ turns: [], onNewConversation })
    expect(screen.queryByText("New conversation")).toBeNull()
  })

  it("shows what a persona reply was based on under that reply, and opens the note it names", () => {
    const onOpenNote = vi.fn()
    const turns: ChatTurn[] = [
      { id: "1", role: "user", body: "which database?" },
      {
        id: "2",
        role: "persona",
        handle: "samantha",
        body: "SQLite.",
        sent: { notes: [{ path: "Projects/Atlas.md", heading: "", source: "vault" }] },
      },
    ]
    setup({ turns, onOpenNote })
    fireEvent.click(screen.getByRole("button", { name: /Based on Atlas/ }))
    fireEvent.click(screen.getByRole("button", { name: "Projects/Atlas.md" }))
    expect(onOpenNote).toHaveBeenCalledWith("Projects/Atlas.md")
  })

  it("leaves the line out when the user turned it off", async () => {
    const turns: ChatTurn[] = [
      { id: "2", role: "persona", handle: "samantha", body: "SQLite.", sent: { notes: [{ path: "Projects/Atlas.md", heading: "", source: "vault" }] } },
    ]
    setup({ turns, showGrounding: false })
    expect(await screen.findByText("SQLite.")).toBeTruthy()
    expect(screen.queryByText(/Based on/)).toBeNull()
  })

  it("shows what a cloud reply was sent and held back, even with the grounded-notes line off", async () => {
    const turns: ChatTurn[] = [
      { id: "2", role: "persona", handle: "samantha", body: "SQLite.", sent: { notes: [], cloud: ["notes"], withheld: ["recaps"] } },
    ]
    setup({ turns, showGrounding: false })
    expect(await screen.findByText("Sent: notes · Held back: recaps")).toBeTruthy()
  })

  it("shows the model picker in place of the plain chip when there is one", () => {
    setup({ model: "ollama_chat/gemma2:9b", modelSlot: <button>pick a model</button> })
    expect(screen.getByRole("button", { name: "pick a model" })).toBeTruthy()
    expect(screen.queryByText("ollama_chat/gemma2:9b")).toBeNull()
  })

  it("shows the plain chip when there is no picker", () => {
    setup({ model: "ollama_chat/gemma2:9b" })
    expect(screen.getByText("ollama_chat/gemma2:9b")).toBeTruthy()
  })

  it("keeps the notice above the message box", () => {
    setup({ notice: <p>cloud notice here</p> })
    const notice = screen.getByText("cloud notice here")
    const box = screen.getByLabelText("Message")
    expect(notice.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("puts no grounding line under a reply that used no note, nor under the user's own message", () => {
    const turns: ChatTurn[] = [
      { id: "1", role: "user", body: "hello", sent: { notes: [{ path: "A.md", heading: "", source: "vault" }] } },
      { id: "2", role: "persona", handle: "samantha", body: "hi", sent: { notes: [] } },
    ]
    setup({ turns })
    expect(screen.queryByText(/Based on/)).toBeNull()
  })
})
