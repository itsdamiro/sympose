// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ChatTurn } from "@/lib/chat-types"
import { ChatPanel } from "./chat-panel"

afterEach(cleanup)

function setup(props: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const onSubmit = vi.fn()
  render(<ChatPanel turns={[]} draft="hello" onDraftChange={() => {}} onSubmit={onSubmit} {...props} />)
  return { onSubmit }
}

const enter = () => fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" })

describe("ChatPanel", () => {
  it("sends the draft on Enter", () => {
    const { onSubmit } = setup()
    enter()
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it("does not send while a reply is in flight", () => {
    const { onSubmit } = setup({ sending: true })
    enter()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("says what the reply in flight is doing, in the terminal's own words", () => {
    setup({ sending: true, phase: "searching" })
    expect(screen.getByText("Searching your notes…")).toBeTruthy()
  })

  it("says it is thinking when the backend has not named a phase yet", () => {
    setup({ sending: true, phase: null })
    expect(screen.getByText("Thinking about your message…")).toBeTruthy()
  })

  it("shows no status line when nothing is in flight", () => {
    setup()
    expect(screen.queryByText(/Searching|Reading|Thinking/)).toBeNull()
  })

  it("draws a system turn as a system line between the conversation", () => {
    const turns: ChatTurn[] = [
      { id: "1", role: "user", body: "hi" },
      { id: "2", role: "system", kind: "error", body: "@samantha couldn't reply: offline" },
    ]
    setup({ turns })
    expect(screen.getByRole("alert").textContent).toBe("@samantha couldn't reply: offline")
  })
})
