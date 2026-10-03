// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { LivePersona } from "@/lib/personas"
import type { PersonaFileInfo } from "@/lib/persona-files-api"
import { PersonaCard } from "./persona-card"

afterEach(cleanup)

const personas = [{ handle: "samantha", name: "Samantha", title: "Your companion", model: "ollama_chat/gemma2:9b" }] as LivePersona[]
const files: PersonaFileInfo[] = [
  { name: "soul.md", label: "Soul", description: "How she talks.", exists: true, local: false, pending: false },
  { name: "profile.md", label: "Profile", description: "What she knows about you.", exists: true, local: false, pending: false },
]

describe("PersonaCard", () => {
  it("shows one FILES chip beside the model chip, the same height, in place of the Soul and Memory buttons", () => {
    const { container } = render(<PersonaCard personas={personas} active="samantha" files={files} onOpenFile={() => {}} />)
    const model = container.querySelector('[data-slot="model-chip"]') as HTMLElement
    const chip = screen.getByRole("button", { name: "Persona files" })
    expect(chip.className).toContain("h-5")
    expect(model.className).toContain("h-5")
    expect(screen.queryByRole("button", { name: "Soul" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Memory" })).toBeNull()
  })

  it("opens a file from the chip's list", async () => {
    const onOpenFile = vi.fn()
    render(<PersonaCard personas={personas} active="samantha" files={files} onOpenFile={onOpenFile} />)
    const chip = screen.getByRole("button", { name: "Persona files" })
    fireEvent.mouseDown(chip)
    fireEvent.mouseUp(chip)
    fireEvent.click(chip)
    fireEvent.click(await screen.findByText("Profile"))
    expect(onOpenFile).toHaveBeenCalledWith("profile.md")
  })

  it("shows the model picker given to it, the chat's own, in place of the plain chip", () => {
    const { container } = render(
      <PersonaCard personas={personas} active="samantha" modelSlot={<button>pick a model</button>} />
    )
    expect(screen.getByRole("button", { name: "pick a model" })).toBeTruthy()
    expect(container.querySelector('[data-slot="model-chip"]')).toBeNull()
  })

  it("shows the cloud notice under the model row when it is given one", () => {
    render(<PersonaCard personas={personas} active="samantha" notice={<div>may receive</div>} />)
    expect(screen.getByText("may receive")).toBeTruthy()
  })
})
