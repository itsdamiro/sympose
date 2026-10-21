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
  it("has the persona icons on the far left, named as one group, with no label of its own", () => {
    const { container } = render(<PersonaSwitcher personas={personas} active="samantha" onSwitch={() => {}} />)
    const row = container.querySelector('[data-slot="persona-switcher"]') as HTMLElement
    const group = screen.getByRole("group", { name: "Switch persona" })
    expect(row.firstElementChild).toBe(group)
    expect(group.querySelectorAll("button")).toHaveLength(2)
    expect(row.textContent).toBe("")
    expect(row.className).toContain("justify-between")
  })

  it("shows the Slack dot at the far right while the persona is connected, and nothing otherwise", () => {
    const { container, rerender } = render(<PersonaSwitcher personas={personas} active="samantha" onSwitch={() => {}} />)
    expect(container.querySelector("[data-slot=slack-dot]")).toBeNull()
    rerender(<PersonaSwitcher personas={personas} active="samantha" onSwitch={() => {}} slack />)
    const row = container.querySelector('[data-slot="persona-switcher"]') as HTMLElement
    expect(row.lastElementChild).toBe(container.querySelector("[data-slot=slack-dot]"))
    expect(row.lastElementChild?.textContent).toBe("Slack")
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
