// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { EditorState } from "@codemirror/state"
import { EditorView } from "@codemirror/view"
import { history, undo } from "@codemirror/commands"

import { captureContext } from "./passage-finder"
import type { Annotation, Proposal } from "./persona-changes-api"
import {
  NO_REVIEW,
  acceptChanges,
  appliedState,
  applyProposals,
  clearApplied,
  attachedComments,
  classify,
  declineChanges,
  hasPending,
  pendingIds,
  reviewExtensions,
  selectionTarget,
  setReviewData,
  type ReviewData,
} from "./review-extensions"

// jsdom does no layout, so a range has no rectangles; CodeMirror asks for them to find where a position is on screen.
beforeAll(() => {
  const none = Object.assign([] as unknown as DOMRectList, { item: () => null })
  Range.prototype.getClientRects = () => none
  Range.prototype.getBoundingClientRect = () => new DOMRect(0, 0, 0, 0)
})

const NOTE = "I run three times a week. The beds are raised.\n\n- Pack charger\n- Phone\n\n- Pack charger\n"

function edit(id: string, find: string, replace: string, text = NOTE): Proposal {
  const at = text.indexOf(find)
  const [before, after] = captureContext(text, at, at + find.length)
  return { id, time: "t", kind: "edit", say: `say ${id}`, find, replace, before, after, status: "pending" }
}

function comment(id: string, quote: string, state: "open" | "resolved" = "open", text = NOTE): Annotation {
  const at = text.indexOf(quote)
  const [before, after] = captureContext(text, at, at + quote.length)
  return { id, time: "t", author: "user", quote, before, after, text: "why?", state, reply_to: null, status: "attached" }
}

const views: EditorView[] = []
function mount(
  data: ReviewData,
  {
    doc = NOTE,
    onResolve = vi.fn(),
    onOpenComment,
    onApplied,
  }: { doc?: string; onResolve?: (ids: string[]) => void; onOpenComment?: (id: string, rect: DOMRect) => void; onApplied?: (ids: string[], untouched: boolean) => void } = {}
) {
  const view = new EditorView({
    state: EditorState.create({ doc, extensions: [history(), reviewExtensions({ initial: () => data, onResolve, onOpenComment, onApplied })] }),
    parent: document.body,
  })
  views.push(view)
  return { view, onResolve }
}
afterEach(() => {
  views.splice(0).forEach((v) => v.destroy())
})

describe("classify", () => {
  it("places a proposal whose passage is there once and lists the others as outdated", () => {
    const here = edit("a", "three times", "four times")
    const gone = edit("b", "raised", "sunken")
    const edited = NOTE.replace("raised", "dug out")

    const { placed, outdated } = classify(edited, [here, gone])

    expect(placed.map((p) => [p.proposal.id, edited.slice(p.from, p.to)])).toEqual([["a", "three times"]])
    expect(outdated.map((p) => p.id)).toEqual(["b"])
  })

  it("follows the passage when text is typed before it", () => {
    const { placed } = classify("XX " + NOTE, [edit("a", "three times", "four times")])
    expect(placed[0].from).toBe(("XX " + NOTE).indexOf("three times"))
  })

  it("leaves a new-note proposal out: it has no passage", () => {
    const create: Proposal = { id: "c", time: "t", kind: "create", say: "", text: "# x", name: "x", status: "pending" }
    expect(classify(NOTE, [create])).toEqual({ placed: [], outdated: [] })
  })

  it("is outdated when the same words turn up twice and the surroundings cannot tell", () => {
    const p = edit("a", "beds", "plots")
    expect(classify(NOTE + NOTE, [p]).outdated).toHaveLength(1)
  })
})

describe("attachedComments", () => {
  it("lists only open comments whose passage is still there", () => {
    const edited = NOTE.replace("Phone", "Mobile")
    const found = attachedComments(edited, [comment("a", "raised"), comment("b", "Phone"), comment("c", "beds", "resolved")])
    expect(found.map((f) => f.annotation.id)).toEqual(["a"])
  })
})

