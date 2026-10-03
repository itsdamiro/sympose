// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { CloudSentIcon } from "./cloud-sent-icon"

afterEach(cleanup)

const icon = () => screen.getByRole("button", { name: "What was sent to the cloud model" })

describe("CloudSentIcon", () => {
  it("carries an amber mark when something was held back, so that case shows without opening it", () => {
    render(<CloudSentIcon sent={{ notes: [], cloud: ["notes"], withheld: ["memory"] }} />)
    expect(icon().getAttribute("data-held")).toBe("true")
    cleanup()
    render(<CloudSentIcon sent={{ notes: [], cloud: ["notes"], withheld: [] }} />)
    expect(icon().getAttribute("data-held")).toBeNull()
  })

  it("opens on a click or a tap, with which model answered and what was sent and held back, in plain words", async () => {
    render(<CloudSentIcon model="gemini/gemini-flash-latest" sent={{ notes: [], cloud: ["notes", "vault_map"], withheld: ["memory"] }} />)
    fireEvent.click(icon())
    expect(await screen.findByText("Answered by gemini/gemini-flash-latest")).toBeTruthy()
    expect(screen.getByText("Sent to the cloud model: notes, vault map")).toBeTruthy()
    expect(screen.getByText("Held back: her memory")).toBeTruthy()
  })

  it("says only what it knows: no model line without a model, no held-back line when nothing was held back", async () => {
    render(<CloudSentIcon sent={{ notes: [], cloud: ["notes"], withheld: [] }} />)
    fireEvent.click(icon())
    expect(await screen.findByText("Sent to the cloud model: notes")).toBeTruthy()
    expect(screen.queryByText(/Answered by/)).toBeNull()
    expect(screen.queryByText(/Held back/)).toBeNull()
  })

  it("is the size of the persona's avatar beside it, so the header reads as one row", () => {
    render(<CloudSentIcon sent={{ notes: [], cloud: ["notes"] }} />)
    expect(icon().className).toContain("size-6")
  })
})
