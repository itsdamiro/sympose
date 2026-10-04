// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { Proposal } from "@/lib/persona-changes-api"

import { OutdatedChanges } from "./outdated-changes"

afterEach(cleanup)

const stale = (id: string, find: string, say = ""): Proposal => ({ id, time: "t", kind: "edit", say, find, replace: "x", before: "", after: "", status: "outdated" })

describe("OutdatedChanges", () => {
  it("draws nothing when there are none", () => {
    const { container } = render(<OutdatedChanges proposals={[]} onDecline={() => {}} />)
    expect(container.childElementCount).toBe(0)
  })

  it("says one change no longer fits, shows its passage and declines it by id", () => {
    const onDecline = vi.fn()
    render(<OutdatedChanges proposals={[stale("a", "three times", "Changed the count.")]} onDecline={onDecline} />)

    expect(screen.getByRole("status").textContent).toContain("A suggested change no longer fits")
    expect(screen.getByText("three times").getAttribute("title")).toBe("three times — Changed the count.")
    fireEvent.click(screen.getByRole("button", { name: "Decline" }))
    expect(onDecline).toHaveBeenCalledWith(["a"])
  })

  it("counts several and offers a decline on each", () => {
    const onDecline = vi.fn()
    render(<OutdatedChanges proposals={[stale("a", "one"), stale("b", "two")]} onDecline={onDecline} />)

    expect(screen.getByRole("status").textContent).toContain("2 suggested changes no longer fit")
    fireEvent.click(screen.getAllByRole("button", { name: "Decline" })[1])
    expect(onDecline).toHaveBeenCalledWith(["b"])
  })
})
