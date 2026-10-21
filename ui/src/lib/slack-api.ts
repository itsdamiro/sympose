/**
 * Client for `GET /api/personas/{handle}/slack` (docs/decisions/093): whether `sympose slack` has the persona connected right
 * now. Anything that goes wrong is "not connected": the dot is a convenience, and a dot that cannot be checked is not shown.
 */
export async function fetchSlackConnected(handle: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/personas/${encodeURIComponent(handle)}/slack`)
    if (!res.ok) return false
    return ((await res.json()) as { connected?: unknown }).connected === true
  } catch {
    return false
  }
}
