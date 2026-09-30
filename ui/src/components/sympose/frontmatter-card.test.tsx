// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FrontmatterCard } from "./frontmatter-card"

afterEach(cleanup)

describe("FrontmatterCard scalar editing", () => {
  it("does not rewrite a value the user opened and left unchanged", () => {
    const onChange = vi.fn()
    render(<FrontmatterCard raw={"draft: true\npriority: 3"} onChange={onChange} />)
    const value = screen.getByText("true")
    fireEvent.click(value)
    fireEvent.blur(screen.getByDisplayValue("true"))
    expect(onChange).not.toHaveBeenCalled()
  })

  it("writes a value the user changed", () => {
    const onChange = vi.fn()
    render(<FrontmatterCard raw={"status: open"} onChange={onChange} />)
    fireEvent.click(screen.getByText("open"))
    fireEvent.change(screen.getByDisplayValue("open"), { target: { value: "done" } })
    fireEvent.blur(screen.getByDisplayValue("done"))
    expect(onChange).toHaveBeenCalledWith("status: done")
  })

  it("shows a nested map as read-only text and never edits it", () => {
    const onChange = vi.fn()
    render(<FrontmatterCard raw={"meta:\n  a: 1"} onChange={onChange} />)
    fireEvent.click(screen.getByText('{"a":1}'))
    expect(screen.queryByRole("textbox")).toBeNull()
    expect(onChange).not.toHaveBeenCalled()
  })
})
