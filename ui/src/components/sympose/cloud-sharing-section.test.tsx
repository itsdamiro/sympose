// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { CloudSharingRows } from "./cloud-sharing-section"

afterEach(cleanup)

const state = (over: Record<string, unknown> = {}) => ({
  model: "gemini/gemini-flash-latest",
  cloud: true,
  categories: [
    { name: "notes", description: "passages of your notes", shared: false },
    { name: "recaps", description: "recaps of earlier conversations", shared: true },
  ],
  ...over,
})

const setup = (s: ReturnType<typeof state> | null, noticeOpen = true) => {
  const onChange = vi.fn()
  const onNoticeOpenChange = vi.fn()
  render(<CloudSharingRows state={s} onChange={onChange} noticeOpen={noticeOpen} onNoticeOpenChange={onNoticeOpenChange} />)
  return { onChange, onNoticeOpenChange }
}

describe("CloudSharingRows", () => {
  it("lists every category with what it is and its state", () => {
    setup(state())
    expect(screen.getByText("passages of your notes")).toBeTruthy()
    const notes = screen.getByRole("radiogroup", { name: "Share notes with cloud models" })
    expect(notes.querySelector('[aria-checked="true"]')?.textContent).toBe("Off")
    const recaps = screen.getByRole("radiogroup", { name: "Share recaps with cloud models" })
    expect(recaps.querySelector('[aria-checked="true"]')?.textContent).toBe("On")
  })

  it("draws a row of the page's own directly under the category it is named for", () => {
    render(<CloudSharingRows state={state()} onChange={vi.fn()} noticeOpen onNoticeOpenChange={vi.fn()} after={{ recaps: <p>after recaps</p>, nowhere: <p>never drawn</p> }} />)
    const note = screen.getByText("after recaps")
    expect(note.previousElementSibling?.textContent).toBe("recaps of earlier conversations")
    expect(screen.queryByText("never drawn")).toBeNull()
  })

  it("switches a category from the other side, whatever the model in use", () => {
    const { onChange } = setup(state({ cloud: false, model: "ollama_chat/gemma2:9b" }))
    fireEvent.click(screen.getByRole("radio", { name: "On", checked: false }))
    expect(onChange).toHaveBeenCalledWith("notes", true)
    fireEvent.click(screen.getAllByRole("radio", { name: "Off", checked: false })[0])
    expect(onChange).toHaveBeenLastCalledWith("recaps", false)
  })

  it("shows the notice switch in the state the notice is in", () => {
    setup(state(), true)
    const group = screen.getByRole("radiogroup", { name: "Notice above the message box" })
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("Shown")
    cleanup()
    setup(state(), false)
    expect(screen.getByRole("radiogroup", { name: "Notice above the message box" }).querySelector('[aria-checked="true"]')?.textContent).toBe("Hidden")
  })

  it("shows and hides the notice, and says what the model in use does with it", () => {
    const { onNoticeOpenChange } = setup(state(), true)
    fireEvent.click(screen.getByRole("radio", { name: "Hidden" }))
    expect(onNoticeOpenChange).toHaveBeenCalledWith(false)
    expect(screen.getByText(/is a cloud model, so the notice is shown while it is on/)).toBeTruthy()
    cleanup()
    const closed = setup(state(), false)
    fireEvent.click(screen.getByRole("radio", { name: "Shown" }))
    expect(closed.onNoticeOpenChange).toHaveBeenCalledWith(true)
  })

  it("says nothing leaves the computer for a local model", () => {
    setup(state({ cloud: false, model: "ollama_chat/gemma2:9b" }))
    expect(screen.getByText(/is on your computer, so nothing leaves it/)).toBeTruthy()
  })

  it("says when the categories could not be loaded, and offers no switch", () => {
    setup(null)
    expect(screen.getByText(/Couldn't load these/)).toBeTruthy()
    expect(screen.queryByRole("radiogroup")).toBeNull()
  })
})
