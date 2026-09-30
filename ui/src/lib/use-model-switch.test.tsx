// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))

import type { ModelsState } from "./models-api"
import { useModelSwitch } from "./use-model-switch"

afterEach(() => {
  cleanup()
  confirmMock.mockReset()
})

const LOCAL = { id: "ollama_chat/gemma2:9b", label: "Gemma2:9b — local, default", short: "Gemma2:9b", cloud: false }
const CLOUD = { id: "gemini/gemini-flash-latest", label: "Gemini Flash — cloud", short: "Gemini Flash", cloud: true }
const CLOUD2 = { id: "openai/gpt-4o-mini", label: "GPT-4o mini — cloud", short: "GPT-4o mini", cloud: true }

const state = (over: Partial<ModelsState> = {}): ModelsState => ({
  models: [LOCAL, CLOUD, CLOUD2],
  current: LOCAL.id,
  currentCloud: false,
  own: null,
  fallback: LOCAL.id,
  fallbackCloud: false,
  ...over,
})

function setup(s: ModelsState | null, hasReplies: boolean, saved = true) {
  const choose = vi.fn().mockResolvedValue(saved)
  const notice = vi.fn()
  const { result } = renderHook(() => useModelSwitch({ state: s, choose, hasReplies, notice }))
  return { choose, notice, switchTo: (m: string | null) => act(async () => result.current(m)) }
}

describe("useModelSwitch", () => {
  it("saves a switch to a cloud model in an empty conversation without asking, and says so", async () => {
    const { choose, notice, switchTo } = setup(state(), false)
    await switchTo(CLOUD.id)
    expect(confirmMock).not.toHaveBeenCalled()
    expect(choose).toHaveBeenCalledWith(CLOUD.id)
    expect(notice).toHaveBeenCalledWith("confirmation", "Switched model to Gemini Flash — cloud.")
  })

  it("asks first when a conversation with replies goes from a local model to a cloud one, and saves only on accept", async () => {
    const { choose, notice, switchTo } = setup(state(), true)
    await switchTo(CLOUD.id)
    expect(choose).not.toHaveBeenCalled()
    const request = confirmMock.mock.calls[0][0]
    expect(request.message).toBe("Switch to Gemini Flash — cloud?")
    expect(request.description).toContain("sent to a cloud model as history")
    expect(request.tone).toBe("default")
    expect(request.permanent).toBeUndefined() // the app's own confirmation, as the user's preference has it
    await act(async () => request.onConfirm())
    expect(choose).toHaveBeenCalledWith(CLOUD.id)
    expect(notice).toHaveBeenCalledTimes(1)
  })

  it("does not switch or say anything if the confirmation is never accepted", async () => {
    const { choose, notice, switchTo } = setup(state(), true)
    await switchTo(CLOUD.id)
    expect(choose).not.toHaveBeenCalled()
    expect(notice).not.toHaveBeenCalled()
  })

  it("asks nothing for a switch between cloud models, or to a local model", async () => {
    const cloudNow = state({ current: CLOUD.id, currentCloud: true })
    const a = setup(cloudNow, true)
    await a.switchTo(CLOUD2.id)
    const b = setup(cloudNow, true)
    await b.switchTo(LOCAL.id)
    expect(confirmMock).not.toHaveBeenCalled()
    expect(a.choose).toHaveBeenCalledWith(CLOUD2.id)
    expect(b.choose).toHaveBeenCalledWith(LOCAL.id)
  })

  it("asks nothing for a switch between two local models, even in a conversation with replies", async () => {
    const other = { id: "ollama_chat/qwen3:8b", label: "Qwen3:8b — local", short: "Qwen3:8b", cloud: false }
    const { choose, switchTo } = setup(state({ models: [LOCAL, other, CLOUD] }), true)
    await switchTo(other.id)
    expect(confirmMock).not.toHaveBeenCalled()
    expect(choose).toHaveBeenCalledWith(other.id)
  })

  it("says nothing leaves the computer when the model chosen is local", async () => {
    const { notice, switchTo } = setup(state({ current: CLOUD.id, currentCloud: true }), true)
    await switchTo(LOCAL.id)
    expect(notice).toHaveBeenCalledWith("confirmation", "Switched model to Gemma2:9b — local, default. Nothing from your vault leaves your computer.")
  })

  it("treats clearing the persona's model as a switch to the default, asking when that default is a cloud one", async () => {
    const { choose, switchTo } = setup(state({ own: LOCAL.id, fallback: CLOUD.id, fallbackCloud: true }), true)
    await switchTo(null)
    expect(confirmMock).toHaveBeenCalledTimes(1)
    expect(confirmMock.mock.calls[0][0].message).toBe("Switch to Gemini Flash — cloud?")
    expect(choose).not.toHaveBeenCalled()
    const calm = setup(state({ own: CLOUD.id, current: CLOUD.id, currentCloud: true }), true)
    await calm.switchTo(null)
    expect(calm.choose).toHaveBeenCalledWith(null)
  })

  it("names a default the list does not hold by its id, and treats an unlisted model as cloud", async () => {
    const { notice, switchTo } = setup(state({ current: CLOUD.id, currentCloud: true, own: CLOUD.id, fallback: "ollama_chat/custom", fallbackCloud: false }), false)
    await switchTo(null)
    expect(notice).toHaveBeenCalledWith("confirmation", "Switched model to ollama_chat/custom. Nothing from your vault leaves your computer.")
    const ask = setup(state(), true)
    await ask.switchTo("unlisted/model")
    expect(confirmMock).toHaveBeenCalled()
  })

  it("says nothing when the save fails (the failure is already shown) and does nothing without state", async () => {
    const failed = setup(state(), false, false)
    await failed.switchTo(CLOUD.id)
    expect(failed.notice).not.toHaveBeenCalled()
    const none = setup(null, false)
    await none.switchTo(CLOUD.id)
    expect(none.choose).not.toHaveBeenCalled()
  })
})
