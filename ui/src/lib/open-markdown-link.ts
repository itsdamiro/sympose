const SAFE_LINK_SCHEMES = new Set(["http:", "https:", "mailto:"])

/** Opens a `[text](url)` link a reader clicked, in a new tab. Restricted to absolute http(s)/mailto: links:
 *  what is shown (a note, a chat reply from a model) is not always authored by the current user, so a
 *  `javascript:`/`data:` URI must not get a free ride into `window.open`. A relative path (a link to
 *  another file in the vault) is a silent no-op: resolved against this page it would open a nonexistent
 *  route of this app in a new tab. */
export function openMarkdownLink(href: string): void {
  let url: URL
  try {
    url = new URL(href)
  } catch {
    return
  }
  if (!SAFE_LINK_SCHEMES.has(url.protocol)) return
  window.open(url.href, "_blank", "noopener,noreferrer")
}
