// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { attach, setAttachmentsNote, takeAttached } from "@/lib/attachments"
import { AttachedChips } from "./attached-chips"

afterEach(() => {
  cleanup()
  act(() => setAttachmentsNote(undefined))
  takeAttached()
})

describe("AttachedChips", () => {
  it("draws nothing until something is attached: there is no chip for what goes with every message", () => {
    const { container } = render(<AttachedChips />)
    act(() => setAttachmentsNote("a.md"))
    expect(container.firstChild).toBeNull()
  })

  it("shows a chip with the attached words, and takes it off with its own button", () => {
    render(<AttachedChips />)
    act(() => {
      setAttachmentsNote("a.md")
      attach({ quote: "three times", before: "", after: "" })
    })
    expect(screen.getByText("three times")).toBeTruthy()

    fireEvent.click(screen.getByRole("button", { name: /remove .*three times/i }))

    expect(screen.queryByText("three times")).toBeNull()
    expect(takeAttached()).toEqual([])
  })

  it("goes when the message takes what was attached", () => {
    render(<AttachedChips />)
    act(() => {
      setAttachmentsNote("a.md")
      attach({ quote: "raised", before: "", after: "" })
    })
    act(() => {
      takeAttached()
    })
    expect(screen.queryByText("raised")).toBeNull()
  })
})