describe("the drawn changes", () => {
  it("strikes the quoted passage and draws her replacement beside it, from the first paint", () => {
    const { view } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })

    expect(view.dom.querySelector(".sy-change-del")?.textContent).toBe("three times")
    expect(view.dom.querySelector(".sy-change-add")?.textContent).toBe("four times")
    expect(view.dom.querySelector('[data-change-id="a"]')?.getAttribute("title")).toBe("say a")
    expect(view.state.doc.toString()).toBe(NOTE)
  })

  it("draws nothing for an outdated proposal or for nothing", () => {
    const stale = edit("a", "three times", "four times")
    const { view } = mount({ proposals: [stale], annotations: [] }, { doc: NOTE.replace("three times", "five times") })
    expect(view.dom.querySelector(".sy-change-del")).toBeNull()
    expect(view.dom.querySelector(".sy-change")).toBeNull()
    expect(mount(NO_REVIEW).view.dom.querySelector(".sy-change")).toBeNull()
  })

  it("has an accept and a decline button on each change, named for a screen reader", () => {
    const { view } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })
    expect(view.dom.querySelector(".sy-change-accept")?.getAttribute("aria-label")).toBe("Accept this change")
    expect(view.dom.querySelector(".sy-change-decline")?.getAttribute("aria-label")).toBe("Decline this change")
    expect(view.dom.querySelectorAll(".sy-change-btn svg")).toHaveLength(2)
  })

  it("updates when new data arrives and when the user types", () => {
    const { view } = mount(NO_REVIEW)
    view.dispatch({ effects: setReviewData.of({ proposals: [edit("a", "raised", "sunken")], annotations: [] }) })
    expect(view.dom.querySelector(".sy-change-del")?.textContent).toBe("raised")

    view.dispatch({ changes: { from: 0, insert: "XX " } })
    expect(view.dom.querySelector(".sy-change-del")?.textContent).toBe("raised")

    view.dispatch({ changes: { from: view.state.doc.toString().indexOf("raised"), to: view.state.doc.toString().indexOf("raised") + 6, insert: "dug" } })
    expect(view.dom.querySelector(".sy-change-del")).toBeNull()
  })

  it("highlights an open comment's passage", () => {
    const { view } = mount({ proposals: [], annotations: [comment("a", "raised"), comment("b", "Phone", "resolved")] })
    expect([...view.dom.querySelectorAll(".sy-comment-hl")].map((e) => e.textContent)).toEqual(["raised"])
  })

  it("marks a commented line for a dot drawn in its own left space, not in a column that changes the editor's width", () => {
    const { view } = mount({ proposals: [], annotations: [comment("a", "raised")] })
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(1)
    expect(view.dom.querySelector(".cm-gutters")).toBeNull()
  })

  it("tells a comment of hers from one of the user's, on the passage and on its line", () => {
    const hers: Annotation = { ...comment("p", "Phone"), author: "persona" }
    const { view } = mount({ proposals: [], annotations: [comment("u", "raised"), hers] })

    expect(view.dom.querySelector('[data-comment-id="p"]')?.classList.contains("sy-by-persona")).toBe(true)
    expect(view.dom.querySelector('[data-comment-id="u"]')?.classList.contains("sy-by-persona")).toBe(false)
    const lines = [...view.dom.querySelectorAll(".sy-comment-line")]
    expect(lines.filter((l) => l.classList.contains("sy-by-persona"))).toHaveLength(1)
    expect(lines.filter((l) => l.classList.contains("sy-by-user"))).toHaveLength(1)
  })

  it("gives a line holding both hers and the user's both marks", () => {
    const hers: Annotation = { ...comment("p", "beds"), author: "persona" }
    const { view } = mount({ proposals: [], annotations: [comment("u", "raised"), hers] })

    const [line] = [...view.dom.querySelectorAll(".sy-comment-line")]
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(1)
    expect(line.classList.contains("sy-by-user") && line.classList.contains("sy-by-persona")).toBe(true)
  })

  it("marks every line a comment's passage runs over", () => {
    const doc = "one two\nthree four\nfive\n"
    const spanning: Annotation = { ...comment("a", "raised"), quote: "one two\nthree", before: "", after: "" }
    const { view } = mount({ proposals: [], annotations: [spanning] }, { doc })
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(2)
  })

  it("refreshes the margin when comments change", () => {
    const { view } = mount(NO_REVIEW)
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(0)
    view.dispatch({ effects: setReviewData.of({ proposals: [], annotations: [comment("a", "raised")] }) })
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(1)
  })
})

