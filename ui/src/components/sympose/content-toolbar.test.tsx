// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import * as React from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ContentToolbar } from "./content-toolbar"

afterEach(cleanup)

function setup(over: Partial<React.ComponentProps<typeof ContentToolbar>> = {}) {
  const mocks = {
    goBack: vi.fn(),
    goForward: vi.fn(),
    setSearchOpen: vi.fn(),
    setVaultSearch: vi.fn(),
    closeSearch: vi.fn(),
    setCreateName: vi.fn(),
    closeCreate: vi.fn(),
    toggleCreate: vi.fn(),
    submitCreate: vi.fn().mockResolvedValue(undefined),
  }
  const props: React.ComponentProps<typeof ContentToolbar> = {
    canGoBack: true,
    canGoForward: true,
    searchOpen: false,
    vaultSearch: "",
    searchInputRef: React.createRef<HTMLInputElement>(),
    isSentinel: false,
    pendingCreate: null,
    createName: "",
    creating: false,
    noteInputRef: React.createRef<HTMLInputElement>(),
    folderInputRef: React.createRef<HTMLInputElement>(),
    ...mocks,
    ...over,
  }
  render(<ContentToolbar {...props} />)
  return mocks
}

describe("ContentToolbar: back and forward", () => {
  it("goes back and forward", () => {
    const p = setup()
    fireEvent.click(screen.getByLabelText("Back"))
    fireEvent.click(screen.getByLabelText("Forward"))
    expect(p.goBack).toHaveBeenCalledTimes(1)
    expect(p.goForward).toHaveBeenCalledTimes(1)
  })

  it("disables each button when there is nowhere to go", () => {
    setup({ canGoBack: false, canGoForward: false })
    expect((screen.getByLabelText("Back") as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText("Forward") as HTMLButtonElement).disabled).toBe(true)
  })

  it("keeps the one that has somewhere to go enabled", () => {
    setup({ canGoBack: true, canGoForward: false })
    expect((screen.getByLabelText("Back") as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByLabelText("Forward") as HTMLButtonElement).disabled).toBe(true)
  })
})

describe("ContentToolbar: search", () => {
  const field = () => screen.getByRole("textbox", { name: "Search vault" })
  const toggle = () => screen.getByRole("button", { name: "Search vault" })

  it("opens the field from its icon, and closes it from the same icon", () => {
    const closed = setup()
    fireEvent.click(toggle())
    expect(closed.setSearchOpen).toHaveBeenCalledWith(true)
    expect(closed.closeSearch).not.toHaveBeenCalled()
    cleanup()
    const open = setup({ searchOpen: true })
    fireEvent.click(toggle())
    expect(open.closeSearch).toHaveBeenCalledTimes(1)
    expect(open.setSearchOpen).not.toHaveBeenCalled()
  })

  it("shows whether it is open, and takes the field out of the tab order while shut", () => {
    setup({ searchOpen: false })
    expect(toggle().getAttribute("aria-pressed")).toBe("false")
    expect(field().getAttribute("tabindex")).toBe("-1")
    cleanup()
    setup({ searchOpen: true })
    expect(toggle().getAttribute("aria-pressed")).toBe("true")
    expect(field().getAttribute("tabindex")).toBe("0")
  })

  it("passes what is typed on, and shows the query", () => {
    const p = setup({ searchOpen: true, vaultSearch: "abc" })
    expect((field() as HTMLInputElement).value).toBe("abc")
    fireEvent.change(field(), { target: { value: "abcd" } })
    expect(p.setVaultSearch).toHaveBeenCalledWith("abcd")
  })

  it("closes on Escape, and not on other keys", () => {
    const p = setup({ searchOpen: true, vaultSearch: "abc" })
    fireEvent.keyDown(field(), { key: "a" })
    expect(p.closeSearch).not.toHaveBeenCalled()
    fireEvent.keyDown(field(), { key: "Escape" })
    expect(p.closeSearch).toHaveBeenCalledTimes(1)
  })

  it("hides itself when left empty, but keeps a query that is still being used", () => {
    const empty = setup({ searchOpen: true, vaultSearch: "" })
    fireEvent.blur(field())
    expect(empty.closeSearch).toHaveBeenCalledTimes(1)
    cleanup()
    const used = setup({ searchOpen: true, vaultSearch: "abc" })
    fireEvent.blur(field())
    expect(used.closeSearch).not.toHaveBeenCalled()
  })

  it("offers to clear a query, and clears it without closing the field, keeping focus in it", () => {
    const p = setup({ searchOpen: true, vaultSearch: "abc" })
    fireEvent.click(screen.getByLabelText("Clear search"))
    expect(p.setVaultSearch).toHaveBeenCalledWith("")
    expect(p.closeSearch).not.toHaveBeenCalled()
  })

  it("offers no clear button while the field is empty", () => {
    setup({ searchOpen: true, vaultSearch: "" })
    expect(screen.queryByLabelText("Clear search")).toBeNull()
  })

  it("keeps the clear button from stealing focus, so clearing is not read as the field losing it", () => {
    setup({ searchOpen: true, vaultSearch: "abc" })
    const notPrevented = fireEvent.mouseDown(screen.getByLabelText("Clear search"))
    expect(notPrevented).toBe(false)
  })
})

