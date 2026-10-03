// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { Note01Icon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it } from "vitest"

import { ResultText } from "./result-text"
import { SearchResultRow } from "./search-result-row"

afterEach(cleanup)

describe("ResultText", () => {
  it("is an icon and a title that wraps to two lines, over a muted detail line indented under the title", () => {
    const { container } = render(<ResultText icon={Note01Icon} title="Atlas" detail="line 3" />)
    const block = container.querySelector('[data-slot="result-text"]') as HTMLElement
    expect(block.querySelector("svg")).toBeTruthy()
    expect(screen.getByText("Atlas").className).toContain("line-clamp-2")
    expect(screen.getByText("Atlas").parentElement?.className).toContain("text-entity")
    expect(screen.getByText("line 3").className).toContain("pl-5")
  })

  it("leaves the detail line out when there is none, and shows what trails the title", () => {
    const { container } = render(<ResultText icon={Note01Icon} title="Atlas" trailing={<em>replying…</em>} />)
    expect(container.querySelectorAll("span.pl-5")).toHaveLength(0)
    expect(screen.getByText("replying…")).toBeTruthy()
  })

  it("marks an emphasized row by the weight of its title", () => {
    render(<ResultText icon={Note01Icon} title="Atlas" emphasized />)
    expect(screen.getByText("Atlas").parentElement?.className).toContain("font-medium")
  })

  it("is what a search result is made of, so the lists cannot drift apart", () => {
    const { container } = render(<SearchResultRow label="Atlas" detail="line 3" onSelect={() => {}} />)
    expect(container.querySelector('[data-slot="result-text"]')).toBeTruthy()
  })
})
