// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { UserIcon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { TopBar } from "./top-bar"

afterEach(cleanup)

describe("TopBar: the persona button", () => {
  it("shows the active persona's icon in her accent, as the desktop menu's account row does", () => {
    render(<TopBar account={{ name: "Samantha", icon: UserIcon, accent: "rgb(1, 2, 3)" }} />)
    const button = screen.getByRole("button", { name: "Samantha" })
    expect(button.querySelector("svg")).not.toBeNull()
    expect(button.textContent).toBe("")
    expect((button.querySelector('[data-slot="avatar-fallback"]') as HTMLElement | null)?.style.background).toContain("rgb(1, 2, 3)")
  })

  it("falls back to the name's first letter without an icon", () => {
    render(<TopBar account={{ name: "Samantha" }} />)
    expect(screen.getByRole("button", { name: "Samantha" }).textContent).toBe("S")
  })
})
