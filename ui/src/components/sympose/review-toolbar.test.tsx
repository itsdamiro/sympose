// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { EditorState } from "@codemirror/state"
import { EditorView } from "@codemirror/view"

import { captureContext } from "@/lib/passage-finder"
import type { Proposal } from "@/lib/persona-changes-api"
import { reviewExtensions } from "@/lib/review-extensions"

import { commentMenuItem, commentToolbarItem, reviewToolbarItems } from "./review-toolbar"

// jsdom does no layout, so a range has no rectangles; CodeMirror asks for them to find where a position is on screen.
beforeAll(() => {
  const none = Object.assign([] as unknown as DOMRectList, { item: () => null })
  Range.prototype.getClientRects = () => none
  Range.prototype.getBoundingClientRect = () => new DOMRect(0, 0, 0, 0)
})

const NOTE = "I run three times a week. The beds are raised.\n"
const edit = (id: string, find: string, replace: string): Proposal => {
  const at = NOTE.indexOf(find)
  const [before, after] = captureContext(NOTE, at, at + find.length)
  return { id, time: "t", kind: "edit", say: "", find, replace, before, after, status: "pending" }
}
const views: EditorView[] = []
const mount = (proposals: Proposal[], doc = NOTE) => {
  const view = new EditorView({
    state: EditorState.create({ doc, extensions: [reviewExtensions({ initial: () => ({ proposals, annotations: [] }), onResolve: () => {} })] }),
    parent: document.body,
  })
  views.push(view)
  return view
}
afterEach(() => views.splice(0).forEach((v) => v.destroy()))

describe("reviewToolbarItems", () => {
  it("has an accept and a decline button with their own ids and titles", () => {
    const [accept, decline] = reviewToolbarItems({ onAcceptNote: () => {}, onDeclineNote: () => {} })
    expect([accept.id, decline.id]).toEqual(["review-accept", "review-decline"])
    expect(accept.title).toMatch(/accept all/i)
    expect(decline.title).toMatch(/decline all/i)
  })

  it("accepts every change in the text at once and asks for the save", () => {
    const onAcceptNote = vi.fn()
    const view = mount([edit("a", "three times", "four times"), edit("b", "raised", "sunken")])
    const [accept] = reviewToolbarItems({ onAcceptNote, onDeclineNote: () => {} })

    accept.run(view)

    expect(view.state.doc.toString()).toBe("I run four times a week. The beds are sunken.\n")
    expect(onAcceptNote).toHaveBeenCalledTimes(1)
  })

  it("does not ask for a save when nothing could be accepted", () => {
    const onAcceptNote = vi.fn()
    const view = mount([edit("a", "three times", "four times")], NOTE.replace("three times", "five times"))
    const [accept] = reviewToolbarItems({ onAcceptNote, onDeclineNote: () => {} })

    accept.run(view)

    expect(onAcceptNote).not.toHaveBeenCalled()
  })

  it("is disabled when nothing in the text can be accepted, and enabled when something can", () => {
    const [accept] = reviewToolbarItems({ onAcceptNote: () => {}, onDeclineNote: () => {} })
    expect(accept.disabled?.(mount([]).state)).toBe(true)
    expect(accept.disabled?.(mount([edit("a", "three times", "four times")]).state)).toBe(false)
    expect(accept.disabled?.(mount([edit("a", "three times", "four times")], NOTE.replace("three times", "five times")).state)).toBe(true)
  })

  it("declines the lot through its callback and is disabled only when the note has no suggestions", () => {
    const onDeclineNote = vi.fn()
    const [, decline] = reviewToolbarItems({ onAcceptNote: () => {}, onDeclineNote })

    decline.run(mount([]))
    expect(onDeclineNote).toHaveBeenCalledTimes(1)
    expect(decline.disabled?.(mount([]).state)).toBe(true)
    // An outdated suggestion can still be declined, though it cannot be accepted.
    expect(decline.disabled?.(mount([edit("a", "three times", "four times")], NOTE.replace("three times", "five times")).state)).toBe(false)
  })
})

describe("commentToolbarItem", () => {
  it("is named for what it does and greyed while nothing is selected", () => {
    const item = commentToolbarItem(() => {})
    const view = mount([])

    expect(item.id).toBe("review-comment")
    expect(item.title).toMatch(/comment/i)
    expect(item.disabled?.(view.state)).toBe(true)
    view.dispatch({ selection: { anchor: 2, head: 5 } })
    expect(item.disabled?.(view.state)).toBe(false)
  })

  it("hands the selection over to be commented on, and does nothing without one", () => {
    const onCompose = vi.fn()
    const item = commentToolbarItem(onCompose)
    const view = mount([])

    item.run(view)
    expect(onCompose).not.toHaveBeenCalled()

    view.dispatch({ selection: { anchor: 2, head: 5 } })
    item.run(view)
    expect(onCompose).toHaveBeenCalledTimes(1)
    expect(onCompose.mock.calls[0][0].quote).toBe(NOTE.slice(2, 5))
  })
})

describe("commentMenuItem", () => {
  it("is the right-click menu's Comment: shown only with a selection, and usable while reading", () => {
    const item = commentMenuItem(() => {})

    expect(item.title).toBe("Comment")
    expect(item.when).toBe("selection")
    expect(item.readOnlySafe).toBe(true)
  })

  it("hands the selection over to be commented on, as the toolbar button does", () => {
    const onCompose = vi.fn()
    const view = mount([])
    view.dispatch({ selection: { anchor: 2, head: 5 } })

    commentMenuItem(onCompose).run(view)

    expect(onCompose).toHaveBeenCalledTimes(1)
    expect(onCompose.mock.calls[0][0].quote).toBe(NOTE.slice(2, 5))
  })

  it("does nothing without a selection", () => {
    const onCompose = vi.fn()

    commentMenuItem(onCompose).run(mount([]))

    expect(onCompose).not.toHaveBeenCalled()
  })
})
