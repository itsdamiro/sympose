// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("./trash-list", () => ({ TrashList: () => <div data-testid="notes" /> }))
vi.mock("./conversation-bin", () => ({ ConversationBin: () => <div data-testid="conversations" /> }))

import { getCookie, setCookie } from "@/lib/cookies"
import { useBinPreferences } from "@/lib/use-bin-section-preference"
import { BinSectionPills, BinView } from "./bin-view"

afterEach(() => {
  cleanup()
  document.cookie = "sympose:bin.section=; max-age=0; path=/"
})

const props = { persona: "samantha", refreshKey: 0, conversationsKey: 0, onNoteRestored: () => {}, onConversationRestored: () => {} }

describe("BinView", () => {
  it("lists the notes or the conversations, never both", () => {
    const { rerender } = render(<BinView {...props} section="notes" />)
    expect(screen.getByTestId("notes")).toBeTruthy()
    expect(screen.queryByTestId("conversations")).toBeNull()
    rerender(<BinView {...props} section="conversations" />)
    expect(screen.getByTestId("conversations")).toBeTruthy()
    expect(screen.queryByTestId("notes")).toBeNull()
  })
})

describe("BinSectionPills", () => {
  it("shows which half is listed and offers the other", () => {
    const onChange = vi.fn()
    render(<BinSectionPills section="notes" onChange={onChange} />)
    expect(screen.getByRole("button", { name: "Notes" }).getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Conversations" }).getAttribute("aria-pressed")).toBe("false")
    fireEvent.click(screen.getByRole("button", { name: "Conversations" }))
    expect(onChange).toHaveBeenCalledWith("conversations")
  })
})

describe("the Bin's choice is kept in a cookie", () => {
  function Harness() {
    const [bin, setBin] = useBinPreferences()
    return <BinSectionPills section={bin.section} onChange={(s) => setBin("section", s)} />
  }

  it("starts on notes, writes the choice, and starts from it next time", () => {
    const first = render(<Harness />)
    expect(screen.getByRole("button", { name: "Notes" }).getAttribute("aria-pressed")).toBe("true")
    fireEvent.click(screen.getByRole("button", { name: "Conversations" }))
    expect(getCookie("sympose:bin.section")).toBe("conversations")
    first.unmount()
    render(<Harness />)
    expect(screen.getByRole("button", { name: "Conversations" }).getAttribute("aria-pressed")).toBe("true")
  })

  it("falls back to notes on a value it does not know", () => {
    setCookie("sympose:bin.section", "garbage")
    render(<Harness />)
    expect(screen.getByRole("button", { name: "Notes" }).getAttribute("aria-pressed")).toBe("true")
  })
})
