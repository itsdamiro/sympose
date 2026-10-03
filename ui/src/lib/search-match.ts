/**
 * The match the toolbar search uses on Settings and the conversations (docs/decisions/065): every word of the query
 * is somewhere in the text, case ignored. An empty query matches everything.
 */
export function matchesQuery(text: string, query: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const haystack = text.toLowerCase()
  return words.every((word) => haystack.includes(word))
}
