// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ModelPicker } from "./model-picker"

afterEach(cleanup)

const state = (over: Record<string, unknown> = {}) => ({
  models: [
    { id: "ollama_chat/gemma2:9b", label: "Gemma2:9b — local, default", short: "Gemma2:9b", cloud: false },
    { id: "gemini/gemini-flash-latest", label: "Gemini Flash — cloud", short: "Gemini Flash", cloud: true },
  ],
  current: "ollama_chat/gemma2:9b",
  currentCloud: false,
  own: null,
  fallback: "ollama_chat/gemma2:9b",
  fallbackCloud: false,
  ...over,
})

function open() {
  const trigger = screen.getByRole("button", { name: /^Model:/ })
  fireEvent.mouseDown(trigger)
  fireEvent.mouseUp(trigger)
  fireEvent.click(trigger)
}

describe("ModelPicker", () => {
  it("shows the model in use on the chip, and whether it is on the device or the cloud", () => {
    const { rerender } = render(<ModelPicker state={state()} onChoose={vi.fn()} />)
    const chip = screen.getByRole("button", { name: "Model: Gemma2:9b. Change" })
    expect(chip.getAttribute("data-tier")).toBe("local")
    rerender(<ModelPicker state={state({ current: "gemini/gemini-flash-latest", currentCloud: true })} onChoose={vi.fn()} />)
    expect(screen.getByRole("button", { name: "Model: Gemini Flash. Change" }).getAttribute("data-tier")).toBe("cloud")
  })

  it("names a model the list does not hold by the last part of its id, and uses the state's cloud flag", () => {
    render(<ModelPicker state={state({ current: "openai/some-unlisted", currentCloud: true })} onChoose={vi.fn()} />)
    const chip = screen.getByRole("button", { name: "Model: some-unlisted. Change" })
    expect(chip.getAttribute("data-tier")).toBe("cloud")
  })

  it("shows nothing while the models are not known", () => {
    const { container } = render(<ModelPicker state={null} onChoose={vi.fn()} />)
    expect(container.textContent).toBe("")
  })

  it("lists the models and chooses one that is not the current", async () => {
    const onChoose = vi.fn()
    render(<ModelPicker state={state()} onChoose={onChoose} />)
    open()
    fireEvent.click(await screen.findByRole("menuitem", { name: /Gemini Flash — cloud/ }))
    expect(onChoose).toHaveBeenCalledWith("gemini/gemini-flash-latest")
  })

  it("does nothing when the model already in use is chosen again", async () => {
    const onChoose = vi.fn()
    render(<ModelPicker state={state()} onChoose={onChoose} />)
    open()
    fireEvent.click(await screen.findByRole("menuitem", { name: /Gemma2:9b — local/ }))
    expect(onChoose).not.toHaveBeenCalled()
  })

  it("offers to bring the cloud notice back only for a cloud model whose notice is closed", async () => {
    const cloud = state({ current: "gemini/gemini-flash-latest", currentCloud: true })
    const onShowNotice = vi.fn()
    const { unmount } = render(<ModelPicker state={cloud} onChoose={vi.fn()} noticeClosed onShowNotice={onShowNotice} />)
    open()
    fireEvent.click(await screen.findByRole("menuitem", { name: /What this model may receive/ }))
    expect(onShowNotice).toHaveBeenCalledTimes(1)
    unmount()
    for (const props of [{ noticeClosed: false }, { noticeClosed: true, state: state() }]) {
      const { unmount: again } = render(<ModelPicker state={props.state ?? cloud} onChoose={vi.fn()} noticeClosed={props.noticeClosed} onShowNotice={onShowNotice} />)
      open()
      await screen.findByRole("menuitem", { name: /Gemini Flash/ })
      expect(screen.queryByRole("menuitem", { name: /What this model may receive/ })).toBeNull()
      again()
    }
  })

  it("offers to clear the persona's own model only while it has one, and clears with null", async () => {
    const onChoose = vi.fn()
    const { unmount } = render(<ModelPicker state={state()} onChoose={onChoose} />)
    open()
    await screen.findByRole("menuitem", { name: /Gemini Flash/ })
    expect(screen.queryByRole("menuitem", { name: /Use the default/ })).toBeNull()
    unmount()
    render(<ModelPicker state={state({ own: "gemini/gemini-flash-latest", current: "gemini/gemini-flash-latest" })} onChoose={onChoose} />)
    open()
    fireEvent.click(await screen.findByRole("menuitem", { name: /Use the default \(ollama_chat\/gemma2:9b\)/ }))
    expect(onChoose).toHaveBeenCalledWith(null)
  })
})
