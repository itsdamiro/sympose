// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { ChatTurn } from "@/lib/chat-types"
import { ChatPanel } from "./chat-panel"

afterEach(cleanup)

function setup(props: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const onSubmit = vi.fn()
  const view = render(<ChatPanel turns={[]} draft="hello" onDraftChange={() => {}} onSubmit={onSubmit} {...props} />)
  return { onSubmit, rerender: view.rerender }
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

  it("still sends while a reply is in flight: the message waits and goes out with the others", () => {
    const { onSubmit } = setup({ sending: true })
    enter()
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it("shows a Stop button only while a reply is in flight, and it stops that reply", () => {
    const onStop = vi.fn()
    const view = render(<ChatPanel turns={[]} draft="" onDraftChange={() => {}} onSubmit={() => {}} onStop={onStop} />)
    expect(screen.queryByLabelText("Stop the reply")).toBeNull()
    view.rerender(<ChatPanel turns={[]} draft="" onDraftChange={() => {}} onSubmit={() => {}} onStop={onStop} sending />)
    fireEvent.click(screen.getByLabelText("Stop the reply"))
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it("has no Stop button when nothing can stop the reply", () => {
    setup({ sending: true })
    expect(screen.queryByLabelText("Stop the reply")).toBeNull()
  })

  it("says what the reply in flight is doing, in the terminal's own words", () => {
    setup({ sending: true, phase: "searching" })
    expect(screen.getByText("Searching your notes…")).toBeTruthy()
  })

  it("says it is thinking when the backend has not named a phase yet", () => {
    setup({ sending: true, phase: null })
    expect(screen.getByText("Thinking about your message…")).toBeTruthy()
  })

  describe("the busy line's phrases and typing", () => {
    beforeEach(() => {
      vi.useFakeTimers()
      vi.stubGlobal("matchMedia", () => ({ matches: false }))
    })
    afterEach(() => {
      vi.useRealTimers()
      vi.unstubAllGlobals()
    })
    const line = () => (document.querySelector('[data-slot="busy-line"] [aria-hidden]') as HTMLElement).textContent ?? ""

    it("types the line out by letters unless typing is off", () => {
      setup({ sending: true, phase: "reading", typeStatus: true })
      expect(line().slice(2)).toBe("R")
      cleanup()
      setup({ sending: true, phase: "reading", typeStatus: false })
      expect(line().slice(2)).toBe("Reading a note…")
    })

    it("rotates through the persona's own phrases it is given", () => {
      setup({ sending: true, phase: "reading", typeStatus: false, statusPhrases: ["Own phrase…"] })
      act(() => void vi.advanceTimersByTime(3100))
      expect(line().slice(2)).toBe("Own phrase…")
    })
  })

  it("says searches use keywords while the index is being built, and only while a reply is in flight", () => {
    setup({ sending: true, phase: "searching", indexing: 40 })
    expect(screen.getByText("Still indexing your notes (40%). Until it is done, searches use keywords.")).toBeTruthy()
    cleanup()
    setup({ sending: true, phase: "searching", indexing: null })
    expect(screen.queryByText(/Still indexing/)).toBeNull()
    cleanup()
    setup({ sending: false, indexing: 40 })
    expect(screen.queryByText(/Still indexing/)).toBeNull()
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

  describe("the message box grows with what is typed", () => {
    const LINE_PX = 20
    beforeEach(() => {
      // jsdom does no layout: stand in for it, a line of text being LINE_PX tall.
      Object.defineProperty(HTMLTextAreaElement.prototype, "scrollHeight", {
        configurable: true,
        get(this: HTMLTextAreaElement) {
          // A closed panel has no width, so its box reads as very tall (the placeholder wraps letter by letter).
          if (this.closest('[data-state="closed"]')) return 500
          return Math.max(1, this.value.split("\n").length) * LINE_PX
        },
      })
    })
    afterEach(() => {
      delete (HTMLTextAreaElement.prototype as unknown as Record<string, unknown>).scrollHeight
    })
    const box = () => screen.getByLabelText("Message") as HTMLTextAreaElement

    it("is as tall as its text, line after line", () => {
      const { rerender } = setup({ draft: "one" })
      expect(box().style.height).toBe("20px")
      rerender(<ChatPanel turns={[]} draft={"one\ntwo\nthree"} onDraftChange={vi.fn()} onSubmit={vi.fn()} />)
      expect(box().style.height).toBe("60px")
      expect(box().style.overflowY).toBe("hidden")
    })

    it("stops growing at about eight lines and scrolls inside from there", () => {
      setup({ draft: Array.from({ length: 30 }, (_, i) => `line ${i}`).join("\n") })
      expect(box().style.height).toBe("192px")
      expect(box().style.overflowY).toBe("auto")
    })

    it("is measured again when the panel opens, not left at the height it had while closed", () => {
      const { rerender } = setup({ draft: "", open: false })
      expect(box().style.height).toBe("192px") // measured while closed: wrong, and must not stick
      rerender(<ChatPanel turns={[]} draft="" open onDraftChange={vi.fn()} onSubmit={vi.fn()} />)
      expect(box().style.height).toBe("20px")
    })

    it("watches the box's width, measures again only when it changed, and stops watching when closed", () => {
      const seen = { observed: [] as Element[], disconnected: 0 }
      let notify: () => void = () => {}
      vi.stubGlobal(
        "ResizeObserver",
        class {
          constructor(cb: () => void) {
            notify = cb
          }
          observe(el: Element) {
            seen.observed.push(el)
          }
          disconnect() {
            seen.disconnected += 1
          }
        }
      )
      let width = 300
      Object.defineProperty(HTMLTextAreaElement.prototype, "clientWidth", { configurable: true, get: () => width })
      try {
        const view = render(<ChatPanel turns={[]} draft="x" onDraftChange={vi.fn()} onSubmit={vi.fn()} />)
        expect(seen.observed).toEqual([box()])
        expect(box().style.height).toBe("20px")
        box().value = "a\nb\nc" // stands in for the text wrapping onto more lines at a narrower width
        notify()
        expect(box().style.height).toBe("20px") // the width has not changed: nothing to measure again
        width = 200
        notify()
        expect(box().style.height).toBe("60px")
        box().value = "a\nb\nc\nd\ne"
        notify()
        expect(box().style.height).toBe("60px") // that width was measured already
        view.unmount()
        expect(seen.disconnected).toBe(1)
      } finally {
        vi.unstubAllGlobals()
        delete (HTMLTextAreaElement.prototype as unknown as Record<string, unknown>).clientWidth
      }
    })

    it("goes back to one line once the message is sent and the box is cleared", () => {
      const { rerender } = setup({ draft: "a\nb\nc\nd" })
      expect(box().style.height).toBe("80px")
      rerender(<ChatPanel turns={[]} draft="" onDraftChange={vi.fn()} onSubmit={vi.fn()} />)
      expect(box().style.height).toBe("20px")
    })
  })

  it("shows the context meter in the footer when it has a figure, and nothing when it has none", () => {
    const { rerender } = setup({ contextFigure: { used: 620, limit: 1000, estimated: false } })
    expect(screen.getByRole("meter").textContent).toBe("62%")
    rerender(<ChatPanel turns={[]} draft="" onDraftChange={vi.fn()} onSubmit={vi.fn()} contextFigure={null} />)
    expect(screen.queryByRole("meter")).toBeNull()
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
