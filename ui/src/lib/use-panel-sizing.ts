import * as React from "react"

import { useAncestorWidth } from "@/lib/use-ancestor-width"
import { useFillWidth } from "@/lib/use-fill-width"
import { eighthWidth, useResizable } from "@/lib/use-resizable"
import { useTransientFlag } from "@/lib/use-transient-flag"

/**
 * The editor panel's width: dragged between an eighth of the shell row and two-thirds of the split area (a cookie
 * remembers it under `storageKey`), or, when `fill` is on, the space actually free to its right.
 */
export function usePanelSizing(wrapRef: React.RefObject<HTMLDivElement | null>, fill: boolean, storageKey?: string) {
  const stageW = useAncestorWidth(wrapRef, 1)
  const shellW = useAncestorWidth(wrapRef, 2)
  // Space actually free to the editor's right — what it grows to when filling,
  // remeasured every frame while a panel slides.
  const availW = useFillWidth(wrapRef)
  // Arm the max-width transition only while `fill` is actually flipping. The
  // rest of the time max-width follows the live measurement instantly, so the
  // editor tracks the content panel sliding out instead of lagging behind it.
  const fillToggling = useTransientFlag(fill)

  // Minimum is an eighth of the shell row — `eighthWidth` is the same rule
  // `<ContentPanel>` uses — so neither working panel can be dragged narrower
  // than the other. Otherwise free up to two-thirds of the split area,
  // defaulting to half; the `|| fallback` covers the first render before
  // anything has been measured.
  const min = React.useCallback(() => eighthWidth(shellW) || 180, [shellW])
  const max = React.useCallback(
    () => Math.round((stageW * 2) / 3) || 9999,
    [stageW]
  )
  const defaultSize = React.useCallback(
    () => Math.round(stageW / 2) || 480,
    [stageW]
  )

  const { size, dragging, handleProps } = useResizable({
    min,
    max,
    defaultSize,
    storageKey,
  })
  return { size, dragging, handleProps, availW, fillToggling }
}
