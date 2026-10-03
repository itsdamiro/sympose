// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PanelCollapseButton } from "./panel-collapse-button"

afterEach(cleanup)

describe("PanelCollapseButton", () => {
  it("is an icon button named for the panel it collapses, that collapses it on a click", () => {
    const onClick = vi.fn()
    render(<PanelCollapseButton label="Collapse the editor" onClick={onClick} />)
    const button = screen.getByRole("button", { name: "Collapse the editor" })
    expect(button.querySelector("svg")).toBeTruthy()
    fireEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("looks like the other buttons of a panel's toolbar: the same size, tone and hover", () => {
    render(<PanelCollapseButton label="Collapse" onClick={() => {}} />)
    const cls = screen.getByRole("button", { name: "Collapse" }).className
    for (const token of ["size-7", "rounded-md", "text-muted-foreground", "hover:bg-accent", "hover:text-foreground"]) {
      expect(cls).toContain(token)
    }
  })
})
