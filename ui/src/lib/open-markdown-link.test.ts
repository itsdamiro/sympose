import { afterEach, describe, expect, it, vi } from "vitest"

import { openMarkdownLink } from "./open-markdown-link"

afterEach(() => vi.unstubAllGlobals())

function stubOpen() {
  const open = vi.fn()
  vi.stubGlobal("window", { open, location: { href: "http://localhost:5173/" } })
  return open
}

describe("openMarkdownLink", () => {
  it("opens http, https and mailto links in a new tab without handing over the page", () => {
    const open = stubOpen()
    openMarkdownLink("https://example.com/a?b=1")
    openMarkdownLink("http://example.com")
    openMarkdownLink("mailto:someone@example.com")
    expect(open).toHaveBeenCalledTimes(3)
    expect(open).toHaveBeenCalledWith("https://example.com/a?b=1", "_blank", "noopener,noreferrer")
  })

  it("ignores links that could run code or read a local file", () => {
    const open = stubOpen()
    for (const href of ["javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,<b>x</b>", "file:///etc/passwd", "vbscript:x"]) {
      openMarkdownLink(href)
    }
    expect(open).not.toHaveBeenCalled()
  })

  it("does nothing for a relative link, which would open a route of this app that does not exist", () => {
    const open = stubOpen()
    for (const href of ["Notes/foo.md", "./foo.md", "../foo.md", "/foo", "#heading", ""]) openMarkdownLink(href)
    expect(open).not.toHaveBeenCalled()
  })

  it("does nothing for something that is not a link at all", () => {
    const open = stubOpen()
    openMarkdownLink("http://")
    openMarkdownLink("not a url")
    expect(open).not.toHaveBeenCalled()
  })
})
