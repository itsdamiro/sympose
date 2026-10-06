// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FolderMoveDialog, type FolderMoveAsk } from "./folder-move-dialog"

afterEach(cleanup)

function show(ask: FolderMoveAsk | null) {
  const onClose = vi.fn()
  render(<FolderMoveDialog ask={ask} onClose={onClose} />)
  return onClose
}

describe("FolderMoveDialog: a folder of that name is already there", () => {
  const ask = (resolve = vi.fn()): Extract<FolderMoveAsk, { kind: "clash" }> => ({ kind: "clash", name: "People", destination: "Archive", resolve })

  it("names the folder and where, and offers a numbered name to move it under", () => {
    show(ask())
    expect(screen.getByText("“People” is already in Archive")).toBeTruthy()
    expect((screen.getByLabelText("New name for the folder") as HTMLInputElement).value).toBe("People (2)")
  })

  it("says the vault root when the destination is the root", () => {
    show({ ...ask(), destination: "" })
    expect(screen.getByText("“People” is already in the vault root")).toBeTruthy()
  })

  it("moves it under the name typed, trimmed, on Enter or the button", () => {
    const a = ask()
    const onClose = show(a)
    fireEvent.change(screen.getByLabelText("New name for the folder"), { target: { value: "  Friends " } })
    fireEvent.click(screen.getByRole("button", { name: "Move as this name" }))
    expect(a.resolve).toHaveBeenCalledExactlyOnceWith({ newName: "Friends" })
    expect(onClose).toHaveBeenCalled()
  })

  it("merges on the Merge button", () => {
    const a = ask()
    const onClose = show(a)
    fireEvent.click(screen.getByRole("button", { name: "Merge" }))
    expect(a.resolve).toHaveBeenCalledExactlyOnceWith({ merge: true })
    expect(onClose).toHaveBeenCalled()
  })

  it.each(["", "   ", "People"])("does not offer a move under the name %j: empty, or the name that is taken", (typed) => {
    show(ask())
    fireEvent.change(screen.getByLabelText("New name for the folder"), { target: { value: typed } })
    expect((screen.getByRole("button", { name: "Move as this name" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("answers nothing, once, when cancelled", () => {
    const a = ask()
    const onClose = show(a)
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    expect(a.resolve).toHaveBeenCalledExactlyOnceWith(null)
    expect(onClose).toHaveBeenCalled()
  })
})

describe("FolderMoveDialog: the files that are in both", () => {
  const files = (n: number) => Array.from({ length: n }, (_, i) => `Note ${i}.md`)
  const ask = (n: number, resolve = vi.fn()): FolderMoveAsk => ({ kind: "notes", files: files(n), resolve })

  it("lists them in one prompt and says nothing is overwritten", () => {
    show(ask(2))
    expect(screen.getByText("2 files have the same name in both folders")).toBeTruthy()
    expect(screen.getByText("Note 0.md")).toBeTruthy()
    expect(screen.getByText(/Nothing is overwritten/)).toBeTruthy()
    expect(screen.queryByText(/and \d+ more/)).toBeNull()
  })

  it("says is for one, and counts the ones not shown when there are many", () => {
    show(ask(1))
    expect(screen.getByText("1 file has the same name in both folders")).toBeTruthy()
    cleanup()
    show(ask(11))
    expect(screen.getByText("and 3 more")).toBeTruthy()
    expect(screen.queryByText("Note 10.md")).toBeNull()
  })

  it("renames them and merges on the one button, and cancels the whole merge on Cancel", () => {
    const yes = vi.fn()
    show(ask(2, yes))
    fireEvent.click(screen.getByRole("button", { name: "Rename them and merge" }))
    expect(yes).toHaveBeenCalledExactlyOnceWith(true)
    cleanup()
    const no = vi.fn()
    show(ask(2, no))
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    expect(no).toHaveBeenCalledExactlyOnceWith(false)
  })
})

describe("FolderMoveDialog: a persona's reach changes", () => {
  const reach = [
    { handle: "grace", name: "Grace", gains: 12, loses: 0 },
    { handle: "ada", name: "Ada", gains: 0, loses: 3 },
  ]

  it("says it for each persona, in the user's terms, and asks", () => {
    show({ kind: "reach", reach, resolve: vi.fn() })
    expect(screen.getByText("This gives Grace access to 12 notes.")).toBeTruthy()
    expect(screen.getByText("This takes 3 notes away from Ada.")).toBeTruthy()
    expect(screen.getByText("Move anyway?")).toBeTruthy()
  })

  it("moves on Move anyway and not on Cancel", () => {
    const yes = vi.fn()
    show({ kind: "reach", reach, resolve: yes })
    fireEvent.click(screen.getByRole("button", { name: "Move anyway" }))
    expect(yes).toHaveBeenCalledExactlyOnceWith(true)
    cleanup()
    const no = vi.fn()
    show({ kind: "reach", reach, resolve: no })
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
    expect(no).toHaveBeenCalledExactlyOnceWith(false)
  })
})

it("shows nothing while there is nothing to ask", () => {
  show(null)
  expect(screen.queryByRole("dialog")).toBeNull()
})
