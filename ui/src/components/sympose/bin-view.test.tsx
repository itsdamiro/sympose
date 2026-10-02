// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("./trash-list", () => ({ TrashList: () => <div data-testid="notes" /> }))
vi.mock("./conversation-bin", () => ({ ConversationBin: () => <div data-testid="conversations" /> }))

import { BinView } from "./bin-view"

afterEach(cleanup)

describe("BinView", () => {
  it("keeps notes and conversations apart, notes first, and switches between them", () => {
    render(<BinView persona="samantha" refreshKey={0} conversationsKey={0} onNoteRestored={() => {}} onConversationRestored={() => {}} />)
    expect(screen.getByTestId("notes")).toBeTruthy()
    expect(screen.queryByTestId("conversations")).toBeNull()
    fireEvent.click(screen.getByRole("radio", { name: "Conversations" }))
    expect(screen.getByTestId("conversations")).toBeTruthy()
    expect(screen.queryByTestId("notes")).toBeNull()
    fireEvent.click(screen.getByRole("radio", { name: "Notes" }))
    expect(screen.getByTestId("notes")).toBeTruthy()
  })
})
