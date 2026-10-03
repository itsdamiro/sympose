import { extractInlineTags } from "@/lib/extract-inline-tags"
import { parseFrontmatter, serializeFrontmatter } from "@/lib/frontmatter"

export type NoteLoadState =
  | { status: "empty" }
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; content: string }

/** How long typing has to pause before an autosave fires (ms). */
export const AUTOSAVE_DELAY = 1500

/**
 * Reassemble the full note the way the vault stores it.
 *
 * - No frontmatter block in the original → the body is the whole document.
 * - Block present but the card never touched it → splice the body back onto the
 *   file's *exact* original prefix (`originalPrefix`), so an unrelated body edit
 *   never reformats the YAML (quote style, indentation, blank lines, CRLFs all
 *   survive).
 * - Card edited a field → re-serialise from its parsed model. Normalising the
 *   block is unavoidable and expected here.
 */
export function joinNote(
  frontmatter: string | null,
  body: string,
  originalPrefix: string | null,
  frontmatterEdited: boolean
): string {
  if (frontmatter === null) return body
  if (!frontmatterEdited && originalPrefix !== null) return originalPrefix + body
  return `---\n${frontmatter.replace(/\s+$/, "")}\n---\n\n${body}`
}

/**
 * Additive-only sync on save: any `#tag` found in the body that isn't
 * already in the frontmatter `tags:` list (case-insensitively) gets
 * appended, lowercased — the reverse never happens, so deleting a `#tag`
 * from the body leaves frontmatter untouched. `null`/unparseable frontmatter
 * (no `---` block, or something `parseFrontmatter` can't round-trip) is left
 * alone, same fallback `<FrontmatterCard>` itself uses.
 */
export function syncInlineTags(
  frontmatter: string | null,
  body: string
): { frontmatter: string | null; changed: boolean } {
  if (frontmatter === null) return { frontmatter, changed: false }
  const data = parseFrontmatter(frontmatter)
  if (data === null) return { frontmatter, changed: false }

  const existing = Array.isArray(data.tags)
    ? data.tags
    : data.tags != null
      ? [data.tags]
      : []
  const existingLower = new Set(existing.map((t) => String(t).toLowerCase()))
  const additions = extractInlineTags(body).filter((t) => !existingLower.has(t))
  if (additions.length === 0) return { frontmatter, changed: false }

  return {
    frontmatter: serializeFrontmatter({ ...data, tags: [...existing, ...additions] }),
    changed: true,
  }
}
