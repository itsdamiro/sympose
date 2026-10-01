// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react"
import * as React from "react"
import { describe, expect, it } from "vitest"

import { useReadOnlyToggle } from "./use-read-only-toggle"

function setup(initial = false) {
  return renderHook(() => {
    const [readOnly, setReadOnly] = React.useState(initial)
    return { readOnly, ...useReadOnlyToggle(readOnly, setReadOnly) }
  })
}

// An `animationend` whose target is, or sits inside, the element with the given class.
function animationEnd(inside: string | null): React.AnimationEvent {
  const root = document.createElement("div")
  const target = document.createElement("span")
  if (inside) root.className = inside
  root.appendChild(target)
  return { target } as unknown as React.AnimationEvent
}

describe("useReadOnlyToggle", () => {
  it("is idle at first, with no handler to attach", () => {
    const { result } = setup()
    expect(result.current).toMatchObject({ exiting: false, entering: false, readOnly: false, onAnimationEnd: undefined })
  })

  it("holds the current mode while the exit plays, then flips it and enters when the chrome row finishes", () => {
    const { result } = setup(false)
    act(() => result.current.toggle())
    expect(result.current).toMatchObject({ exiting: true, entering: false, readOnly: false })
    act(() => result.current.onAnimationEnd!(animationEnd("sy-note-chrome")))
    expect(result.current).toMatchObject({ exiting: false, entering: true, readOnly: true })
  })

  it("drops the enter state when the chrome row's enter finishes, and the handler with it", () => {
    const { result } = setup(false)
    act(() => result.current.toggle())
    act(() => result.current.onAnimationEnd!(animationEnd("sy-note-chrome")))
    act(() => result.current.onAnimationEnd!(animationEnd("sy-note-chrome")))
    expect(result.current).toMatchObject({ exiting: false, entering: false, readOnly: true, onAnimationEnd: undefined })
  })

  it("ignores an animation that ends somewhere other than the chrome row", () => {
    const { result } = setup(false)
    act(() => result.current.toggle())
    act(() => result.current.onAnimationEnd!(animationEnd(null)))
    expect(result.current).toMatchObject({ exiting: true, readOnly: false })
  })

  it("toggles back the other way", () => {
    const { result } = setup(true)
    act(() => result.current.toggle())
    act(() => result.current.onAnimationEnd!(animationEnd("sy-note-chrome")))
    expect(result.current.readOnly).toBe(false)
  })

  it("commits once when two chrome animations end in the same batch", () => {
    const { result } = setup(false)
    act(() => result.current.toggle())
    const end = result.current.onAnimationEnd!
    act(() => {
      end(animationEnd("sy-note-chrome"))
      end(animationEnd("sy-note-chrome"))
    })
    expect(result.current).toMatchObject({ readOnly: true, entering: true })
  })
})
