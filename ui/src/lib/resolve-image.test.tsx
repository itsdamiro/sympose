import type { ReactElement } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { resolveEmbed } from "./resolve-embed"
import { resolveImageSource } from "./resolve-image"

const fetchMock = vi.fn()
const found = () => fetchMock.mockResolvedValue({ ok: true })
const asImg = (node: unknown) => node as ReactElement<Record<string, unknown> & { style: Record<string, unknown> }>

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal("fetch", fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

describe("an image embed", () => {
  it("asks the backend with HEAD, then draws the image from that address", async () => {
    found()
    const img = asImg(await resolveEmbed([], "samantha", "shot.png", "Projects/x/note.md"))
    const url = "/api/vault/image?path=shot.png&from=Projects%2Fx%2Fnote.md&persona=samantha"
    expect(fetchMock).toHaveBeenCalledWith(url, { method: "HEAD" })
    expect(img.type).toBe("img")
    expect(img.props).toMatchObject({ src: url, alt: "shot.png", loading: "lazy" })
  })

  it("reads a width and a width and height after the pipe", async () => {
    found()
    expect(asImg(await resolveEmbed([], "s", "shot.png|100", "n.md")).props).toMatchObject({ width: 100 })
    expect(asImg(await resolveEmbed([], "s", "shot.png|100", "n.md")).props.height).toBeUndefined()
    expect(asImg(await resolveEmbed([], "s", "shot.png|300x200", "n.md")).props).toMatchObject({ width: 300, height: 200 })
  })

  it("has no size when the hint is not a number, or is 0", async () => {
    found()
    for (const hint of ["big", "0", "0x0", "300x0"]) {
      const img = asImg(await resolveEmbed([], "s", `shot.png|${hint}`, "n.md"))
      expect(img.props.width, hint).toBeUndefined()
      expect(img.props.height, hint).toBeUndefined()
    }
  })

  it("keeps the proportions when the column is narrower than the size asked for", async () => {
    found()
    const both = asImg(await resolveEmbed([], "s", "shot.png|300x200", "n.md"))
    expect(both.props.style).toEqual({ maxWidth: "100%", height: "auto", aspectRatio: "300 / 200" })
    const one = asImg(await resolveEmbed([], "s", "shot.png|300", "n.md"))
    expect(one.props.style).toEqual({ maxWidth: "100%", height: "auto", aspectRatio: undefined })
  })

  it("asks for the name as written: a wikilink is not an address, so a % in it is not decoded", async () => {
    found()
    await resolveEmbed([], "s", "a%20b.png", "n.md")
    expect(fetchMock).toHaveBeenCalledWith("/api/vault/image?path=a%2520b.png&from=n.md&persona=s", { method: "HEAD" })
  })

  it("stays literal when no file is found, and when the backend cannot be reached", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false })
    expect(await resolveEmbed([], "s", "gone.png", "n.md")).toBeNull()
    fetchMock.mockRejectedValueOnce(new Error("offline"))
    expect(await resolveEmbed([], "s", "gone.png", "n.md")).toBeNull()
  })

  it("is recognised by its extension in any case, and a note embed is not asked of the image route", async () => {
    found()
    expect(await resolveEmbed([], "s", "Photo.JPEG", "n.md")).not.toBeNull()
    fetchMock.mockClear()
    expect(await resolveEmbed([], "s", "Missing note", "n.md")).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe("an image written as ![alt](path)", () => {
  it("draws a local path", async () => {
    found()
    const img = asImg(await resolveImageSource("samantha", "n.md", "assets/shot.png", "A shot"))
    expect(img.props).toMatchObject({ src: "/api/vault/image?path=assets%2Fshot.png&from=n.md&persona=samantha", alt: "A shot" })
  })

  it("reads a size at the end of the alt text and takes it out of it", async () => {
    found()
    expect(asImg(await resolveImageSource("s", "n.md", "a.png", "A shot|100")).props).toMatchObject({ alt: "A shot", width: 100 })
    expect(asImg(await resolveImageSource("s", "n.md", "a.png", "|300x200")).props).toMatchObject({ alt: "", width: 300, height: 200 })
  })

  it("keeps an alt whose bar is not a size", async () => {
    found()
    expect(asImg(await resolveImageSource("s", "n.md", "a.png", "left|right")).props.alt).toBe("left|right")
  })

  it.each(["https://example.com/a.png", "http://example.com/a.png", "data:image/png;base64,AAAA", "//example.com/a.png", "file:///etc/a.png"])(
    "never loads %s",
    async (src) => {
      found()
      expect(await resolveImageSource("s", "n.md", src, "x")).toBeNull()
      expect(fetchMock).not.toHaveBeenCalled()
    }
  )

  it("never asks the backend about a source that is not an image file", async () => {
    found()
    for (const src of ["readme.md", "Architecture", "#section", "page.html"]) {
      expect(await resolveImageSource("s", "n.md", src, "x"), src).toBeNull()
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("asks for the decoded name of an address with %20 or angle brackets", async () => {
    found()
    await resolveImageSource("s", "n.md", "my%20shot.png", "x")
    await resolveImageSource("s", "n.md", "<my shot.png>", "x")
    const asked = fetchMock.mock.calls.map(([url]) => url as string)
    expect(asked).toEqual(Array(2).fill("/api/vault/image?path=my%20shot.png&from=n.md&persona=s"))
  })

  it("stays literal when no file is found", async () => {
    fetchMock.mockResolvedValue({ ok: false })
    expect(await resolveImageSource("s", "n.md", "gone.png", "x")).toBeNull()
  })
})
