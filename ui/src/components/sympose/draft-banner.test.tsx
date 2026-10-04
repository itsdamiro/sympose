// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import { DraftBanner } from "./draft-banner"

afterEach(cleanup)

describe("DraftBanner", () => {
  it("names the note and says it is not in the vault yet", () => {
    render(<DraftBanner name="Ideas/New plan.md" onAccept={() => {}} onDecline={() => {}} />)
    expect(screen.getByText("Ideas/New plan.md")).toBeTruthy()
    expect(screen.getByText(/not in your vault until you accept/i)).toBeTruthy()
  })

  it("accepts and declines from its own two buttons, each only its own", () => {
    const onAccept = vi.fn()
    const onDecline = vi.fn()
    render(<DraftBanner name="n" onAccept={onAccept} onDecline={onDecline} />)
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    expect([onAccept.mock.calls.length, onDecline.mock.calls.length]).toEqual([1, 0])
    fireEvent.click(screen.getByRole("button", { name: "Decline" }))
    expect([onAccept.mock.calls.length, onDecline.mock.calls.length]).toEqual([1, 1])
  })
})
