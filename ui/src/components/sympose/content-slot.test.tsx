// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import * as React from "react"
import { afterEach, describe, expect, it } from "vitest"

import { ContentSlot } from "./content-slot"

afterEach(cleanup)

// jsdom has no `AnimationEvent`, so React listens for the prefixed name there.
const animationEnd = (el: Element) => fireEvent(el, new Event("webkitAnimationEnd", { bubbles: true }))

const slot = (key: string, body: React.ReactNode, direction: "forward" | "back" = "forward") => (
  <ContentSlot swapKey={key} direction={direction}>
    {body}
  </ContentSlot>
)
const wrapper = () => screen.getByTestId("a-body")?.closest("div.flex") as HTMLElement

describe("ContentSlot", () => {
  it("shows the first body as it is, with no slide", () => {
    render(slot("A", <p data-testid="a-body">A</p>))
    expect(wrapper().className).not.toContain("animate-in")
    expect(wrapper().className).not.toContain("animate-out")
    expect(screen.getByTestId("a-body").textContent).toBe("A")
  })

  it("lays the body out as a column with a gap, and mounts a fresh element for each section so its slide restarts", () => {
    const { rerender } = render(slot("A", <p data-testid="a-body">A</p>))
    expect(wrapper().className).toContain("flex flex-col gap-4")
    const first = wrapper()
    rerender(slot("B", <p data-testid="b-body">B</p>))
    animationEnd(wrapper())
    const second = screen.getByTestId("b-body").closest("div.flex") as HTMLElement
    expect(second).not.toBe(first)
    expect(second.className).toContain("flex flex-col gap-4")
  })

  it("follows the body while the section stays the same", () => {
    const { rerender } = render(slot("A", <p data-testid="a-body">one</p>))
    rerender(slot("A", <p data-testid="a-body">two</p>))
    expect(screen.getByTestId("a-body").textContent).toBe("two")
    expect(wrapper().className).not.toContain("animate")
  })

  it("keeps the old body sliding out, inert, until its animation ends, then slides the new one in", () => {
    const { rerender } = render(slot("A", <p data-testid="a-body">A</p>))
    rerender(slot("B", <p data-testid="b-body">B</p>))
    expect(screen.getByTestId("a-body")).toBeTruthy()
    expect(screen.queryByTestId("b-body")).toBeNull()
    const outgoing = wrapper()
    expect(outgoing.className).toContain("animate-out")
    expect(outgoing.className).toContain("pointer-events-none")
    animationEnd(outgoing)
    expect(screen.queryByTestId("a-body")).toBeNull()
    expect(screen.getByTestId("b-body")).toBeTruthy()
    expect(screen.getByTestId("b-body").closest("div.flex")!.className).toContain("animate-in")
  })

  it("slides out to the left going forward, and to the right going back", () => {
    const fwd = render(slot("A", <p data-testid="a-body">A</p>))
    fwd.rerender(slot("B", <p>B</p>, "forward"))
    expect(wrapper().className).toContain("slide-out-to-left")
    cleanup()
    const back = render(slot("A", <p data-testid="a-body">A</p>))
    back.rerender(slot("B", <p>B</p>, "back"))
    expect(wrapper().className).toContain("slide-out-to-right")
  })

  it("slides in from the right going forward, and from the left going back", () => {
    for (const [direction, from] of [["forward", "slide-in-from-right"], ["back", "slide-in-from-left"]] as const) {
      const { rerender } = render(slot("A", <p data-testid="a-body">A</p>, direction))
      rerender(slot("B", <p data-testid="b-body">B</p>, direction))
      animationEnd(wrapper())
      expect(screen.getByTestId("b-body").closest("div.flex")!.className).toContain(from)
      cleanup()
    }
  })

  it("does not swap when an animation inside the old body ends", () => {
    const { rerender } = render(slot("A", <p data-testid="a-body">A</p>))
    rerender(slot("B", <p data-testid="b-body">B</p>))
    animationEnd(screen.getByTestId("a-body"))
    expect(screen.getByTestId("a-body")).toBeTruthy()
    expect(screen.queryByTestId("b-body")).toBeNull()
  })

  it("does nothing on an animation that ends while it is not sliding out", () => {
    render(slot("A", <p data-testid="a-body">A</p>))
    animationEnd(wrapper())
    expect(screen.getByTestId("a-body")).toBeTruthy()
  })
})