describe("drawing details", () => {
  it("puts her replacement right after the struck passage, not before it", () => {
    const { view } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })
    const struck = view.dom.querySelector(".sy-change-del") as Element
    const added = view.dom.querySelector(".sy-change") as Element
    expect(struck.compareDocumentPosition(added) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("redraws a change whose replacement changed, and keeps the drawing of one that did not", () => {
    const { view } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })
    const before = view.dom.querySelector(".sy-change")
    view.dispatch({ effects: setReviewData.of({ proposals: [edit("a", "three times", "four times")], annotations: [] }) })
    expect(view.dom.querySelector(".sy-change")).toBe(before)

    view.dispatch({ effects: setReviewData.of({ proposals: [edit("a", "three times", "five times")], annotations: [] }) })
    expect(view.dom.querySelector(".sy-change-add")?.textContent).toBe("five times")
  })

  it("does not take the caret when a button is pressed", () => {
    const { view } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })
    const down = new MouseEvent("mousedown", { bubbles: true, cancelable: true })
    view.dom.querySelector(".sy-change-accept")?.dispatchEvent(down)
    expect(down.defaultPrevented).toBe(true)
  })

  it("takes the margin dot away when typing removes the commented passage", () => {
    const { view } = mount({ proposals: [], annotations: [comment("a", "raised")] })
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(1)
    const at = view.state.doc.toString().indexOf("raised")
    view.dispatch({ changes: { from: at, to: at + 6, insert: "dug" } })
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(0)
  })
})

