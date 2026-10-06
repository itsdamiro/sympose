// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"

import type { EditModeInfo } from "@/lib/edit-mode-api"
import { PersonaEditMenu } from "./persona-edit-menu"

afterEach(cleanup)

const MODES = (["plan", "manual", "accept", "auto"] as const).map((id) => ({ id, summary: `about ${id}` }))
const info = (over: Partial<EditModeInfo> = {}): EditModeInfo => ({ mode: "manual", source: "persona", modes: MODES, notes: { accept: null, auto: null }, model: "m", ...over })
const open = () => {
  const trigger = screen.getByRole("button", { name: "What this persona may do to your notes" })
  fireEvent.mouseDown(trigger)
  fireEvent.mouseUp(trigger)
  fireEvent.click(trigger)
}

describe("PersonaEditMenu", () => {
  it("is not available until the mode is known", () => {
    render(<PersonaEditMenu info={null} onChoose={() => {}} />)
    expect((screen.getByRole("button", { name: "What this persona may do to your notes" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("reads the current mode, and marks it as a default when she follows the Settings page's", () => {
    render(<PersonaEditMenu info={info({ mode: "accept" })} onChoose={() => {}} />)
    expect(screen.getByRole("button", { name: "What this persona may do to your notes" }).textContent).toBe("Accept edits")
    cleanup()
    render(<PersonaEditMenu info={info({ mode: "auto", source: "global" })} onChoose={() => {}} />)
    expect(screen.getByRole("button", { name: "What this persona may do to your notes" }).textContent).toBe("Auto (default)")
  })

  it("lists the four modes with a line each and the current one chosen", () => {
    render(<PersonaEditMenu info={info({ mode: "accept" })} onChoose={() => {}} />)
    open()
    const items = screen.getAllByRole("menuitemradio")
    expect(items.map((i) => i.textContent)).toEqual(["Planabout plan", "Manualabout manual", "Accept editsabout accept", "Autoabout auto"])
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["false", "false", "true", "false"])
  })

  it("says the mode chosen", () => {
    const onChoose = vi.fn()
    render(<PersonaEditMenu info={info()} onChoose={onChoose} />)
    open()
    fireEvent.click(screen.getByRole("menuitemradio", { name: /^Auto/ }))
    expect(onChoose).toHaveBeenCalledWith("auto")
  })

  it("offers the default only when she has a mode of her own, and clearing says null", () => {
    const onChoose = vi.fn()
    render(<PersonaEditMenu info={info({ source: "global" })} onChoose={onChoose} />)
    open()
    expect(screen.queryByRole("menuitem", { name: "Use the default" })).toBeNull()
    cleanup()
    render(<PersonaEditMenu info={info({ source: "persona" })} onChoose={onChoose} />)
    open()
    fireEvent.click(screen.getByRole("menuitem", { name: "Use the default" }))
    expect(onChoose).toHaveBeenCalledWith(null)
  })
})
