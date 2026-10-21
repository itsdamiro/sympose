// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"

import { EditorNotice } from "./editor-notice"

afterEach(cleanup)

describe("EditorNotice", () => {
  it("draws its title, its line, its actions and what goes under them", () => {
    render(
      <EditorNotice title="A title" actions={<button type="button">Act</button>} below={<p>Under it</p>}>
        The line.
      </EditorNotice>
    )
    expect(screen.getByText("A title")).toBeTruthy()
    expect(screen.getByText("The line.")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Act" })).toBeTruthy()
    expect(screen.getByText("Under it")).toBeTruthy()
  })

  it("leaves out the line and the actions when there are none", () => {
    const { container } = render(<EditorNotice title="Only a title" />)
    expect(container.querySelectorAll("span").length).toBe(1)
    expect(container.querySelector("button")).toBeNull()
  })

  it("sets a file's name in the monospace face and any other title in the medium weight", () => {
    const { rerender } = render(<EditorNotice title="profile.md" mono />)
    expect(screen.getByText("profile.md").className).toContain("font-mono")
    expect(screen.getByText("profile.md").className).not.toContain("font-medium")

    rerender(<EditorNotice title="A title" />)
    expect(screen.getByText("A title").className).toContain("font-medium")
    expect(screen.getByText("A title").className).not.toContain("font-mono")
  })

  it("is the properties card's sibling: its fill, corners and content gutter", () => {
    render(<EditorNotice title="t" role="status" />)
    const block = screen.getByRole("status")
    expect(block.className).toContain("sy-frontmatter-panel")
    expect(block.className).toContain("rounded-lg")
    expect(block.className).toContain("px-(--gutter,1rem)")
  })
})