describe("accepting and declining", () => {
  it("applies the replacement to the text, as one undoable change, and tells the panel which", () => {
    const { view, onResolve } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })

    ;(view.dom.querySelector(".sy-change-accept") as HTMLButtonElement).click()

    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times"))
    expect(onResolve).toHaveBeenCalledWith(["a"])
    undo(view)
    expect(view.state.doc.toString()).toBe(NOTE)
  })

  it("declines without touching the text", () => {
    const { view, onResolve } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })

    ;(view.dom.querySelector(".sy-change-decline") as HTMLButtonElement).click()

    expect(view.state.doc.toString()).toBe(NOTE)
    expect(onResolve).toHaveBeenCalledWith(["a"])
  })

  it("applies several in one change, each where its own passage is, whatever order they were given in", () => {
    const { view, onResolve } = mount({
      proposals: [edit("b", "raised", "sunken"), edit("a", "three times", "four times")],
      annotations: [],
    })

    expect(acceptChanges(view, ["a", "b"]).sort()).toEqual(["a", "b"])

    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times").replace("raised", "sunken"))
    expect(onResolve).toHaveBeenCalledTimes(1)
    undo(view)
    expect(view.state.doc.toString()).toBe(NOTE)
  })

  it("accepts only the ones named and leaves an outdated one alone", () => {
    const stale = edit("s", "raised", "sunken")
    const { view, onResolve } = mount(
      { proposals: [edit("a", "three times", "four times"), stale], annotations: [] },
      { doc: NOTE.replace("raised", "dug") }
    )

    expect(acceptChanges(view, ["a", "s"])).toEqual(["a"])
    expect(view.state.doc.toString()).toBe(NOTE.replace("raised", "dug").replace("three times", "four times"))
    expect(onResolve).toHaveBeenCalledWith(["a"])
  })

  it("accepts only the one named and leaves another that could be placed alone", () => {
    const { view, onResolve } = mount({ proposals: [edit("a", "three times", "four times"), edit("b", "raised", "sunken")], annotations: [] })

    expect(acceptChanges(view, ["a"])).toEqual(["a"])

    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times"))
    expect(onResolve).toHaveBeenCalledWith(["a"])
    expect(pendingIds(view.state)).toEqual(["b"])
  })

  it("applies one of two proposals on the same passage and leaves the other waiting", () => {
    const { view, onResolve } = mount({
      proposals: [edit("a", "three times", "four times"), edit("b", "three times", "five times")],
      annotations: [],
    })

    expect(acceptChanges(view, ["a", "b"])).toEqual(["a"])

    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times"))
    expect(onResolve).toHaveBeenCalledWith(["a"])
  })

  it("applies the earlier of two proposals whose passages overlap", () => {
    const { view } = mount({
      proposals: [edit("a", "run three times", "walk"), edit("b", "three times a week", "daily")],
      annotations: [],
    })

    expect(acceptChanges(view, ["a", "b"])).toEqual(["a"])
    expect(view.state.doc.toString()).toBe(NOTE.replace("run three times", "walk"))
  })

  it("accepts nothing and says nothing when none can be placed", () => {
    const { view, onResolve } = mount(NO_REVIEW)
    expect(acceptChanges(view, ["x"])).toEqual([])
    expect(onResolve).not.toHaveBeenCalled()
  })

  it("declines by id without touching the text", () => {
    const { view, onResolve } = mount({ proposals: [edit("a", "three times", "four times")], annotations: [] })
    declineChanges(view, ["a", "b"])
    expect(onResolve).toHaveBeenCalledWith(["a", "b"])
    expect(view.state.doc.toString()).toBe(NOTE)
  })

  it("reports what is pending now, which changes with the text", () => {
    const { view } = mount({ proposals: [edit("a", "three times", "four times"), edit("b", "raised", "sunken")], annotations: [] })
    expect(pendingIds(view.state).sort()).toEqual(["a", "b"])
    expect(hasPending(view.state)).toBe(true)

    const at = view.state.doc.toString().indexOf("raised")
    view.dispatch({ changes: { from: at, to: at + 6, insert: "dug" } })
    expect(pendingIds(view.state)).toEqual(["a"])

    expect(hasPending(EditorState.create({ doc: "x" }))).toBe(false) // an editor without the extension has none
  })
})


describe("comments in the text", () => {
  it("highlights a comment once however many answers it has, and tags the highlight with its id", () => {
    const root = comment("c1", "raised")
    const answer: Annotation = { ...root, id: "c2", author: "persona", reply_to: "c1", text: "because" }
    const { view } = mount({ proposals: [], annotations: [root, answer] })

    const marks = [...view.dom.querySelectorAll(".sy-comment-hl")]
    expect(marks.map((m) => (m as HTMLElement).dataset.commentId)).toEqual(["c1"])
    expect(view.dom.querySelectorAll(".sy-comment-line")).toHaveLength(1)
    expect(attachedComments(NOTE, [root, answer]).map((f) => f.annotation.id)).toEqual(["c1"])
  })

  it("tells who clicked which comment, and where the passage is, and still lets the click through", () => {
    const onOpenComment = vi.fn()
    const { view } = mount({ proposals: [], annotations: [comment("c1", "raised")] }, { onOpenComment })
    const mark = view.dom.querySelector(".sy-comment-hl") as HTMLElement
    const click = new MouseEvent("click", { bubbles: true, cancelable: true })

    mark.dispatchEvent(click)

    expect(onOpenComment).toHaveBeenCalledTimes(1)
    expect(onOpenComment.mock.calls[0][0]).toBe("c1")
    expect(onOpenComment.mock.calls[0][1]).toHaveProperty("width")
    expect(click.defaultPrevented).toBe(false)
  })

  it("says nothing for a click elsewhere in the text, or when nobody is listening", () => {
    const onOpenComment = vi.fn()
    const { view } = mount({ proposals: [], annotations: [comment("c1", "raised")] }, { onOpenComment })
    ;(view.dom.querySelector(".cm-line") as HTMLElement).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    expect(onOpenComment).not.toHaveBeenCalled()

    const quiet = mount({ proposals: [], annotations: [comment("c1", "raised")] }).view
    expect(() => (quiet.dom.querySelector(".sy-comment-hl") as HTMLElement).dispatchEvent(new MouseEvent("click", { bubbles: true }))).not.toThrow()
  })
})

