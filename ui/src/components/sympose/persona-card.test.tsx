// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { LivePersona } from "@/lib/personas"
import { PersonaCard } from "./persona-card"

afterEach(cleanup)

const personas = [{ handle: "samantha", name: "Samantha", title: "Your companion", model: "ollama_chat/gemma2:9b" }] as LivePersona[]

describe("PersonaCard", () => {
  it("shows Soul and Memory as chips in capitals, the height of the model chip beside them", () => {
    const { container } = render(<PersonaCard personas={personas} active="samantha" />)
    const model = container.querySelector('[data-slot="model-chip"]') as HTMLElement
    for (const name of ["Soul", "Memory"]) {
      const chip = screen.getByRole("button", { name })
      expect(chip.className).toContain("uppercase")
      expect(chip.className).toContain("h-5") // the model chip's height
      expect(chip.className).toContain("bg-chip") // and its surface
      expect(model.className).toContain("h-5")
      expect(chip.hasAttribute("disabled")).toBe(true) // still not built: coming soon
    }
  })
})
