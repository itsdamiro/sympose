import { describe, expect, it } from "vitest"

import * as chatData from "./chat-mock-data"

describe("chat sample data", () => {
  it("ships no canned persona replies", () => {
    // A made-up answer about the vault would read as a real, grounded one (zero-hallucination rule).
    expect(Object.keys(chatData)).toEqual([])
  })
})
