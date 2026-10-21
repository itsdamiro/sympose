// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { EditorState } from "@codemirror/state"
import { EditorView } from "@codemirror/view"

import type { Proposal } from "@/lib/persona-changes-api"
import { reviewExtensions } from "@/lib/review-extensions"

import { commentMenuItem, commentToolbarItem } from "./review-toolbar"

// jsdom does no layout, so a range has no rectangles; CodeMirror asks for them to find where a position is on screen.
beforeAll(() => {
  const none = Object.assign([] as unknown as DOMRectList, { item: () => null })
  Range.prototype.getClientRects = () => none
  Range.prototype.getBoundingClientRect = () => new DOMRect(0, 0, 0, 0)
})

const NOTE = "I run three times a week. The beds are raised.\n"
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

    commentMenuItem(onCompose).run(view, { rect: new DOMRect(0, 0, 1, 1) })

    expect(onCompose).toHaveBeenCalledTimes(1)
    expect(onCompose.mock.calls[0][0].quote).toBe(NOTE.slice(2, 5))
  })

  it("opens the box beside the rectangle stylo gives for the selection (a table cell's words), not where the editor puts the position", () => {
    const onCompose = vi.fn()
    const view = mount([])
    view.dispatch({ selection: { anchor: 2, head: 5 } })
    const rect = new DOMRect(120, 340, 60, 18)

    commentMenuItem(onCompose).run(view, { rect })

    expect(onCompose.mock.calls[0][0].rect).toBe(rect)
  })

  it("does nothing without a selection", () => {
    const onCompose = vi.fn()

    commentMenuItem(onCompose).run(mount([]), { rect: new DOMRect(0, 0, 1, 1) })

    expect(onCompose).not.toHaveBeenCalled()
  })
})