describe("ContentToolbar: new note and new folder", () => {
  it("opens each from its icon", () => {
    const p = setup()
    fireEvent.click(screen.getByRole("button", { name: "New note" }))
    fireEvent.click(screen.getByRole("button", { name: "New folder" }))
    expect(p.toggleCreate.mock.calls).toEqual([["note"], ["folder"]])
  })

  it("shows which one is open", () => {
    setup({ pendingCreate: "folder" })
    expect(screen.getByRole("button", { name: "New note" }).getAttribute("aria-pressed")).toBe("false")
    expect(screen.getByRole("button", { name: "New folder" }).getAttribute("aria-pressed")).toBe("true")
  })

  it("shows what is typed only in the field that is open", () => {
    setup({ pendingCreate: "note", createName: "Fresh" })
    expect((screen.getByLabelText("New note filename") as HTMLInputElement).value).toBe("Fresh")
    expect((screen.getByLabelText("New folder name") as HTMLInputElement).value).toBe("")
  })

  it("shows the typed name in the folder field, and not the note field, when a folder is being named", () => {
    setup({ pendingCreate: "folder", createName: "Box" })
    expect((screen.getByLabelText("New folder name") as HTMLInputElement).value).toBe("Box")
    expect((screen.getByLabelText("New note filename") as HTMLInputElement).value).toBe("")
  })

  it("keeps the field that is not open out of the tab order", () => {
    setup({ pendingCreate: "folder" })
    expect(screen.getByLabelText("New note filename").getAttribute("tabindex")).toBe("-1")
    expect(screen.getByLabelText("New folder name").getAttribute("tabindex")).toBe("0")
    cleanup()
    setup({ pendingCreate: "note" })
    expect(screen.getByLabelText("New note filename").getAttribute("tabindex")).toBe("0")
    expect(screen.getByLabelText("New folder name").getAttribute("tabindex")).toBe("-1")
  })

  it("passes on what is typed, in either field", () => {
    const p = setup({ pendingCreate: "note" })
    fireEvent.change(screen.getByLabelText("New note filename"), { target: { value: "a" } })
    fireEvent.change(screen.getByLabelText("New folder name"), { target: { value: "b" } })
    expect(p.setCreateName.mock.calls).toEqual([["a"], ["b"]])
  })

  it("creates on Enter and closes on Escape, in either field, and ignores other keys", () => {
    for (const label of ["New note filename", "New folder name"]) {
      const p = setup({ pendingCreate: label === "New note filename" ? "note" : "folder" })
      fireEvent.keyDown(screen.getByLabelText(label), { key: "x" })
      expect(p.submitCreate).not.toHaveBeenCalled()
      expect(p.closeCreate).not.toHaveBeenCalled()
      fireEvent.keyDown(screen.getByLabelText(label), { key: "Enter" })
      expect(p.submitCreate).toHaveBeenCalledTimes(1)
      expect(p.closeCreate).not.toHaveBeenCalled()
      fireEvent.keyDown(screen.getByLabelText(label), { key: "Escape" })
      expect(p.submitCreate).toHaveBeenCalledTimes(1)
      expect(p.closeCreate).toHaveBeenCalledTimes(1)
      cleanup()
    }
  })

  it("closes when focus leaves either field", () => {
    const p = setup({ pendingCreate: "note" })
    fireEvent.blur(screen.getByLabelText("New note filename"))
    fireEvent.blur(screen.getByLabelText("New folder name"))
    expect(p.closeCreate).toHaveBeenCalledTimes(2)
  })

  it("locks both fields while a create is running", () => {
    setup({ pendingCreate: "note", creating: true })
    expect((screen.getByLabelText("New note filename") as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText("New folder name") as HTMLButtonElement).disabled).toBe(true)
  })

  it("is left out entirely on Settings, Persona and the Bin, while search and back stay", () => {
    setup({ isSentinel: true })
    expect(screen.queryByRole("button", { name: "New note" })).toBeNull()
    expect(screen.queryByRole("button", { name: "New folder" })).toBeNull()
    expect(screen.queryByLabelText("New note filename")).toBeNull()
    expect(screen.getByLabelText("Back")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Search vault" })).toBeTruthy()
  })
})
