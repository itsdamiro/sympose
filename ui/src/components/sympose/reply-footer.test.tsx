// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SentRecord } from "@/lib/chat-types"
import { ReplyFooter } from "./reply-footer"

afterEach(cleanup)

const one: SentRecord = { notes: [{ path: "Projects/Atlas.md", heading: "Goals", source: "vault", via: "embedding", similarity: 0.81 }] }
const two: SentRecord = {
  notes: [
    { path: "Projects/Atlas.md", heading: "", source: "vault" },
    { path: "Sympose/Settings.md", heading: "", source: "sympose" },
  ],
  searched: "atlas database",
}
const chatsOnly: SentRecord = { notes: [], chats: [{ session: "s1", turn: 2, how: "auto" }, { session: "s2", turn: 5, how: "auto" }] }
const cloud: SentRecord = { ...one, cloud: ["notes", "vault_map"], withheld: ["memory"] }

describe("ReplyFooter: the references", () => {
  it("shows nothing when nothing specific to the reply was used, or when the record is missing", () => {
    expect(render(<ReplyFooter sent={{ notes: [] }} />).container.firstChild).toBeNull()
    cleanup()
    expect(render(<ReplyFooter sent={null} />).container.firstChild).toBeNull()
    cleanup()
    // the standing context alone never makes a row
    expect(render(<ReplyFooter sent={{ notes: [], recaps: ["s1"], memory: ["profile"], history_dropped: 2 }} />).container.firstChild).toBeNull()
  })

  it("starts as one quiet line naming the note, closed", () => {
    render(<ReplyFooter sent={one} />)
    expect(screen.getByRole("button", { name: /Based on Atlas/ }).getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByText("Projects/Atlas.md")).toBeNull()
  })

  it("opens to each note with its heading and how it was found, and closes again", () => {
    render(<ReplyFooter sent={one} />)
    const toggle = screen.getByRole("button", { name: /Based on Atlas/ })
    fireEvent.click(toggle)
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByText("Projects/Atlas.md")).toBeTruthy()
    expect(screen.getByText(/Goals/)).toBeTruthy()
    expect(screen.getByText("by meaning · similarity 0.81")).toBeTruthy()
    fireEvent.click(toggle)
    expect(screen.queryByText("Projects/Atlas.md")).toBeNull()
  })

  it("opens a note of the user's vault when its path is clicked, and never offers the reference library's", () => {
    const onOpenNote = vi.fn()
    render(<ReplyFooter sent={two} onOpenNote={onOpenNote} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on 2 notes/ }))
    fireEvent.click(screen.getByRole("button", { name: "Projects/Atlas.md" }))
    expect(onOpenNote).toHaveBeenCalledWith("Projects/Atlas.md")
    expect(screen.queryByRole("button", { name: "Sympose/Settings.md" })).toBeNull()
    expect(screen.getByText("Sympose/Settings.md")).toBeTruthy()
  })

  it("shows a reply built only from earlier conversations, and says how many exchanges, word for word", () => {
    render(<ReplyFooter sent={chatsOnly} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on 2 earlier exchanges/ }))
    expect(screen.getByText("2 exchanges from earlier conversations, word for word")).toBeTruthy()
  })

  it("lists what she looked up herself, and names a row that found nothing by what she did", () => {
    const sent: SentRecord = { notes: [], mode: "ask", lookups: [{ tool: "search_notes", query: "atlas", found: 0 }] }
    render(<ReplyFooter sent={sent} />)
    fireEvent.click(screen.getByRole("button", { name: /Looked up one thing/ }))
    expect(screen.getByText('searched "atlas" (0 found)')).toBeTruthy()
  })

  it("lists the standing context, and the follow-up query, only inside a row that is already there", () => {
    render(<ReplyFooter sent={{ ...two, recaps: ["s1", "s2"], memory: ["profile"], history_dropped: 1 }} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on 2 notes/ }))
    expect(screen.getByText("Searched for “atlas database”")).toBeTruthy()
    expect(screen.getByText("2 earlier-conversation recaps")).toBeTruthy()
    expect(screen.getByText("her memory (profile.md)")).toBeTruthy()
    expect(screen.getByText("1 older turn left out of context")).toBeTruthy()
  })

  it("keeps the closed line to one line however many notes: it truncates and never wraps", () => {
    render(<ReplyFooter sent={two} />)
    const label = screen.getByText("Based on 2 notes")
    expect(label.className).toContain("truncate")
  })
})

describe("ReplyFooter: the cloud icon", () => {
  const icon = () => screen.getByRole("button", { name: "What was sent to the cloud model" })

  it("sits on the same row as the references, with an amber mark when something was held back", () => {
    render(<ReplyFooter sent={cloud} />)
    expect(icon().getAttribute("data-held")).toBe("true")
    expect(screen.getByRole("button", { name: /Based on Atlas/ })).toBeTruthy()
  })

  it("has no mark when nothing was held back", () => {
    render(<ReplyFooter sent={{ ...one, cloud: ["notes"], withheld: [] }} />)
    expect(icon().getAttribute("data-held")).toBeNull()
  })

  it("opens on a click or a tap, with what was sent and held back in plain words", async () => {
    render(<ReplyFooter sent={cloud} />)
    fireEvent.click(icon())
    expect(await screen.findByText("Sent to the cloud model: notes, vault map")).toBeTruthy()
    expect(screen.getByText("Held back: her memory")).toBeTruthy()
  })

  it("stands alone when the reply used no references", () => {
    render(<ReplyFooter sent={{ notes: [], cloud: [], withheld: ["notes"] }} />)
    expect(icon()).toBeTruthy()
    expect(screen.queryByRole("button", { name: /Based on/ })).toBeNull()
  })

  it("is not drawn for a local reply, or one that involved nothing of the vault", () => {
    render(<ReplyFooter sent={one} />)
    expect(screen.queryByRole("button", { name: "What was sent to the cloud model" })).toBeNull()
    cleanup()
    expect(render(<ReplyFooter sent={{ notes: [], cloud: [], withheld: [] }} />).container.firstChild).toBeNull()
  })
})

describe("ReplyFooter: the two display choices", () => {
  it("hides the references but keeps the icon when the line is off", () => {
    render(<ReplyFooter sent={cloud} showReferences={false} />)
    expect(screen.queryByRole("button", { name: /Based on/ })).toBeNull()
    expect(screen.getByRole("button", { name: "What was sent to the cloud model" })).toBeTruthy()
  })

  it("hides the icon but keeps the references when the cloud notice is off", () => {
    render(<ReplyFooter sent={cloud} showCloud={false} />)
    expect(screen.getByRole("button", { name: /Based on Atlas/ })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "What was sent to the cloud model" })).toBeNull()
  })

  it("draws nothing when both are off", () => {
    expect(render(<ReplyFooter sent={cloud} showReferences={false} showCloud={false} />).container.firstChild).toBeNull()
  })
})
