// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { BrainIcon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { PersonaHeader } from "./persona-header"

afterEach(cleanup)

describe("PersonaHeader", () => {
  it("shows the name and the title, and tints the band and the avatar in her colour", () => {
    const { container } = render(
      <PersonaHeader name="Ada" title="A tutor" icon={BrainIcon} accent="rgb(1, 2, 3)" accentDark="rgb(4, 5, 6)" />
    )
    expect(screen.getByRole("heading", { name: "Ada" })).toBeTruthy()
    expect(screen.getByText("A tutor")).toBeTruthy()
    const root = container.firstElementChild as HTMLElement
    expect(root.style.getPropertyValue("--persona-accent")).toBe("rgb(1, 2, 3)")
    expect(root.style.getPropertyValue("--persona-accent-dark")).toBe("rgb(4, 5, 6)")
    expect((container.querySelector("[data-slot='avatar-fallback']") as HTMLElement).style.background).toContain("rgb(1, 2, 3)")
  })

  it("takes the band's size and the name row's own classes from its caller", () => {
    const { container } = render(
      <PersonaHeader name="Ada" title="" icon={BrainIcon} accent="red" accentDark="blue" bandClass="h-12 rounded-none" className="px-4" />
    )
    const band = container.querySelector("[aria-hidden]") as HTMLElement
    expect(band.className).toContain("h-12")
    expect(band.className).not.toContain("h-28")
    expect(screen.getByRole("heading", { name: "Ada" }).closest(".px-4")).toBeTruthy()
  })
})
