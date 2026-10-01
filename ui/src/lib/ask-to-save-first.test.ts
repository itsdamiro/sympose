import { afterEach, describe, expect, it, vi } from "vitest"

const confirmed = vi.hoisted(() => ({ requests: [] as { message: string; confirmLabel?: string; cancelLabel?: string; onConfirm: () => Promise<void> }[] }))
vi.mock("@/lib/confirm-store", () => ({ confirm: (req: (typeof confirmed.requests)[number]) => confirmed.requests.push(req) }))

import { askToSaveFirst } from "./ask-to-save-first"
import { setUnsavedGuard } from "./unsaved-guard"

afterEach(() => {
  setUnsavedGuard(null)
  confirmed.requests.length = 0
})

const guard = (dirty: boolean, saved = true) => ({ name: () => "Plan", isDirty: () => dirty, save: vi.fn().mockResolvedValue(saved), retarget: vi.fn() })

describe("askToSaveFirst", () => {
  it("asks nothing when no note is open or the open note has no unsaved changes", () => {
    const proceed = vi.fn()
    expect(askToSaveFirst(proceed)).toBe(false)
    setUnsavedGuard(guard(false))
    expect(askToSaveFirst(proceed)).toBe(false)
    expect(confirmed.requests).toHaveLength(0)
    expect(proceed).not.toHaveBeenCalled() // the caller carries on itself when it was not asked
  })

  it("asks, naming the note, and does nothing until the answer", () => {
    const g = guard(true)
    setUnsavedGuard(g)
    const proceed = vi.fn()
    expect(askToSaveFirst(proceed)).toBe(true)
    expect(confirmed.requests[0]).toMatchObject({ message: 'Save your changes to "Plan" first?', confirmLabel: "Save and switch", cancelLabel: "Stay" })
    expect(g.save).not.toHaveBeenCalled()
    expect(proceed).not.toHaveBeenCalled()
  })

  it("saves first and only then lets the switch go ahead", async () => {
    const g = guard(true)
    setUnsavedGuard(g)
    const proceed = vi.fn()
    askToSaveFirst(proceed)
    await confirmed.requests[0].onConfirm()
    expect(g.save).toHaveBeenCalledTimes(1)
    expect(proceed).toHaveBeenCalledTimes(1)
  })

  it("does not switch when the save failed", async () => {
    setUnsavedGuard(guard(true, false))
    const proceed = vi.fn()
    askToSaveFirst(proceed)
    await confirmed.requests[0].onConfirm()
    expect(proceed).not.toHaveBeenCalled()
  })
})
