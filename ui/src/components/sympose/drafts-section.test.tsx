// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { Draft } from "@/lib/persona-changes-api"
import { DraftsSection } from "./drafts-section"

afterEach(cleanup)

const created: Draft = { path: "Ideas/New plan.md", name: "New plan", is_new: true, count: 1, comments: 0, items: 1, time: "2" }
const edited: Draft = { path: "Garden/Beds.md", name: null, is_new: false, count: 3, comments: 0, items: 3, time: "1" }
const commented: Draft = { path: "Garden/Soil.md", name: null, is_new: false, count: 0, comments: 2, items: 2, time: "0" }
const both: Draft = { path: "Garden/Seeds.md", name: null, is_new: false, count: 1, comments: 4, items: 5, time: "0" }
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
    expect(screen.getByLabelText("3 to review")).toBeTruthy()
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
    expect(screen.getByLabelText("2 to review")).toBeTruthy()
  })

  it("shows both the changes waiting and the open comments on a note that has both", () => {
    show([both])
    expect(screen.getByLabelText("5 to review")).toBeTruthy() // one number: the changes and the comments together
    expect(screen.getByRole("treeitem").textContent).not.toMatch(/review|change|comment/) // an icon and a number, no words
  })

  it("counts the items on each row on its own", () => {
    show([{ ...commented, comments: 1, items: 1 }, edited])
    const rows = screen.getAllByRole("treeitem")
    expect(rows[0].textContent).toContain("1")
    expect(rows[1].textContent).toContain("3")
    expect(rows[1].querySelector("svg")).not.toBeNull()
  })

  it("opens a note that has only comments like any other draft", () => {
    const onOpen = vi.fn()
    show([commented], onOpen)
    fireEvent.click(screen.getByText("Garden/Soil"))
    expect(onOpen).toHaveBeenCalledWith(commented)
  })

  describe("the note's own menu (right-click)", () => {
    const actions = () => ({ persona: "samantha", onRenamed: vi.fn(), onDeleted: vi.fn(), onCreated: vi.fn(), hideExtension: true })

    it("is on the row of a note that exists, with rename and delete", async () => {
      render(<DraftsSection drafts={[commented]} onOpen={vi.fn()} hideExtension actions={actions()} />)
      fireEvent.contextMenu(screen.getByText("Garden/Soil"))
      expect(await screen.findByText("Rename")).toBeTruthy()
      expect(screen.getByText("Delete")).toBeTruthy()
    })

    it("is not on a new note that has no file yet", () => {
      render(<DraftsSection drafts={[created]} onOpen={vi.fn()} hideExtension actions={actions()} />)
      fireEvent.contextMenu(screen.getByText("New plan"))
      expect(screen.queryByText("Rename")).toBeNull()
    })

    it("has no menu when no actions are given", () => {
      show([commented])
      fireEvent.contextMenu(screen.getByText("Garden/Soil"))
      expect(screen.queryByText("Rename")).toBeNull()
    })
  })
})
