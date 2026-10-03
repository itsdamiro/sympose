// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { DropdownMenu } from "@/components/ui/dropdown-menu"
import { RowActionsTrigger, rowActionClass } from "./row-actions"

afterEach(cleanup)

describe("row actions", () => {
  it("is one look for the hover control of every row: hidden until the row is hovered or focused, then a tinted button", () => {
    expect(rowActionClass).toContain("opacity-0")
    expect(rowActionClass).toContain("group-hover/row:opacity-100")
    expect(rowActionClass).toContain("focus-visible:opacity-100")
    expect(rowActionClass).toContain("hover:bg-accent")
    expect(rowActionClass).not.toContain("hover:bg-background") // the conversation list's copy had drifted to this
  })

  it("is the three-dots menu button, named for the screen reader", () => {
    render(
      <DropdownMenu>
        <RowActionsTrigger aria-label="Actions for Atlas" />
      </DropdownMenu>
    )
    const button = screen.getByRole("button", { name: "Actions for Atlas" })
    expect(button.className).toContain(rowActionClass.split(" ")[0])
    expect(button.querySelector("svg")).toBeTruthy()
  })
})
