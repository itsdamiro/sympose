// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { useChatSession } from "./use-chat-session"

const chatState = { turns: [] as { role: string }[], sending: false, sessionId: "s1", context: { used: 1 }, notice: vi.fn() }
const models = { state: { current: "gemma" } as { current: string } | null, choose: vi.fn() }
const useChat = vi.fn()
const useModels = vi.fn()
const useStatusPhrases = vi.fn()
const useContextMeter = vi.fn()
const useModelSwitch = vi.fn()
const useSharing = vi.fn()
const useCloudNotice = vi.fn()
vi.mock("./use-chat", () => ({ useChat: (...a: unknown[]) => useChat(...a) }))
vi.mock("./use-models", () => ({ useModels: (...a: unknown[]) => useModels(...a) }))
vi.mock("./use-status-phrases", () => ({ useStatusPhrases: (...a: unknown[]) => useStatusPhrases(...a) }))
vi.mock("./use-context-meter", () => ({ useContextMeter: (...a: unknown[]) => useContextMeter(...a) }))
vi.mock("./use-model-switch", () => ({ useModelSwitch: (...a: unknown[]) => useModelSwitch(...a) }))
vi.mock("./use-sharing", () => ({ useSharing: (...a: unknown[]) => useSharing(...a) }))
vi.mock("./use-cloud-notice", () => ({ useCloudNotice: (...a: unknown[]) => useCloudNotice(...a) }))

beforeEach(() => {
  vi.resetAllMocks()
  chatState.turns = []
  chatState.sending = false
  models.state = { current: "gemma" }
  useChat.mockReturnValue(chatState)
  useModels.mockReturnValue(models)
  useStatusPhrases.mockReturnValue(["a phrase"])
  useContextMeter.mockReturnValue({ figure: 1 })
  useModelSwitch.mockReturnValue(() => {})
  useSharing.mockReturnValue({ state: { cloud: true }, setShared: vi.fn() })
  useCloudNotice.mockReturnValue({ open: true })
})

describe("useChatSession", () => {
  it("keys the conversation, the models and the sharing on the active persona", () => {
    renderHook(() => useChatSession("grace"))
    expect(useChat).toHaveBeenCalledWith("grace")
    expect(useModels).toHaveBeenCalledWith("grace")
    expect(useStatusPhrases).toHaveBeenCalledWith("grace", false)
    expect(useSharing).toHaveBeenCalledWith("grace", "gemma")
  })

  it("hands the busy line whether a reply is being waited for", () => {
    chatState.sending = true
    renderHook(() => useChatSession("grace"))
    expect(useStatusPhrases).toHaveBeenCalledWith("grace", true)
  })

  it("says the conversation has no replies until the persona has answered once", () => {
    chatState.turns = [{ role: "user" }]
    renderHook(() => useChatSession("grace"))
    expect(useContextMeter.mock.calls[0][0].hasReplies).toBe(false)
    expect(useModelSwitch.mock.calls[0][0].hasReplies).toBe(false)
    chatState.turns = [{ role: "user" }, { role: "persona" }]
    renderHook(() => useChatSession("grace"))
    expect(useContextMeter.mock.calls[1][0].hasReplies).toBe(true)
    expect(useModelSwitch.mock.calls[1][0].hasReplies).toBe(true)
  })

  it("gives the meter the real figure, the session, the persona and the model in use", () => {
    renderHook(() => useChatSession("grace"))
    expect(useContextMeter).toHaveBeenCalledWith({
      persona: "grace",
      sessionId: "s1",
      model: "gemma",
      real: chatState.context,
      hasReplies: false,
    })
  })

  it("lets the model switch pick through the models hook and say so in the chat", () => {
    renderHook(() => useChatSession("grace"))
    expect(useModelSwitch).toHaveBeenCalledWith({
      state: models.state,
      choose: models.choose,
      hasReplies: false,
      notice: chatState.notice,
    })
  })

  it("derives the cloud notice from what the sharing state says about the model", () => {
    renderHook(() => useChatSession("grace"))
    expect(useCloudNotice).toHaveBeenCalledWith(true)
  })

  it("has no model in use until the models are known", () => {
    models.state = null
    const { result } = renderHook(() => useChatSession("grace"))
    expect(result.current.modelInUse).toBeUndefined()
    expect(useSharing).toHaveBeenCalledWith("grace", undefined)
    expect(useContextMeter.mock.calls[0][0].model).toBeUndefined()
  })

  it("returns each piece for the shell", () => {
    const { result } = renderHook(() => useChatSession("grace"))
    expect(result.current.chat).toBe(chatState)
    expect(result.current.models).toBe(models)
    expect(result.current.modelInUse).toBe("gemma")
    expect(result.current.statusPhrases).toEqual(["a phrase"])
    expect(result.current.contextFigure).toEqual({ figure: 1 })
    expect(result.current.sharingState).toEqual({ cloud: true })
    expect(result.current.cloudNotice).toEqual({ open: true })
  })
})
