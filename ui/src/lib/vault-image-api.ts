/** The address of one vault image (`GET /api/vault/image`): `path` as written in the note, `from` the open note's path. */
export function vaultImageUrl(path: string, from: string, persona: string): string {
  return `/api/vault/image?path=${encodeURIComponent(path)}&from=${encodeURIComponent(from)}&persona=${encodeURIComponent(persona)}`
}

/** Whether the backend finds an image for `url`: a reference that matches no file stays text. A backend that
 *  cannot be reached is the same answer. */
export async function imageExists(url: string): Promise<boolean> {
  try {
    return (await fetch(url, { method: "HEAD" })).ok
  } catch {
    return false
  }
}
