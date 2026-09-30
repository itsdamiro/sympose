// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChatMarkdown } from "./chat-markdown"

afterEach(cleanup)

describe("ChatMarkdown", () => {
  it("renders Markdown as formatted text, not as source", async () => {
    const { container } = render(<ChatMarkdown>{"# Title\n\nSome **bold** text.\n\n- one\n- two"}</ChatMarkdown>)
    await waitFor(() => expect(container.querySelector("h1")).not.toBeNull())
    expect(container.querySelector("strong")?.textContent).toBe("bold")
    expect(container.querySelectorAll("li")).toHaveLength(2)
    expect(container.textContent).not.toContain("**")
  })

  it("opens the note a wikilink names when it is clicked", async () => {
    const onWikiLinkClick = vi.fn()
    render(<ChatMarkdown onWikiLinkClick={onWikiLinkClick}>{"See [[Atlas]] for the database."}</ChatMarkdown>)
    fireEvent.click(await screen.findByText("Atlas"))
    expect(onWikiLinkClick).toHaveBeenCalledWith("Atlas")
  })

  it("does not run or render markup a model wrote into its reply", async () => {
    const hostile = 'Hi <script>window.__pwned = 1</script><img src="x" onerror="window.__pwned = 2"><a href="javascript:window.__pwned=3">go</a>\n\n[click](javascript:window.__pwned=4)'
    const { container } = render(<ChatMarkdown>{hostile}</ChatMarkdown>)
    await waitFor(() => expect(container.textContent).toContain("Hi"))
    await new Promise((r) => setTimeout(r, 50))
    expect(container.querySelector("script")).toBeNull()
    expect(container.querySelector("img[onerror]")).toBeNull()
    for (const a of container.querySelectorAll("a")) fireEvent.click(a)
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined()
  })
})
