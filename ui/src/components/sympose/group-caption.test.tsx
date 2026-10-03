// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { PinIcon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { GroupCaption } from "./group-caption"

afterEach(cleanup)

describe("GroupCaption", () => {
  it("is a small icon and label, indented by what it is given", () => {
    const { container } = render(<GroupCaption icon={PinIcon} label="Pinned" paddingLeft={12} />)
    const caption = container.querySelector('[data-slot="group-caption"]') as HTMLElement
    expect(caption.querySelector("svg")).toBeTruthy()
    expect(screen.getByText("Pinned")).toBeTruthy()
    expect(caption.style.paddingLeft).toBe("12px")
  })

  it("has a hover menu of group actions only when it is given some", () => {
    const { rerender } = render(<GroupCaption icon={PinIcon} label="Pinned" paddingLeft={0} />)
    expect(screen.queryByRole("button", { name: "Pinned group actions" })).toBeNull()
    rerender(<GroupCaption icon={PinIcon} label="Pinned" paddingLeft={0} menuItems={<span>Unpin all</span>} />)
    expect(screen.getByRole("button", { name: "Pinned group actions" })).toBeTruthy()
  })
})
