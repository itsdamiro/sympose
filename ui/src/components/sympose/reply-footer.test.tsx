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
    expect(screen.getByText("found by topic · close match")).toBeTruthy()
    fireEvent.click(toggle)
    expect(screen.queryByText("Projects/Atlas.md")).toBeNull()
  })

  it("lists a note once however it was found: its passages and ways of being found merge", () => {
    const sent: SentRecord = {
      notes: [
        { path: "Projects/Atlas.md", heading: "Goals", source: "vault", via: "opened" },
        { path: "Projects/Atlas.md", heading: "", source: "vault", via: "value" },
        { path: "Projects/Atlas.md", heading: "Risks", source: "vault", via: "opened" },
      ],
    }
    render(<ReplyFooter sent={sent} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on Atlas/ }))
    expect(screen.getAllByText("Projects/Atlas.md")).toHaveLength(1)
    expect(screen.getByText(/Goals, Risks/)).toBeTruthy()
    expect(screen.getByText("opened by a lookup · by a property value")).toBeTruthy()
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

  it("shows a reply built only from earlier conversations, and says how many exchanges, word for word", async () => {
    render(<ReplyFooter sent={chatsOnly} />)
    expect(screen.getByText(/Based on 2 earlier messages/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "More about what this reply used" }))
    expect(await screen.findByText("2 messages from earlier chats, quoted exactly")).toBeTruthy()
  })

  it("lists what she looked up herself, and names a row that found nothing by what she did", async () => {
    const sent: SentRecord = { notes: [], mode: "ask", lookups: [{ tool: "search_notes", query: "atlas", found: 0 }] }
    render(<ReplyFooter sent={sent} />)
    expect(screen.getByText(/Looked up one thing/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "More about what this reply used" }))
    expect(await screen.findByText('searched "atlas" (0 found)')).toBeTruthy()
  })

  it("keeps the standing context, and the follow-up query, behind the info icon, off the opened notes", async () => {
    render(<ReplyFooter sent={{ ...two, recaps: ["s1", "s2"], memory: ["profile"], history_dropped: 1 }} />)
    fireEvent.click(screen.getByRole("button", { name: /Based on 2 notes/ }))
    expect(screen.queryByText("the persona's memory (profile.md)")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "More about what this reply used" }))
    expect(await screen.findByText("Also searched for “atlas database”")).toBeTruthy()
    expect(screen.getByText("2 earlier-conversation recaps")).toBeTruthy()
    expect(screen.getByText("the persona's memory (profile.md)")).toBeTruthy()
    expect(screen.getByText("1 older message didn't fit in this chat")).toBeTruthy()
  })

  it("keeps the note icon before the line, whether it opens notes or is plain text", () => {
    render(<ReplyFooter sent={one} />)
    expect(screen.getByRole("button", { name: /Based on Atlas/ }).querySelector("svg")).not.toBeNull()
    cleanup()
    const { container } = render(<ReplyFooter sent={chatsOnly} />)
    expect(container.querySelector('[data-slot="reply-footer"] span svg')).not.toBeNull()
  })

  it("draws no info icon when there is nothing but notes", () => {
    render(<ReplyFooter sent={one} />)
    expect(screen.queryByRole("button", { name: "More about what this reply used" })).toBeNull()
  })

  it("keeps the closed line to one line however many notes: it truncates and never wraps", () => {
    render(<ReplyFooter sent={two} />)
    const label = screen.getByText("Based on 2 notes")
    expect(label.className).toContain("truncate")
  })
})

describe("ReplyFooter: only the references", () => {
  it("draws nothing for a cloud reply that used no references: the cloud icon is in the reply's header, not here", () => {
    expect(render(<ReplyFooter sent={{ notes: [], cloud: ["notes"], withheld: ["memory"] }} />).container.firstChild).toBeNull()
  })

  it("draws no cloud icon beside the references", () => {
    render(<ReplyFooter sent={cloud} />)
    expect(screen.getByRole("button", { name: /Based on Atlas/ })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "What was sent to the cloud model" })).toBeNull()
  })

  it("draws nothing when the references are turned off", () => {
    expect(render(<ReplyFooter sent={cloud} showReferences={false} />).container.firstChild).toBeNull()
  })
})
