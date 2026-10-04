// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { Draft } from "@/lib/persona-changes-api"
import { DraftsSection } from "./drafts-section"

afterEach(cleanup)

const created: Draft = { path: "Ideas/New plan.md", name: "New plan", is_new: true, count: 1, time: "2" }
const edited: Draft = { path: "Garden/Beds.md", name: null, is_new: false, count: 3, time: "1" }
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
})
