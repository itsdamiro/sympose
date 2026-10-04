/**
 * Find a quoted passage in a note again (docs/decisions/070). The same rule as the backend's
 * `sympose/passage_finder.py`, because the editor works on its own text, which can be ahead of the file on disk:
 * a proposal or a comment remembers the passage it is about and a little text on each side, never a position, and
 * `locate` says whether the passage is there once, not at all (someone rewrote those words), or more than once with
 * the surrounding text unable to tell which. It never guesses between candidates and never matches a passage that
 * is not there word for word. Keep the two in step: `passage-finder.test.ts` mirrors `tests/test_passage_finder.py`.
 */

export type Located = { status: "one"; start: number; end: number } | { status: "none" } | { status: "many" }

/** How much text on each side the backend keeps with a passage; only used to tell apart repeats of it. */
export const CONTEXT_CHARS = 40

/** The text just before `start` and just after `end`, each at most `size` characters. */
export function captureContext(text: string, start: number, end: number, size = CONTEXT_CHARS): [string, string] {
  return [text.slice(Math.max(0, start - size), start), text.slice(end, end + size)]
}

function agreeingBefore(text: string, at: number, before: string): number {
  let n = 0
  while (n < before.length && n < at && text[at - 1 - n] === before[before.length - 1 - n]) n++
  return n
}

function agreeingAfter(text: string, at: number, after: string): number {
  let n = 0
  while (n < after.length && at + n < text.length && text[at + n] === after[n]) n++
  return n
}

/** Where `quote` is in `text`, using `before` and `after` only when it occurs more than once. */
export function locate(text: string, quote: string, before = "", after = ""): Located {
  if (!quote) return { status: "none" }
  const starts: number[] = []
  for (let at = text.indexOf(quote); at !== -1; at = text.indexOf(quote, at + 1)) starts.push(at) // overlaps count
  if (starts.length === 0) return { status: "none" }
  if (starts.length === 1) return { status: "one", start: starts[0], end: starts[0] + quote.length }
  const fit = starts.map((at) => agreeingBefore(text, at, before) + agreeingAfter(text, at + quote.length, after))
  const best = Math.max(...fit)
  const winners = starts.filter((_, i) => fit[i] === best)
  if (winners.length === 1 && best > 0) return { status: "one", start: winners[0], end: winners[0] + quote.length }
  return { status: "many" }
}
