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
  it("draws what renderAfter gives under a persona's reply and under no other turn", () => {
    const turns: ChatTurn[] = [
      { id: "u1", role: "user", body: "make me a tutor" },
      { id: "p1", role: "persona", handle: "samantha", body: "Here she is." },
    ]
    setup({ turns, renderAfter: (turn) => <p key={turn.id}>after {turn.id}</p> })
    expect(screen.getAllByText(/^after /).map((n) => n.textContent)).toEqual(["after p1"])
  })

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

  describe("the controls under the message box", () => {
    const hi: ChatTurn[] = [{ id: "1", role: "user", body: "hi" }]
    const exchanges = (n: number): ChatTurn[] =>
      Array.from({ length: n }, (_, i): ChatTurn[] => [
        { id: `u${i}`, role: "user", body: "q" },
        { id: `p${i}`, role: "persona", handle: "samantha", body: "a" },
      ]).flat()
    const full = { used: 800, limit: 1000, estimated: false } // 80%: the meter is amber
    const roomy = { used: 300, limit: 1000, estimated: false }

    it("has no attachment button: the plus is gone", () => {
      setup()
      expect(screen.queryByRole("button", { name: "Add attachment" })).toBeNull()
    })

    it("starts with a new-conversation icon, which has nothing to leave until there is a conversation", () => {
      const onNewConversation = vi.fn()
      setup({ turns: [], onNewConversation })
      expect(screen.getByRole("button", { name: "New conversation" })).toHaveProperty("disabled", true)
      cleanup()
      setup({ turns: hi, onNewConversation })
      fireEvent.click(screen.getByRole("button", { name: "New conversation" }))
      expect(onNewConversation).toHaveBeenCalledTimes(1)
      cleanup()
      setup({ turns: hi, onNewConversation, sending: true }) // the reply finishes into the conversation it was sent from (ADR 057)
      expect(screen.getByRole("button", { name: "New conversation" })).toHaveProperty("disabled", false)
    })

    it("puts a pin toggle beside it once the conversation can be pinned", () => {
      const onTogglePin = vi.fn()
      setup({ turns: hi })
      expect(screen.queryByRole("button", { name: "Pin conversation" })).toBeNull()
      cleanup()
      setup({ turns: hi, onTogglePin, pinned: false })
      const pin = screen.getByRole("button", { name: "Pin conversation" })
      expect(pin.getAttribute("aria-pressed")).toBe("false")
      fireEvent.click(pin)
      expect(onTogglePin).toHaveBeenCalledTimes(1)
      cleanup()
      setup({ turns: [], onTogglePin }) // a blank conversation has not started: nothing to pin
      expect(screen.queryByRole("button", { name: "Pin conversation" })).toBeNull()
      cleanup()
      setup({ turns: hi, onTogglePin, pinned: true })
      expect(screen.getByRole("button", { name: "Unpin conversation" }).getAttribute("aria-pressed")).toBe("true")
    })

    it("offers Condense only when it is advisable: the meter is amber and there is something to fold", () => {
      const onCompact = vi.fn()
      setup({ turns: exchanges(6), onCompact, contextFigure: full })
      fireEvent.click(screen.getByRole("button", { name: "Condense" }))
      expect(onCompact).toHaveBeenCalledTimes(1)
      for (const [label, props] of [
        ["a roomy conversation", { turns: exchanges(6), contextFigure: roomy }],
        ["no figure yet", { turns: exchanges(6), contextFigure: null }],
        ["nothing to fold", { turns: exchanges(3), contextFigure: full }],
        ["notes that already cover it", { turns: exchanges(6), contextFigure: full, condensed: 4 }],
        ["a reply in flight", { turns: exchanges(6), contextFigure: full, sending: true }],
        ["no way to condense", { turns: exchanges(6), contextFigure: full, onCompact: undefined }],
      ] as const) {
        cleanup()
        setup({ onCompact, ...props })
        expect(screen.queryByRole("button", { name: "Condense" }), label).toBeNull()
      }
    })

    it("says what it is condensing, and cannot be pressed again, while the notes are written, even if the meter has dropped", () => {
      const onCompact = vi.fn()
      setup({ turns: exchanges(6), onCompact, contextFigure: roomy, compacting: true })
      const button = screen.getByRole("button", { name: "Condensing…" })
      expect(button).toHaveProperty("disabled", true)
      fireEvent.click(button)
      expect(onCompact).not.toHaveBeenCalled()
    })

    it("lists them in one group at the left: new conversation, pin, condense", () => {
      setup({ turns: exchanges(6), onCompact: vi.fn(), onNewConversation: vi.fn(), onTogglePin: vi.fn(), pinned: false, contextFigure: full })
      const group = screen.getByRole("group", { name: "Conversation controls" })
      expect(Array.from(group.querySelectorAll("button")).map((b) => b.getAttribute("aria-label") ?? b.textContent)).toEqual([
        "New conversation",
        "Pin conversation",
        "Condense",
      ])
    })
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

  it("keeps the model chip in the reply's header and puts the cloud mark and hover on it, even with the references line off", async () => {
    const turns: ChatTurn[] = [
      {
        id: "2", role: "persona", handle: "samantha", body: "SQLite.", model: "gemini/gemini-flash-latest",
        sent: { notes: [{ path: "Projects/Atlas.md", heading: "", source: "vault" }], cloud: ["notes"], withheld: ["recaps"] },
      },
    ]
    setup({ turns, showGrounding: false })
    const chip = await screen.findByRole("button", { name: /what was sent to the cloud model/ })
    expect(chip.textContent).toContain("gemini/gemini-flash-latest")
    expect(chip.getAttribute("data-held")).toBe("true")
    const message = chip.closest('[data-slot="chat-message"]') as HTMLElement
    expect(message.querySelector('[data-slot="reply-footer"]')?.contains(chip) ?? false).toBe(false) // not in the footer row
    expect(chip.parentElement?.className).toContain("items-center") // the header row: avatar, this, the time
  })

  it("names the model that made each reply, not the one chosen now, and a local reply's chip has no hover", async () => {
    const turns: ChatTurn[] = [{ id: "2", role: "persona", handle: "samantha", body: "SQLite.", model: "ollama_chat/gemma2:9b" }]
    const { container } = render(<ChatPanel turns={turns} draft="" onDraftChange={() => {}} onSubmit={() => {}} model="gemini/gemini-flash-latest" />)
    await screen.findByText("SQLite.")
    const chip = container.querySelector('[data-slot="chat-message"] [data-slot="model-chip"]')
    expect(chip?.textContent).toBe("ollama_chat/gemma2:9b")
    expect(chip?.closest("button")).toBeNull()
  })

  it("leaves the cloud mark off the chip when the user turned it off", async () => {
    const turns: ChatTurn[] = [
      { id: "2", role: "persona", handle: "samantha", body: "SQLite.", sent: { notes: [], cloud: ["notes"], withheld: [] } },
    ]
    setup({ turns, showCloudSent: false })
    expect(await screen.findByText("SQLite.")).toBeTruthy()
    expect(screen.queryByRole("button", { name: /what was sent to the cloud model/ })).toBeNull()
  })

  it("shows a reply built from her own lookups or earlier exchanges, not only from notes", async () => {
    const turns: ChatTurn[] = [
      { id: "2", role: "persona", handle: "samantha", body: "As you said.", sent: { notes: [], chats: [{ session: "s1", turn: 2, how: "auto" }] } },
    ]
    setup({ turns })
    expect(await screen.findByText(/Based on 1 earlier message/)).toBeTruthy()
  })

  it("greets an empty conversation with the persona's icon, her name and her title, as the Bin's empty list does", () => {
    const { container } = render(<ChatPanel turns={[]} draft="" onDraftChange={() => {}} onSubmit={() => {}} personaName="Ada" personaTitle="Proofreader" />)
    expect(screen.getByText("Ask Ada anything")).toBeTruthy()
    expect(screen.getByText("Proofreader")).toBeTruthy() // her own title, not a line about the vault
    expect(container.querySelector('[data-slot="empty-icon"] svg')).not.toBeNull()
  })

  it("shows how long a reply took to start, before its time, and nothing when that is not known", async () => {
    const turns: ChatTurn[] = [
      { id: "2", role: "persona", handle: "samantha", body: "SQLite.", latency: "0.82s", timestamp: "10:42" },
      { id: "3", role: "persona", handle: "samantha", body: "Postgres.", timestamp: "10:43" },
    ]
    setup({ turns })
    const ttft = await screen.findByText("TTFT 0.82s")
    const time = screen.getByText("10:42")
    expect(ttft.compareDocumentPosition(time) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy() // the latency comes first
    expect(screen.getAllByText(/TTFT/)).toHaveLength(1)
    expect(ttft.nextElementSibling?.textContent).toBe("·") // a centre dot between the two, only where both are shown
    expect(screen.getByText("10:43").previousElementSibling?.textContent).not.toBe("·")
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
