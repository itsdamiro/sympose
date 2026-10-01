import * as React from "react"

import { cn } from "@/lib/utils"
import {
  slideEnterClassName,
  slideExitClassName,
  useSlideSwap,
  type SlideDirection,
} from "@/lib/use-slide-swap"

/**
 * The content panel's body, sliding sideways when the section shown changes:
 * keyed on the section (`swapKey`), back and forward aware (`direction` is set
 * alongside whatever triggered the change), and sequential rather than a
 * crossfade: the outgoing section finishes its own slide-out before the incoming
 * one starts sliding in (see `useSlideSwap`).
 *
 * The slide-out ends on this element's own `animationend` only: an animation
 * inside the body bubbles up here too and must not commit the swap early.
 */
export function ContentSlot({
  swapKey,
  direction,
  children,
}: {
  swapKey: string
  direction: SlideDirection
  children: React.ReactNode
}) {
  const {
    displayKey,
    displayPayload,
    exitDirection,
    enterDirection,
    onExitComplete,
  } = useSlideSwap(swapKey, children, direction)
  return (
    <div
      key={displayKey}
      className={cn(
        "flex flex-col gap-4",
        exitDirection
          ? slideExitClassName(exitDirection)
          : enterDirection && slideEnterClassName(enterDirection)
      )}
      onAnimationEnd={
        exitDirection
          ? (e) => {
              if (e.target === e.currentTarget) onExitComplete()
            }
          : undefined
      }
    >
      {displayPayload}
    </div>
  )
}
