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

  it("shows the Slack mark before the time on a message written in Slack, beside the paperclip", () => {
    render(
      <ChatMessage role="user" timestamp="2:03 PM" attached={1} slack>
        hi
      </ChatMessage>
    )
    const line = screen.getByRole("img", { name: "Sent from Slack" }).parentElement as HTMLElement
    const parts = Array.from(line.childNodes).map((n) => (n as Element).getAttribute?.("aria-label") ?? n.textContent)
    expect(parts).toEqual(["Sent from Slack", "1 passage of the note attached", "2:03 PM"])
  })

  it("shows the Slack mark even when the message has no time", () => {
    render(
      <ChatMessage role="user" slack>
        hi
      </ChatMessage>
    )
    expect(screen.getByRole("img", { name: "Sent from Slack" })).toBeTruthy()
  })

  it("shows no Slack mark on a reply", () => {
    render(
      <ChatMessage role="persona" handle="samantha" timestamp="2:03 PM">
        hello
      </ChatMessage>
    )
    expect(screen.queryByRole("img", { name: "Sent from Slack" })).toBeNull()
  })
})
