// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ fetchSessions: vi.fn(), updateSession: vi.fn(), deleteSession: vi.fn() }))
vi.mock("@/lib/sessions-api", () => api)
const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn() }))
vi.mock("@/lib/confirm-store", () => ({ confirm: confirmMock }))
vi.mock("@/lib/notify", () => ({ notify: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))

import { useSessionList } from "./use-session-list"

const row = (id: string, extra: Record<string, unknown> = {}) => ({
  id,
  title: `t-${id}`,
  turns: 2,
  created_at: null,
  updated_at: null,
  pinned_at: null,
  replying: false,
  ...extra,
})

const chat = (extra: Record<string, unknown> = {}) => ({
  sessionId: "a" as string | undefined,
  marks: {} as Record<string, { replying: boolean; unread: boolean }>,
  listVersion: 0,
  openConversation: vi.fn().mockResolvedValue(true),
  newConversation: vi.fn().mockResolvedValue(undefined),
  forgetConversation: vi.fn().mockResolvedValue(undefined),
  ...extra,
})

beforeEach(() => {
  api.fetchSessions.mockResolvedValue([row("a"), row("b")])
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe("useSessionList", () => {
  it("lists the backend's rows with the one on screen, the replying and the unread added from the chat", async () => {
    const c = chat({ marks: { b: { replying: true, unread: false }, a: { replying: false, unread: true } } })
    const { result } = renderHook(() => useSessionList("samantha", c))
    await waitFor(() => expect(result.current.sessions).toHaveLength(2))
    expect(result.current.sessions.map((s) => [s.id, s.current, s.replying, s.unread])).toEqual([
      ["a", true, false, true],
      ["b", false, true, false],
    ])
  })

  it("reads the list again when the chat says something changed", async () => {
    const { rerender } = renderHook((props) => useSessionList("samantha", props), { initialProps: chat() })
    await waitFor(() => expect(api.fetchSessions).toHaveBeenCalledTimes(1))
    rerender(chat({ listVersion: 1 }))
    await waitFor(() => expect(api.fetchSessions).toHaveBeenCalledTimes(2))
  })

  it("shows none of another persona's rows while its own load", async () => {
    let arrive: (v: unknown) => void = () => {}
    const { result, rerender } = renderHook(({ p }) => useSessionList(p, chat()), { initialProps: { p: "samantha" } })
    await waitFor(() => expect(result.current.sessions).toHaveLength(2))
    api.fetchSessions.mockReturnValue(new Promise((r) => (arrive = r)))
    rerender({ p: "grace" })
    expect(result.current.sessions).toEqual([])
    await act(async () => arrive([row("z")]))
    expect(result.current.sessions.map((s) => s.id)).toEqual(["z"])
  })

  it("renames and pins through the backend and reads the list again", async () => {
    api.updateSession.mockResolvedValue({ ok: true, value: row("a") })
    const { result } = renderHook(() => useSessionList("samantha", chat()))
    await waitFor(() => expect(result.current.sessions).toHaveLength(2))
    await act(async () => void (await result.current.rename("a", "Movies")))
    expect(api.updateSession).toHaveBeenCalledWith("samantha", "a", { title: "Movies" })
    await act(async () => void (await result.current.pin("b", true)))
    expect(api.updateSession).toHaveBeenLastCalledWith("samantha", "b", { pinned: true })
    expect(api.fetchSessions).toHaveBeenCalledTimes(3)
  })

  it("says why a rename was refused and does not read the list again", async () => {
    api.updateSession.mockResolvedValue({ ok: false, error: "A title is one line of 1 to 80 characters." })
    const { result } = renderHook(() => useSessionList("samantha", chat()))
    await waitFor(() => expect(result.current.sessions).toHaveLength(2))
    let done = true
    await act(async () => void (done = await result.current.rename("a", "x")))
    expect(done).toBe(false)
    expect(api.fetchSessions).toHaveBeenCalledTimes(1)
    const { notify } = await import("@/lib/notify")
    expect(notify.error).toHaveBeenCalledWith("A title is one line of 1 to 80 characters.")
  })

  it("asks before a delete, and on yes deletes, drops it from the chat, and tells the bin", async () => {
    api.deleteSession.mockResolvedValue({ ok: true, value: undefined })
    const c = chat()
    const { result } = renderHook(() => useSessionList("samantha", c))
    await waitFor(() => expect(result.current.sessions).toHaveLength(2))
    act(() => result.current.remove(result.current.sessions[1]))
    expect(api.deleteSession).not.toHaveBeenCalled()
    const bin = result.current.binVersion
    await act(async () => {
      await confirmMock.mock.calls[0][0].onConfirm()
    })
    expect(api.deleteSession).toHaveBeenCalledWith("samantha", "b")
    expect(c.forgetConversation).toHaveBeenCalledWith("b")
    expect(result.current.binVersion).toBe(bin + 1)
  })

  it("keeps the conversation in the chat when the backend refuses the delete", async () => {
    api.deleteSession.mockResolvedValue({ ok: false, error: "A reply is being written in that conversation. Stop it first." })
    const c = chat()
    const { result } = renderHook(() => useSessionList("samantha", c))
    await waitFor(() => expect(result.current.sessions).toHaveLength(2))
    act(() => result.current.remove(result.current.sessions[0]))
    await act(async () => {
      await confirmMock.mock.calls[0][0].onConfirm()
    })
    expect(c.forgetConversation).not.toHaveBeenCalled()
    const { notify } = await import("@/lib/notify")
    expect(notify.error).toHaveBeenCalledWith("A reply is being written in that conversation. Stop it first.")
  })

  it("opens a conversation through the chat and says so when it cannot", async () => {
    const c = chat({ openConversation: vi.fn().mockResolvedValue(false) })
    const { result } = renderHook(() => useSessionList("samantha", c))
    await act(async () => result.current.open("b"))
    expect(c.openConversation).toHaveBeenCalledWith("b")
    const { notify } = await import("@/lib/notify")
    expect(notify.error).toHaveBeenCalledWith("Couldn't open that conversation")
  })
})
