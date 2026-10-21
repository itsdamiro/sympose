// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { EditorState } from "@codemirror/state"
import { EditorView } from "@codemirror/view"

import { captureContext } from "@/lib/passage-finder"
import type { Proposal } from "@/lib/persona-changes-api"
import { reviewExtensions } from "@/lib/review-extensions"

import { acceptAllIn, ReviewNotice } from "./review-notice"

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
afterEach(() => {
  cleanup()
  views.splice(0).forEach((v) => v.destroy())
})

describe("acceptAllIn", () => {
  it("accepts every change in the text at once and says it did", () => {
    const view = mount([edit("a", "three times", "four times"), edit("b", "raised", "sunken")])

    expect(acceptAllIn(view)).toBe(true)
    expect(view.state.doc.toString()).toBe("I run four times a week. The beds are sunken.\n")
  })

  it("says nothing was accepted when no change is in the text any more", () => {
    const view = mount([edit("a", "three times", "four times")], NOTE.replace("three times", "five times"))

    expect(acceptAllIn(view)).toBe(false)
    expect(view.state.doc.toString()).toContain("five times")
  })
})

describe("ReviewNotice", () => {
  it("draws nothing when no change is waiting", () => {
    const { container } = render(<ReviewNotice personaName="Samantha" count={0} onAccept={() => {}} onDecline={() => {}} />)
    expect(container.childElementCount).toBe(0)
  })

  it("names the persona and counts what she suggested, one or several", () => {
    const { rerender } = render(<ReviewNotice personaName="Samantha" count={1} onAccept={() => {}} onDecline={() => {}} />)
    expect(screen.getByRole("status").textContent).toContain("Samantha suggested 1 change")
    expect(screen.getByRole("status").textContent).not.toContain("changes")

    rerender(<ReviewNotice personaName="Samantha" count={3} onAccept={() => {}} onDecline={() => {}} />)
    expect(screen.getByRole("status").textContent).toContain("Samantha suggested 3 changes")
  })

  it("accepts and declines the whole note from its two buttons, each only its own", () => {
    const onAccept = vi.fn()
    const onDecline = vi.fn()
    render(<ReviewNotice personaName="Samantha" count={2} onAccept={onAccept} onDecline={onDecline} />)

    fireEvent.click(screen.getByRole("button", { name: "Accept all" }))
    expect([onAccept.mock.calls.length, onDecline.mock.calls.length]).toEqual([1, 0])
    fireEvent.click(screen.getByRole("button", { name: "Decline all" }))
    expect([onAccept.mock.calls.length, onDecline.mock.calls.length]).toEqual([1, 1])
  })
})
