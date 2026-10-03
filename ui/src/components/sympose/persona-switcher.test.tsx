// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { LivePersona } from "@/lib/personas"
import { PersonaSwitcher } from "./persona-switcher"

afterEach(cleanup)

const personas = [
  { handle: "samantha", name: "Samantha", title: "Your vault companion", model: "ollama_chat/gemma2:9b" },
  { handle: "aria", name: "Aria", title: "Keeps the reading list", model: "gemini/gemini-flash-latest" },
] as LivePersona[]

describe("PersonaSwitcher", () => {
  it("is a settings-style row: the label on the left, a persona icon for each persona on the right", () => {
    const { container } = render(<PersonaSwitcher personas={personas} active="samantha" onSwitch={() => {}} />)
    const row = container.querySelector('[data-slot="control-row"]') as HTMLElement
    expect(row.firstElementChild?.textContent).toBe("Switch persona")
    expect(screen.getByRole("button", { name: "Samantha" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Aria" })).toBeTruthy()
  })

  it("draws the icons at the size of the main menu's persona icon", () => {
    render(<PersonaSwitcher personas={personas} active="samantha" onSwitch={() => {}} />)
    const avatar = screen.getByRole("button", { name: "Aria" }).querySelector('[data-slot="avatar"]')
    expect(avatar?.getAttribute("data-size")).toBe("sm")
  })

  it("marks the active persona, and switches only to another one", () => {
    const onSwitch = vi.fn()
    render(<PersonaSwitcher personas={personas} active="samantha" onSwitch={onSwitch} />)
    expect(screen.getByRole("button", { name: "Samantha" }).getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Aria" }).getAttribute("aria-pressed")).toBe("false")
    fireEvent.click(screen.getByRole("button", { name: "Samantha" }))
    expect(onSwitch).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Aria" }))
    expect(onSwitch).toHaveBeenCalledWith("aria")
  })

  it("shows the persona's name with its short description when an icon is hovered or focused", async () => {
    render(<PersonaSwitcher personas={personas} active="samantha" onSwitch={() => {}} />)
    fireEvent.focus(screen.getByRole("button", { name: "Aria" }))
    expect(await screen.findByText("Keeps the reading list")).toBeTruthy()
    expect(screen.getByText("Aria")).toBeTruthy() // the popup's heading
  })
})
