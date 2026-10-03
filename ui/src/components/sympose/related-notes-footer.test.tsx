// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { RelatedNotesFooter } from "./related-notes-footer"
import type { RelatedNote } from "@/lib/vault-related-api"

beforeEach(() => {
  document.cookie = "sympose:footer.related.open=; max-age=0; path=/"
})
afterEach(cleanup)

const related: RelatedNote[] = [
  { rel_path: "Code/Tailwind.md", title: "Tailwind", percent: 80 },
  { rel_path: "b.md", title: "b", percent: 20 },
]

function setup(over: Partial<React.ComponentProps<typeof RelatedNotesFooter>> = {}) {
  const onSelect = vi.fn()
  const view = render(
    <RelatedNotesFooter related={related} actions={{ persona: "samantha" }} hideExtension={false} onSelect={onSelect} {...over} />
  )
  return { onSelect, view }
}

describe("RelatedNotesFooter", () => {
  it("lists the neighbours under a Related caption, each with its meter, and opens one on a click", () => {
    const { onSelect } = setup()
    expect(document.querySelector('[data-slot="group-caption"]')?.textContent).toBe("Related")
    const meters = screen.getAllByRole("meter")
    expect(meters.map((m) => m.getAttribute("aria-valuenow"))).toEqual(["80", "20"])
    expect(meters[0].textContent).toBe("80%")
    fireEvent.click(screen.getByText("Tailwind.md"))
    expect(onSelect).toHaveBeenCalledWith({ type: "note", name: "Tailwind.md", path: "Code/Tailwind.md" })
  })

  it("draws nothing at all when there is nothing to show, or only what the user hid", () => {
    const { view } = setup({ related: [] })
    expect(view.container.innerHTML).toBe("")
    cleanup()
    const hidden = setup({ related: [{ ...related[0], hidden: true }] })
    expect(hidden.view.container.innerHTML).toBe("")
  })

  it("does not draw a note the user hid, and keeps the others", () => {
    setup({ related: [{ ...related[0], hidden: true }, related[1]] })
    expect(screen.queryByText("Tailwind.md")).toBeNull()
    expect(screen.getByText("b.md")).toBeTruthy()
  })

  it("can be folded away to its caption and the choice is remembered", () => {
    setup()
    fireEvent.click(screen.getByRole("button", { name: "Fold related notes" }))
    expect(screen.queryByText("b.md")).toBeNull()
    expect(screen.getByText("Related")).toBeTruthy()
    cleanup()
    setup()
    expect(screen.queryByText("b.md")).toBeNull()
  })

  it("clamps the meter into 0 to 100 and shows whole percents", () => {
    setup({
      related: [
        { rel_path: "x.md", title: "x", percent: 140 },
        { rel_path: "y.md", title: "y", percent: -5 },
        { rel_path: "z.md", title: "z", percent: 33.6 },
      ],
    })
    expect(screen.getAllByRole("meter").map((m) => [m.getAttribute("aria-valuenow"), m.textContent])).toEqual([
      ["100", "100%"],
      ["0", "0%"],
      ["34", "34%"],
    ])
  })
})
