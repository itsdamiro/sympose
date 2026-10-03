// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatActionGroup } from "./chat-action-group"

afterEach(cleanup)

describe("ChatActionGroup", () => {
  it("keeps its chip look, for the other places the toolbar will be used: a small secondary pill of icon buttons", () => {
    const { container } = render(<ChatActionGroup />)
    const group = container.querySelector('[data-slot="chat-action-group"]') as HTMLElement
    expect(group.className).toContain("bg-secondary")
    expect(group.className).toContain("rounded-md")
    expect(group.className).toContain("p-0.5")
    for (const button of screen.getAllByRole("button")) expect(button.className).toContain("size-7")
  })

  it("has the chat toggle only: no placeholder buttons beside it", () => {
    render(<ChatActionGroup />)
    expect(screen.getAllByRole("button")).toHaveLength(1)
    expect(screen.queryByRole("button", { name: "Bookmark conversation" })).toBeNull()
  })

  it("toggles the chat panel and carries its state", () => {
    const onToggleChat = vi.fn()
    render(<ChatActionGroup chatOpen onToggleChat={onToggleChat} />)
    const chat = screen.getByRole("button", { name: "Chat" })
    expect(chat.getAttribute("aria-pressed")).toBe("true")
    fireEvent.click(chat)
    expect(onToggleChat).toHaveBeenCalledTimes(1)
  })
})
