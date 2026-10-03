// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { NoteBreadcrumb } from "./note-breadcrumb"
import { NoteLinksFooter } from "./note-links-footer"

afterEach(cleanup)

describe("NoteBreadcrumb", () => {
  it("shows the vault name, the folders and the file, and only the first folder navigates", () => {
    const go = vi.fn()
    render(<NoteBreadcrumb path="Movies/Sub/Alien.md" vaultName="garden" onNavigateToRootFolder={go} />)
    expect(screen.getByText("garden")).toBeTruthy()
    expect(screen.getByText("Alien.md")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Movies" }))
    expect(go).toHaveBeenCalledWith("Movies")
    expect(screen.queryByRole("button", { name: "Sub" })).toBeNull()
  })

  it("drops the vault name when there is none", () => {
    render(<NoteBreadcrumb path="A.md" vaultName={null} />)
    expect(screen.queryByText("garden")).toBeNull()
    expect(screen.getByText("A.md")).toBeTruthy()
  })
})

describe("NoteLinksFooter", () => {
  it("lists each link as a button that opens it", () => {
    const open = vi.fn()
    render(<NoteLinksFooter links={["One", "Two"]} phone={false} onWikiLinkClick={open} />)
    fireEvent.click(screen.getByRole("button", { name: "Two" }))
    expect(open).toHaveBeenCalledWith("Two")
    expect(screen.getByText("Links")).toBeTruthy()
  })
})
