// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ReplyModelChip } from "./reply-model-chip"

afterEach(cleanup)

const M = "gemini/gemini-flash-latest"
const chip = () => screen.getByRole("button", { name: /what was sent to the cloud model/ })

describe("ReplyModelChip", () => {
  it("is the plain model chip when nothing went to a cloud model, or the mark is turned off", () => {
    const { container } = render(<ReplyModelChip model="ollama_chat/gemma2:9b" sent={{ notes: [] }} />)
    expect(container.querySelector('[data-slot="model-chip"]')?.textContent).toBe("ollama_chat/gemma2:9b")
    expect(screen.queryByRole("button")).toBeNull()
    cleanup()
    render(<ReplyModelChip model={M} sent={{ notes: [], cloud: ["notes"] }} showCloudSent={false} />)
    expect(screen.queryByRole("button")).toBeNull()
    expect(screen.getByText(M)).toBeTruthy()
  })

  it("keeps the model's name on the chip and marks it amber when something was held back", () => {
    render(<ReplyModelChip model={M} sent={{ notes: [], cloud: ["notes"], withheld: ["memory"] }} />)
    expect(chip().textContent).toContain(M)
    expect(chip().getAttribute("data-held")).toBe("true")
    cleanup()
    render(<ReplyModelChip model={M} sent={{ notes: [], cloud: ["notes"], withheld: [] }} />)
    expect(chip().getAttribute("data-held")).toBeNull()
  })

  it("opens on a click or a tap with what was sent and held back, in plain words", async () => {
    render(<ReplyModelChip model={M} sent={{ notes: [], cloud: ["notes", "vault_map"], withheld: ["memory"] }} />)
    fireEvent.click(chip())
    expect(await screen.findByText("Sent to the cloud model: notes, vault map")).toBeTruthy()
    expect(screen.getByText("Held back: the persona's memory")).toBeTruthy()
  })

  it("says no held-back line when nothing was held back", async () => {
    render(<ReplyModelChip model={M} sent={{ notes: [], cloud: ["notes"], withheld: [] }} />)
    fireEvent.click(chip())
    expect(await screen.findByText("Sent to the cloud model: notes")).toBeTruthy()
    expect(screen.queryByText(/Held back/)).toBeNull()
  })
})
