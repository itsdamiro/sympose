// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { CloudNotice } from "./cloud-notice"

afterEach(cleanup)

const state = (over: Record<string, unknown> = {}) => ({
  model: "gemini/gemini-flash-latest",
  cloud: true,
  categories: [
    { name: "notes", description: "passages of your notes", shared: false },
    { name: "recaps", description: "recaps of earlier conversations", shared: true },
  ],
  ...over,
})

describe("CloudNotice", () => {
  it("says what a cloud model always receives and names the model", () => {
    render(<CloudNotice state={state()} onChange={vi.fn()} />)
    expect(screen.getByText("gemini/gemini-flash-latest")).toBeTruthy()
    expect(screen.getByText(/receives your messages and this conversation/)).toBeTruthy()
  })

  it("says nothing of the vault is sent while every kind is off", () => {
    const off = state({ categories: [{ name: "notes", description: "d", shared: false }] })
    render(<CloudNotice state={off} onChange={vi.fn()} />)
    expect(screen.getByText(/Nothing from your vault is sent until you switch a kind on/)).toBeTruthy()
  })

  it("says the vault may be sent once something is on", () => {
    render(<CloudNotice state={state()} onChange={vi.fn()} />)
    expect(screen.getByText(/may also receive what is switched on below/)).toBeTruthy()
  })

  it("shows each category as a switch in its own state, with what it is on hover", () => {
    render(<CloudNotice state={state()} onChange={vi.fn()} />)
    expect(screen.getByRole("button", { name: "notes" }).getAttribute("aria-pressed")).toBe("false")
    expect(screen.getByRole("button", { name: "recaps" }).getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "notes" }).getAttribute("title")).toBe("passages of your notes")
  })

  it("asks for the opposite of a category's state when it is clicked", () => {
    const onChange = vi.fn()
    render(<CloudNotice state={state()} onChange={onChange} />)
    fireEvent.click(screen.getByRole("button", { name: "notes" }))
    fireEvent.click(screen.getByRole("button", { name: "recaps" }))
    expect(onChange).toHaveBeenNthCalledWith(1, "notes", true)
    expect(onChange).toHaveBeenNthCalledWith(2, "recaps", false)
  })

  it("shows nothing for a local model, or while the state is not known", () => {
    const { container, rerender } = render(<CloudNotice state={state({ cloud: false })} onChange={vi.fn()} />)
    expect(container.textContent).toBe("")
    rerender(<CloudNotice state={null} onChange={vi.fn()} />)
    expect(container.textContent).toBe("")
  })
})
