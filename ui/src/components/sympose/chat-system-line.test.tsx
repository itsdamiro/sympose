// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ChatSystemLine } from "./chat-system-line"

afterEach(cleanup)

describe("ChatSystemLine", () => {
  it("announces an error as an alert", () => {
    render(<ChatSystemLine kind="error">@samantha couldn't reply</ChatSystemLine>)
    expect(screen.getByRole("alert").textContent).toBe("@samantha couldn't reply")
  })

  it("marks the other kinds as plain status text", () => {
    render(<ChatSystemLine kind="notice">Older turns were left out</ChatSystemLine>)
    expect(screen.getByRole("status").getAttribute("data-kind")).toBe("notice")
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("shows text exactly as given, never as markup", () => {
    render(<ChatSystemLine kind="output">{"Todo [x] item <b>not bold</b>"}</ChatSystemLine>)
    expect(screen.getByRole("status").textContent).toBe("Todo [x] item <b>not bold</b>")
  })
})
