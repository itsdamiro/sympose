// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { EditorState } from "@codemirror/state"
import { EditorView } from "@codemirror/view"

import { captureContext } from "@/lib/passage-finder"
import type { Proposal } from "@/lib/persona-changes-api"
import { reviewExtensions } from "@/lib/review-extensions"

import { reviewToolbarItems } from "./review-toolbar"

const NOTE = "I run three times a week. The beds are raised.\n"
const edit = (id: string, find: string, replace: string): Proposal => {
  const at = NOTE.indexOf(find)
  const [before, after] = captureContext(NOTE, at, at + find.length)
  return { id, time: "t", kind: "edit", say: "", find, replace, before, after, status: "pending" }
}
const views: EditorView[] = []
const mount = (proposals: Proposal[], doc = NOTE) => {
  const view = new EditorView({
    state: EditorState.create({ doc, extensions: [reviewExtensions({ initial: () => ({ proposals, annotations: [] }), onResolve: () => {}, gutter: false })] }),
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
