// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { Draft } from "@/lib/persona-changes-api"
import { DraftsSection } from "./drafts-section"

afterEach(cleanup)

const created: Draft = { path: "Ideas/New plan.md", name: "New plan", is_new: true, count: 1, comments: 0, time: "2" }
const edited: Draft = { path: "Garden/Beds.md", name: null, is_new: false, count: 3, comments: 0, time: "1" }
const commented: Draft = { path: "Garden/Soil.md", name: null, is_new: false, count: 0, comments: 2, time: "0" }
const both: Draft = { path: "Garden/Seeds.md", name: null, is_new: false, count: 1, comments: 4, time: "0" }
const show = (drafts: Draft[], onOpen = vi.fn(), selectedPath?: string) =>
  render(<DraftsSection drafts={drafts} onOpen={onOpen} selectedPath={selectedPath} hideExtension />)

describe("DraftsSection", () => {
  it("draws nothing without drafts", () => {
    const { container } = show([])
    expect(container.firstChild).toBeNull()
  })

  it("lists a new note under its working name marked new, and an existing note by its path with the changes waiting", () => {
    show([created, edited])
    expect(screen.getByText("Drafts")).toBeTruthy()
    expect(screen.getByText("New plan")).toBeTruthy()
    expect(screen.getByText("new")).toBeTruthy()
    expect(screen.getByText("Garden/Beds")).toBeTruthy()
    expect(screen.getByText("3")).toBeTruthy()
  })

  it("keeps the order it is given", () => {
    show([created, edited])
    const rows = screen.getAllByRole("treeitem").map((r) => r.textContent)
    expect(rows[0]).toContain("New plan")
    expect(rows[1]).toContain("Garden/Beds")
  })

  it("opens the draft whose row is chosen", () => {
    const onOpen = vi.fn()
    show([created, edited], onOpen)
    fireEvent.click(screen.getByText("Garden/Beds"))
    expect(onOpen).toHaveBeenCalledWith(edited)
  })

  it("has no row menu: a draft is not a note to pin, rename or delete", () => {
    show([created, edited])
    expect(screen.queryByLabelText(/note actions/i)).toBeNull()
  })
})

describe("DraftsSection rows", () => {
  it("keep the end label where it is when a row is focused: no menu button takes room on the right", () => {
    show([created])
    const row = screen.getByText("New plan").closest("button")!
    expect(row.className).not.toContain("pr-8")
  })

  it("names the group for what it holds: Drafts, Comments, or both", () => {
    const { rerender } = show([edited])
    expect(screen.getByText("Drafts")).toBeTruthy()

    rerender(<DraftsSection drafts={[commented]} onOpen={vi.fn()} hideExtension />)
    expect(screen.getByText("Comments")).toBeTruthy()
    expect(screen.queryByText("Drafts")).toBeNull()

    rerender(<DraftsSection drafts={[edited, commented]} onOpen={vi.fn()} hideExtension />)
    expect(screen.getByText("Drafts & comments")).toBeTruthy()
  })

  it("lists a note that has only comments, ending with how many are open and no change count", () => {
    show([commented])
    const row = screen.getByRole("treeitem")
    expect(row.textContent).toContain("Garden/Soil")
    expect(row.textContent).toContain("2")
    expect(row.querySelector("svg")).not.toBeNull()
    expect(screen.getByLabelText("2 open comments")).toBeTruthy()
    expect(screen.queryByLabelText(/change/)).toBeNull()
  })

  it("shows both the changes waiting and the open comments on a note that has both", () => {
    show([both])
    expect(screen.getByLabelText("1 change waiting")).toBeTruthy()
    expect(screen.getByLabelText("4 open comments")).toBeTruthy()
  })

  it("says 1 open comment in the singular, and a note with changes only shows no comment mark", () => {
    show([{ ...commented, comments: 1 }, edited])
    expect(screen.getByLabelText("1 open comment")).toBeTruthy()
    const rows = screen.getAllByRole("treeitem")
    expect(rows[1].querySelector('[aria-label$="open comments"], [aria-label$="open comment"]')).toBeNull()
  })

  it("opens a note that has only comments like any other draft", () => {
    const onOpen = vi.fn()
    show([commented], onOpen)
    fireEvent.click(screen.getByText("Garden/Soil"))
    expect(onOpen).toHaveBeenCalledWith(commented)
  })
})
