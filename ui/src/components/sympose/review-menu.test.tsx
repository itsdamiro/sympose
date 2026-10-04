// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import type { EditorView } from "@codemirror/view"
import type { EditorState } from "@codemirror/state"
import type { ToolbarCustomItem } from "@damiro/stylo"

import { NoteActionsMenu } from "./note-actions-menu"

afterEach(cleanup)

const view = (state: object) => ({ state }) as unknown as EditorView
const item = (id: string, title: string, over: Partial<ToolbarCustomItem> = {}): ToolbarCustomItem => ({ id, title, icon: null, run: () => {}, ...over })

const Menu = ({ items, getView }: { items: ToolbarCustomItem[]; getView: () => EditorView | null }) => (
  <NoteActionsMenu path="A.md" persona="samantha" onRenamed={() => {}} onDeleted={() => {}} reviewItems={items} getView={getView} />
)

function open() {
  const trigger = screen.getByRole("button", { name: "Note actions" })
  fireEvent.mouseDown(trigger)
  fireEvent.mouseUp(trigger)
  fireEvent.click(trigger)
}

describe("the review entries of the note actions menu", () => {
  it("lists every item by its title", () => {
    render(<Menu items={[item("a", "Comment on it"), item("b", "Accept everything")]} getView={() => view({})} />)
    open()
    expect(screen.getByRole("menuitem", { name: "Comment on it" })).toBeTruthy()
    expect(screen.getByRole("menuitem", { name: "Accept everything" })).toBeTruthy()
  })

  it("runs an item against the editor's view", () => {
    const run = vi.fn()
    const v = view({})
    render(<Menu items={[item("a", "Comment on it", { run })]} getView={() => v} />)
    open()
    fireEvent.click(screen.getByRole("menuitem", { name: "Comment on it" }))
    expect(run).toHaveBeenCalledWith(v)
  })

  it("greys an item the editor's current state says is off, and only that one", () => {
    const disabled = (state: EditorState) => (state as unknown as { empty: boolean }).empty
    render(
      <Menu
        items={[item("a", "Comment on it", { disabled }), item("b", "Decline everything", { disabled: () => false })]}
        getView={() => view({ empty: true })}
      />,
    )
    open()
    expect(screen.getByRole("menuitem", { name: "Comment on it" }).getAttribute("aria-disabled")).toBe("true")
    expect(screen.getByRole("menuitem", { name: "Decline everything" }).getAttribute("aria-disabled")).not.toBe("true")
  })

  it("lists nothing extra without review items, and keeps the note's own actions", () => {
    render(<NoteActionsMenu path="A.md" persona="samantha" onRenamed={() => {}} onDeleted={() => {}} />)
    open()
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeTruthy()
    expect(screen.queryByRole("menuitem", { name: /comment/i })).toBeNull()
  })

  it("does nothing when the editor is not there", () => {
    const run = vi.fn()
    render(<Menu items={[item("a", "Comment on it", { run })]} getView={() => null} />)
    open()
    fireEvent.click(screen.getByRole("menuitem", { name: "Comment on it" }))
    expect(run).not.toHaveBeenCalled()
  })
})