describe("selectionTarget", () => {
  it("is the selected words with the text around them", () => {
    const { view } = mount(NO_REVIEW)
    const at = NOTE.indexOf("raised")
    view.dispatch({ selection: { anchor: at, head: at + 6 } })

    const target = selectionTarget(view)

    expect(target?.quote).toBe("raised")
    expect(target?.before).toBe(NOTE.slice(0, at))
    expect(target?.after).toBe(NOTE.slice(at + 6, at + 6 + 40))
    expect(target?.rect).toBeTruthy()
  })

  it("is nothing when nothing is selected", () => {
    expect(selectionTarget(mount(NO_REVIEW).view)).toBeNull()
  })
})

describe("applying her edits in accept mode (docs/decisions/072)", () => {
  const data = (...proposals: Proposal[]): ReviewData => ({ proposals, annotations: [] })
  const type = (view: EditorView, at: number, insert: string, to = at) => view.dispatch({ changes: { from: at, to, insert }, userEvent: "input.type" })

  it("puts her replacement in the text, marks it, and does not tell the server anything", () => {
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")))

    expect(applyProposals(view, ["a"])).toEqual(["a"])

    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times"))
    expect(view.dom.querySelector(".sy-applied")?.textContent).toBe("four times")
    expect(view.dom.querySelector(".sy-applied-undo")).not.toBeNull()
    expect(onResolve).not.toHaveBeenCalled()
  })

  it("applies several at once and refuses the second of two on one passage", () => {
    const { view } = mount(data(edit("a", "three times", "four times"), edit("b", "raised", "sunken"), edit("c", "three", "two")))

    expect(applyProposals(view, ["a", "b", "c"])).toEqual(["a", "b"])

    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times").replace("raised", "sunken"))
    expect([...view.dom.querySelectorAll(".sy-applied")].map((e) => e.textContent)).toEqual(["four times", "sunken"])
  })

  it("reports what is applied, and that the user has not touched the note", () => {
    const onApplied = vi.fn()
    const { view } = mount(data(edit("a", "three times", "four times")), { onApplied })

    applyProposals(view, ["a"])

    expect(onApplied).toHaveBeenLastCalledWith(["a"], true)
    expect(appliedState(view.state)).toEqual({ ids: ["a"], untouched: true })
  })

  it("is touched once the user types anywhere", () => {
    const onApplied = vi.fn()
    const { view } = mount(data(edit("a", "three times", "four times")), { onApplied })
    applyProposals(view, ["a"])

    type(view, 0, "X")

    expect(appliedState(view.state)).toEqual({ ids: ["a"], untouched: false })
    expect(onApplied).toHaveBeenLastCalledWith(["a"], false)
  })

  it("follows the new words when text is typed before them", () => {
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")))
    applyProposals(view, ["a"])

    type(view, 0, "XX ")

    expect(view.dom.querySelector(".sy-applied")?.textContent).toBe("four times")
    expect(onResolve).not.toHaveBeenCalled()
  })

  it("keeps it when text is typed at either edge of the new words", () => {
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")))
    applyProposals(view, ["a"])
    const at = view.state.doc.toString().indexOf("four times")

    type(view, at + "four times".length, "!")
    type(view, at, ">")

    expect(appliedState(view.state).ids).toEqual(["a"])
    expect(onResolve).not.toHaveBeenCalled()
  })

  it("drops it and forgets the proposal when the user types inside the new words", () => {
    const onApplied = vi.fn()
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")), { onApplied })
    applyProposals(view, ["a"])
    const at = view.state.doc.toString().indexOf("four times")

    type(view, at + 2, "Z")

    expect(onResolve).toHaveBeenCalledWith(["a"])
    expect(appliedState(view.state).ids).toEqual([])
    expect(onApplied).toHaveBeenLastCalledWith([], true)
    expect(view.dom.querySelector(".sy-applied")).toBeNull()
  })

  it("drops it and forgets the proposal when the editor's undo takes the words back out", () => {
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")))
    applyProposals(view, ["a"])

    undo(view)

    expect(view.state.doc.toString()).toBe(NOTE)
    expect(onResolve).toHaveBeenCalledWith(["a"])
    expect(appliedState(view.state).ids).toEqual([])
  })

  it("the Undo on the mark puts her original words back and forgets the proposal", () => {
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")))
    applyProposals(view, ["a"])

    view.dom.querySelector<HTMLButtonElement>(".sy-applied-undo")!.click()

    expect(view.state.doc.toString()).toBe(NOTE)
    expect(onResolve).toHaveBeenCalledWith(["a"])
    expect(view.dom.querySelector(".sy-applied")).toBeNull()
  })

  it("clearApplied ends the marks and returns the ids, without telling the server (the save does that)", () => {
    const onApplied = vi.fn()
    const { view, onResolve } = mount(data(edit("a", "three times", "four times")), { onApplied })
    applyProposals(view, ["a"])

    expect(clearApplied(view)).toEqual(["a"])

    expect(appliedState(view.state).ids).toEqual([])
    expect(view.dom.querySelector(".sy-applied")).toBeNull()
    expect(view.state.doc.toString()).toBe(NOTE.replace("three times", "four times"))
    expect(onResolve).not.toHaveBeenCalled()
    expect(onApplied).toHaveBeenLastCalledWith([], true)
  })

  it("an edit that deletes words keeps its Undo, which puts them back; typing at the gap drops it", () => {
    const { view, onResolve } = mount(data(edit("a", " The beds are raised.", "")))
    applyProposals(view, ["a"])
    expect(view.state.doc.toString()).toBe(NOTE.replace(" The beds are raised.", ""))
    expect(view.dom.querySelector(".sy-applied-undo")).not.toBeNull()

    view.dom.querySelector<HTMLButtonElement>(".sy-applied-undo")!.click()

    expect(view.state.doc.toString()).toBe(NOTE)
    expect(onResolve).toHaveBeenCalledWith(["a"])

    const second = mount(data(edit("b", " The beds are raised.", "")))
    applyProposals(second.view, ["b"])
    type(second.view, second.view.state.doc.toString().indexOf("week.") + 5, "!")
    expect(second.onResolve).toHaveBeenCalledWith(["b"])
  })

  it("tells the panel once when the editor has been made, after the update, so it may then dispatch", async () => {
    const onReady = vi.fn()
    const view = new EditorView({
      state: EditorState.create({ doc: NOTE, extensions: [reviewExtensions({ initial: () => NO_REVIEW, onResolve: vi.fn(), onReady })] }),
      parent: document.body,
    })
    views.push(view)
    expect(onReady).not.toHaveBeenCalled()

    await Promise.resolve()

    expect(onReady).toHaveBeenCalledTimes(1)
    expect(onReady).toHaveBeenCalledWith(view)
  })

  it("applying nothing changes nothing", () => {
    const { view } = mount(data(edit("a", "three times", "four times")))
    expect(applyProposals(view, ["nope"])).toEqual([])
    expect(view.state.doc.toString()).toBe(NOTE)
  })
})
