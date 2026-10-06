// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ChatMessage } from "./chat-message"

afterEach(cleanup)

describe("ChatMessage: the user's message", () => {
  it("shows a paperclip beside the time when passages of the note were attached", () => {
    render(
      <ChatMessage role="user" timestamp="2:03 PM" attached={1}>
        make this bold
      </ChatMessage>
    )
    expect(screen.getByRole("img", { name: "1 passage of the note attached" })).toBeTruthy()
    expect(screen.getByText("2:03 PM")).toBeTruthy()
  })

  it("says how many when there are several", () => {
    render(
      <ChatMessage role="user" timestamp="2:03 PM" attached={3}>
        hi
      </ChatMessage>
    )
    expect(screen.getByRole("img", { name: "3 passages of the note attached" }).textContent).toContain("3")
  })

  it("shows no mark on a message with nothing attached", () => {
    render(
      <ChatMessage role="user" timestamp="2:03 PM">
        hi
      </ChatMessage>
    )
    expect(screen.queryByRole("img")).toBeNull()
  })
})
