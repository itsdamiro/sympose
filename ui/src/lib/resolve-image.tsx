import type { ReactNode } from "react"
import { imageExists, vaultImageUrl } from "./vault-image-api"

const IMAGE_FILE = /\.(png|jpe?g|webp|gif|svg)$/i
const SIZE_HINT = /^(\d+)(?:x(\d+))?$/
const HAS_SCHEME = /^([a-z][a-z0-9+.-]*:|\/\/)/i

export function isImageRef(target: string): boolean {
  return IMAGE_FILE.test(target)
}

/** `300` is a width in pixels, `300x200` a width and a height (Obsidian's size hint). */
function readSize(hint: string | undefined): { width?: number; height?: number } {
  const match = hint === undefined ? null : SIZE_HINT.exec(hint.trim())
  if (!match) return {}
  const width = Number(match[1])
  const height = match[2] ? Number(match[2]) : undefined
  // A size of 0 would hide the picture: it is read as no size.
  if (!width || height === 0) return {}
  return { width, ...(height ? { height } : {}) }
}

/** The name in a Markdown address: `<my shot.png>` and `my%20shot.png` both name `my shot.png`. */
function addressName(src: string): string {
  const bare = src.trim().replace(/^<(.*)>$/, "$1")
  try {
    return decodeURIComponent(bare)
  } catch {
    return bare
  }
}

/**
 * One image of the vault for both stylo hooks (docs/decisions/085): `![[shot.png|300]]` through `embedSource` and
 * `![alt|300](path)` through `imageSource`. `null` keeps the source as text, which is what a reference with no
 * file behind it gets, and a remote (`http:`, `https:`) or inline (`data:`) source, so opening a note never loads
 * an address of its own. So does a source that is not an image file, which is never asked of the backend.
 */
export async function resolveImage(
  persona: string,
  from: string,
  src: string,
  alt: string,
  hint?: string
): Promise<ReactNode> {
  const path = src.trim()
  if (!isImageRef(path) || HAS_SCHEME.test(path)) return null
  const url = vaultImageUrl(path, from, persona)
  if (!(await imageExists(url))) return null
  const { width, height } = readSize(hint)
  return (
    <img
      src={url}
      alt={alt}
      loading="lazy"
      width={width}
      height={height}
      style={{ maxWidth: "100%", height: "auto", aspectRatio: width && height ? `${width} / ${height}` : undefined }}
    />
  )
}

/** `imageSource(src, alt)`: a size hint written at the end of the alt text is read and taken out of it. */
export function resolveImageSource(persona: string, from: string, srcAddress: string, alt: string): Promise<ReactNode> {
  const src = addressName(srcAddress)
  const at = alt.lastIndexOf("|")
  if (at >= 0 && SIZE_HINT.test(alt.slice(at + 1).trim())) {
    return resolveImage(persona, from, src, alt.slice(0, at), alt.slice(at + 1))
  }
  return resolveImage(persona, from, src, alt)
}
