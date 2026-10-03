// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ControlRow, ControlSearchProvider, ControlSection } from "./control-section"

afterEach(() => {
  cleanup()
  document.cookie = "sympose:pref.section.notifications=; max-age=0"
})

function page(query: string) {
  return (
    <ControlSearchProvider query={query}>
      <ControlSection title="Notifications">
        <ControlRow label="Feedback messages">x</ControlRow>
        <ControlRow label="Delete confirmation" keywords="asks before a note goes to the bin">
          x
        </ControlRow>
        <ControlRow label="With a hint" hint={<p>the hint text</p>}>
          x
        </ControlRow>
      </ControlSection>
      <ControlSection title="Chat">
        <ControlRow label="Reveal speed">x</ControlRow>
      </ControlSection>
    </ControlSearchProvider>
  )
}

const rows = () => [...document.querySelectorAll('[data-slot="control-row"]')] as HTMLElement[]
const row = (label: string) => rows().find((r) => r.textContent?.includes(label))!
const section = (title: string) => [...document.querySelectorAll('[data-slot="control-section"]')].find((s) => s.textContent?.includes(title)) as HTMLElement

describe("the Settings search on ControlSection and ControlRow", () => {
  it("filters nothing with no query", () => {
    render(page(""))
    expect(rows().every((r) => !r.hidden)).toBe(true)
  })

  it("hides the rows that fail the query, keeps their place (not unmounted), and keeps those that match", () => {
    render(page("feedback"))
    expect(row("Feedback messages").hidden).toBe(false)
    expect(row("Delete confirmation").hidden).toBe(true)
    expect(screen.getByText("Delete confirmation")).toBeTruthy() // still mounted: its state is kept
  })

  it("matches a row by its keywords, and needs every word", () => {
    render(page("bin note"))
    expect(row("Delete confirmation").hidden).toBe(false)
    expect(row("Feedback messages").hidden).toBe(true)
  })

  it("shows a row's whole line, hint included, or none of it", () => {
    render(page("hint"))
    expect(row("With a hint").hidden).toBe(false)
    cleanup()
    render(page("feedback"))
    expect(row("With a hint").hidden).toBe(true)
    expect(row("With a hint").textContent).toContain("the hint text") // the hint is inside the hidden row, so it hides with it
  })

  it("shows a section's whole content when the query matches its title", () => {
    render(page("notifications"))
    expect(rows().filter((r) => r.closest('[data-slot="control-section"]') === section("Notifications")).every((r) => !r.hidden)).toBe(true)
    expect(section("Notifications").hasAttribute("data-search-match")).toBe(true)
    expect(row("Reveal speed").hidden).toBe(true)
  })

  it("marks a section with no match to be hidden when no row shows, and holds a matching one open", () => {
    render(page("reveal"))
    expect(section("Chat").className).toContain("not-has-")
    expect(section("Notifications").className).toContain("not-has-")
    // a collapsed section is held open while the query lasts, so the match can be seen
    expect(screen.getByText("Reveal speed")).toBeTruthy()
  })

  it("does not mark anything while there is no query", () => {
    render(page(""))
    expect(section("Chat").className).not.toContain("not-has-")
  })
})
