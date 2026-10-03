// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { CollapsibleFooterSection } from "./collapsible-footer-section"

const clear = (id: string) => {
  document.cookie = `sympose:footer.${id}.open=; max-age=0; path=/`
}
beforeEach(() => {
  clear("one")
  clear("two")
})
afterEach(cleanup)

const section = (id: string, body = "the body") => (
  <CollapsibleFooterSection id={id} label={`${id} things`} caption={<span>Caption {id}</span>}>
    <p>{body}</p>
  </CollapsibleFooterSection>
)

describe("CollapsibleFooterSection", () => {
  it("is open by default, shows its caption, and folds down to just the caption", () => {
    render(section("one"))
    expect(screen.getByText("the body")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Fold one things" }))
    expect(screen.queryByText("the body")).toBeNull()
    expect(screen.getByText("Caption one")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Show one things" }).getAttribute("aria-expanded")).toBe("false")
  })

  it("keeps each section's choice apart, under its own cookie, across a remount", () => {
    render(
      <>
        {section("one", "body one")}
        {section("two", "body two")}
      </>
    )
    fireEvent.click(screen.getByRole("button", { name: "Fold one things" }))
    cleanup()
    render(
      <>
        {section("one", "body one")}
        {section("two", "body two")}
      </>
    )
    expect(screen.queryByText("body one")).toBeNull()
    expect(screen.getByText("body two")).toBeTruthy()
  })

  it("takes its content's height with no fixed height or viewport cap, and scrolls inside only when squeezed", () => {
    render(section("one"))
    const body = screen.getByText("the body").parentElement!
    expect(body.className).toContain("min-h-0")
    expect(body.className).toContain("overflow-y-auto")
    expect(body.className).not.toMatch(/(^|\s)(h-|max-h-)/)
  })
})
