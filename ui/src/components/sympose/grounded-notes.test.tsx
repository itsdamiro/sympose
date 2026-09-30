// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SentRecord } from "@/lib/chat-types"
import { GroundedNotes } from "./grounded-notes"

afterEach(cleanup)

const one: SentRecord = { notes: [{ path: "Projects/Atlas.md", heading: "Goals", source: "vault", via: "embedding", similarity: 0.81 }] }
const two: SentRecord = {
  notes: [
    { path: "Projects/Atlas.md", heading: "", source: "vault" },
    { path: "Sympose/Settings.md", heading: "", source: "sympose" },
  ],
  searched: "atlas database",
}

describe("GroundedNotes", () => {
  it("shows nothing when no note grounded the reply", () => {
    const { container } = render(<GroundedNotes sent={{ notes: [] }} />)
    expect(container.firstChild).toBeNull()
    cleanup()
    expect(render(<GroundedNotes sent={null} />).container.firstChild).toBeNull()
  })

  it("starts as one quiet line naming the note", () => {
    render(<GroundedNotes sent={one} />)
    expect(screen.getByRole("button", { name: /Based on Atlas/ }).getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByText("Projects/Atlas.md")).toBeNull()
  })

  it("opens to each note with its heading and how it was found, and closes again", () => {
    render(<GroundedNotes sent={one} />)
    const toggle = screen.getByRole("button", { name: /Based on Atlas/ })
    fireEvent.click(toggle)
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByText("Projects/Atlas.md")).toBeTruthy()
    expect(screen.getByText(/Goals/)).toBeTruthy()
    expect(screen.getByText("by meaning · similarity 0.81")).toBeTruthy()
    fireEvent.click(toggle)
    expect(screen.queryByText("Projects/Atlas.md")).toBeNull()
  })

  it("opens a note of the user's vault when its path is clicked", () => {
    const onOpenNote = vi.fn()
    render(<GroundedNotes sent={one} onOpenNote={onOpenNote} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on Atlas/ }))
    fireEvent.click(screen.getByRole("button", { name: "Projects/Atlas.md" }))
    expect(onOpenNote).toHaveBeenCalledWith("Projects/Atlas.md")
  })

  it("never offers to open a note from the built-in reference library", () => {
    const onOpenNote = vi.fn()
    render(<GroundedNotes sent={two} onOpenNote={onOpenNote} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on 2 notes/ }))
    expect(screen.getByRole("button", { name: "Projects/Atlas.md" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Sympose/Settings.md" })).toBeNull()
    expect(screen.getByText("Sympose/Settings.md")).toBeTruthy()
  })

  it("says what a follow-up was rewritten into when that found the notes", () => {
    render(<GroundedNotes sent={two} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on 2 notes/ }))
    expect(screen.getByText("Searched for “atlas database”")).toBeTruthy()
  })
})
