/**
 * A list of vault paths kept in one cookie (docs/decisions/051): the pins, the
 * recents and the expanded folders. A path may hold a comma, so the list is a
 * JSON array; a value that does not start with `[` is the older comma-joined
 * form and is still read, so an upgrade loses nothing.
 */

// A browser drops a cookie past about 4 KB (name and value). Measured on the
// encoded value, with room left for the name and attributes.
export const MAX_COOKIE_VALUE = 3500

export function readList(raw: string | null): string[] {
  if (!raw) return []
  if (raw.startsWith("[")) {
    try {
      const parsed: unknown = JSON.parse(raw)
      return Array.isArray(parsed)
        ? parsed.filter((p): p is string => typeof p === "string" && p !== "")
        : []
    } catch {
      return []
    }
  }
  return raw.split(",").filter(Boolean)
}

/**
 * The JSON for `list`, trimmed so its encoded form fits a cookie: the oldest
 * entries go first, so a save never fails silently. `newestFirst` says which
 * end is the oldest — the end for a recents list, the front for insertion
 * order (pins, expanded folders).
 */
export function writeList(list: string[], newestFirst = false): string {
  let kept = list
  while (
    kept.length > 0 &&
    encodeURIComponent(JSON.stringify(kept)).length > MAX_COOKIE_VALUE
  ) {
    kept = newestFirst ? kept.slice(0, -1) : kept.slice(1)
  }
  return JSON.stringify(kept)
}

/** `list` with `oldPath` replaced by `newPath` — a renamed or moved note keeps
 *  its pin and its place in the recents. Order is kept; a list already holding
 *  `newPath` drops the duplicate. */
export function remapPath(
  list: string[],
  oldPath: string,
  newPath: string
): string[] {
  if (!list.includes(oldPath)) return list
  const mapped = list.map((p) => (p === oldPath ? newPath : p))
  return mapped.filter((p, i) => mapped.indexOf(p) === i)
}

/** `list` with the folder `oldFolder` renamed to `newFolder`: the folder's own path and every path under it follow
 *  (docs/decisions/073). `People and Pets/` and `Other/People/` are not under `People/`. Order is kept; the same list
 *  comes back when nothing is under the folder. */
export function remapPrefix(
  list: string[],
  oldFolder: string,
  newFolder: string
): string[] {
  const prefix = `${oldFolder}/`
  if (!list.some((p) => p === oldFolder || p.startsWith(prefix))) return list
  const mapped = list.map((p) =>
    p === oldFolder || p.startsWith(prefix) ? newFolder + p.slice(oldFolder.length) : p
  )
  return mapped.filter((p, i) => mapped.indexOf(p) === i)
}

