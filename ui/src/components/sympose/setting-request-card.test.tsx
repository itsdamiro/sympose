// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SettingRequest } from "@/lib/confirmations-api"
import { SettingRequestCard } from "./setting-request-card"

afterEach(cleanup)

const request = (over: Partial<SettingRequest> = {}): SettingRequest => ({
  id: "r1", kind: "setting", state: "waiting", reason: null, created_at: "t",
  setting: { name: "history_tokens", label: "Most earlier chat sent per message (history_tokens)", summary: "", from: "automatic", to: "3000", note: null },
  ...over,
})

describe("SettingRequestCard", () => {
  it("shows what the setting is and the change from and to; a line on what it does only where the label does not say it", () => {
    render(<SettingRequestCard request={request()} onAnswer={vi.fn()} />)
    expect(screen.getByText("Most earlier chat sent per message (history_tokens)")).toBeTruthy()
    expect(screen.getByLabelText("From automatic to 3000")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy()
  })

  it("shows the line on what a setting does when it has one", () => {
    render(<SettingRequestCard request={request({ setting: { ...request().setting, summary: "the model this persona answers with" } })} onAnswer={vi.fn()} />)
    expect(screen.getByText("the model this persona answers with")).toBeTruthy()
  })

  it("says the consequence on its own line when there is one", () => {
    const note = "A cloud model may then receive this from your vault; a local model is not affected."
    render(<SettingRequestCard request={request({ setting: { ...request().setting, note } })} onAnswer={vi.fn()} />)
    expect(screen.getByText(note)).toBeTruthy()
  })

  it("answers with the choice, and sends nothing but the yes or no", async () => {
    const onAnswer = vi.fn().mockResolvedValue(null)
    render(<SettingRequestCard request={request()} onAnswer={onAnswer} />)
    fireEvent.click(screen.getByRole("button", { name: "Decline" }))
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(false))
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith(true))
  })

  it("shows the reason the setting refused and stays waiting", async () => {
    render(<SettingRequestCard request={request()} onAnswer={vi.fn().mockResolvedValue("10 is not valid for history_tokens: a number, 500 or more.")} />)
    fireEvent.click(screen.getByRole("button", { name: "Accept" }))
    expect((await screen.findByRole("alert")).textContent).toContain("not valid")
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy()
  })

  it.each([
    ["accepted", "Changed"],
    ["declined", "Declined"],
    ["replaced", "Replaced by a newer proposal"],
  ] as const)("once %s keeps the change and says %s, with no buttons", (state, line) => {
    render(<SettingRequestCard request={request({ state, setting: { ...request().setting, note: "Careful." } })} onAnswer={vi.fn()} />)
    expect(screen.getByText(line)).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
    expect(screen.queryByText("Careful.")).toBeNull()
    expect(screen.getByLabelText("From automatic to 3000")).toBeTruthy()
  })
})
