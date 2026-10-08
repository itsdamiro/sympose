// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import type { ChatTurn } from "./chat-types"
import type { ConfirmationRequest } from "./confirmations-api"
import { requestIdsOf, useConfirmations } from "./use-confirmations"

const fetchConfirmations = vi.fn()
const answerConfirmation = vi.fn()
vi.mock("./confirmations-api", () => ({
  fetchConfirmations: (...a: unknown[]) => fetchConfirmations(...a),
  answerConfirmation: (...a: unknown[]) => answerConfirmation(...a),
}))

const request = (id: string, state: ConfirmationRequest["state"] = "waiting"): ConfirmationRequest => ({
  id, kind: "persona", state, handle: "ada", reason: null, created_at: "t", folder_choices: ["Work"], edit_modes: [{ id: "manual", summary: "m" }],
  draft: { name: "Ada", title: "", soul: "s", icon: "book", accent: "#fff", accent_dark: "#000", edit_mode: "manual", folders: ["Work"] },
})
const reply = (id: string, ...requests: string[]): ChatTurn => ({
  id, role: "persona", body: "x", sent: { notes: [], lookups: requests.map((r) => ({ tool: "propose_persona", saved: true, request: r })) },
})

beforeEach(() => {
  fetchConfirmations.mockReset()
  answerConfirmation.mockReset()
})

describe("requestIdsOf", () => {
  it("lists the requests the replies refer to, and only those of propose_persona", () => {
    const turns: ChatTurn[] = [
      reply("a", "r1"),
      { id: "b", role: "persona", body: "x", sent: { notes: [], lookups: [{ tool: "search_notes", found: 2 }, { tool: "propose_persona", saved: false }] } },
      { id: "c", role: "user", body: "hi" },
      reply("d", "r2", "r3"),
    ]
    expect(requestIdsOf(turns)).toEqual(["r1", "r2", "r3"])
  })
})

describe("useConfirmations", () => {
  it("reads nothing while no reply refers to a request", () => {
    renderHook(() => useConfirmations("samantha", "s1", [{ id: "u", role: "user", body: "hi" }]))
    expect(fetchConfirmations).not.toHaveBeenCalled()
  })

  it("reads the conversation's requests when a reply refers to one, and again when a new one appears", async () => {
    fetchConfirmations.mockResolvedValue([request("r1")])
    const { result, rerender } = renderHook((p: { turns: ChatTurn[] }) => useConfirmations("samantha", "s1", p.turns), {
      initialProps: { turns: [reply("a", "r1")] },
    })
    await waitFor(() => expect(result.current.byId.r1?.state).toBe("waiting"))
    expect(fetchConfirmations).toHaveBeenCalledWith("samantha", "s1")

    fetchConfirmations.mockResolvedValue([request("r1", "replaced"), request("r2")])
    rerender({ turns: [reply("a", "r1"), reply("b", "r2")] })
    await waitFor(() => expect(result.current.byId.r1?.state).toBe("replaced"))
    expect(result.current.byId.r2.state).toBe("waiting")
  })

  it("keeps the answered request and reads the roster again once a persona is made", async () => {
    fetchConfirmations.mockResolvedValue([request("r1")])
    answerConfirmation.mockResolvedValue({ ok: true, request: request("r1", "accepted") })
    const onAccepted = vi.fn()
    const { result } = renderHook(() => useConfirmations("samantha", "s1", [reply("a", "r1")], onAccepted))
    await waitFor(() => expect(result.current.byId.r1).toBeTruthy())

    let error: string | null = "x"
    await act(async () => {
      error = await result.current.answer("r1", true, ["Work"])
    })

    expect(error).toBeNull()
    expect(answerConfirmation).toHaveBeenCalledWith("samantha", "r1", true, ["Work"], null)
    expect(result.current.byId.r1.state).toBe("accepted")
    expect(onAccepted).toHaveBeenCalledTimes(1)
  })

  it("does not read the roster again for a decline or an outdated request", async () => {
    fetchConfirmations.mockResolvedValue([request("r1")])
    const onAccepted = vi.fn()
    const { result } = renderHook(() => useConfirmations("samantha", "s1", [reply("a", "r1")], onAccepted))
    await waitFor(() => expect(result.current.byId.r1).toBeTruthy())

    answerConfirmation.mockResolvedValue({ ok: true, request: request("r1", "declined") })
    await act(async () => void (await result.current.answer("r1", false, null)))
    answerConfirmation.mockResolvedValue({ ok: true, request: request("r1", "outdated") })
    await act(async () => void (await result.current.answer("r1", true, null)))

    expect(onAccepted).not.toHaveBeenCalled()
  })

  it("hands back the reason when the answer is refused and keeps the card as it was", async () => {
    fetchConfirmations.mockResolvedValue([request("r1")])
    answerConfirmation.mockResolvedValue({ ok: false, error: "Choose at least one folder the new persona may read." })
    const { result } = renderHook(() => useConfirmations("samantha", "s1", [reply("a", "r1")]))
    await waitFor(() => expect(result.current.byId.r1).toBeTruthy())

    let error: string | null = null
    await act(async () => {
      error = await result.current.answer("r1", true, [])
    })

    expect(error).toBe("Choose at least one folder the new persona may read.")
    expect(result.current.byId.r1.state).toBe("waiting")
  })
})
