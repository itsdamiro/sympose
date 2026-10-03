// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { PersonaFileInfo } from "@/lib/persona-files-api"
import { PersonaFilesMenu } from "./persona-files-menu"

afterEach(cleanup)

const file = (name: string, label: string, over: Partial<PersonaFileInfo> = {}): PersonaFileInfo => ({
  name, label, description: `About ${label}`, exists: true, local: false, pending: false, ...over,
})
const FILES = [file("soul.md", "Soul"), file("profile.md", "Profile", { pending: true }), file("context.md", "Context"), file("decisions.md", "Decisions")]

/** A Base UI menu opens from a pointer sequence, not a bare click. */
const openMenu = () => {
  const trigger = screen.getByRole("button", { name: "Persona files" })
  fireEvent.mouseDown(trigger)
  fireEvent.mouseUp(trigger)
  fireEvent.click(trigger)
}

describe("PersonaFilesMenu", () => {
  it("is one chip in capitals, the size of the model chip's, that opens a list", () => {
    render(<PersonaFilesMenu files={FILES} onOpen={() => {}} />)
    const chip = screen.getByRole("button", { name: "Persona files" })
    expect(chip.textContent).toContain("Files")
    for (const token of ["h-5", "bg-chip", "uppercase", "tracking-wide"]) expect(chip.className).toContain(token)
  })

  it("lists the four files with what each is, and opens the one chosen", async () => {
    const onOpen = vi.fn()
    render(<PersonaFilesMenu files={FILES} onOpen={onOpen} />)
    openMenu()
    for (const label of ["Soul", "Profile", "Context", "Decisions"]) expect(await screen.findByText(label)).toBeTruthy()
    expect(screen.getByText("About Context")).toBeTruthy()
    fireEvent.click(screen.getByText("Context"))
    expect(onOpen).toHaveBeenCalledWith("context.md")
  })

  it("marks a file whose rewrite is waiting for review", async () => {
    render(<PersonaFilesMenu files={FILES} onOpen={() => {}} />)
    openMenu()
    await screen.findByText("Profile")
    expect(screen.getAllByLabelText("A rewrite is waiting for review")).toHaveLength(1)
  })

  it("is not offered until the files are known", () => {
    render(<PersonaFilesMenu files={[]} onOpen={() => {}} />)
    expect(screen.getByRole("button", { name: "Persona files" })).toHaveProperty("disabled", true)
  })

  it("carries an amber mark on the chip itself when something is waiting, so it shows without opening", () => {
    const { container } = render(<PersonaFilesMenu files={FILES} onOpen={() => {}} />)
    expect(container.querySelector('[data-slot="persona-files-pending"]')).toBeTruthy()
    cleanup()
    const { container: calm } = render(<PersonaFilesMenu files={[file("soul.md", "Soul")]} onOpen={() => {}} />)
    expect(calm.querySelector('[data-slot="persona-files-pending"]')).toBeNull()
  })
})
