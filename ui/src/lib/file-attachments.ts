/**
 * Files attached to a message by dropping or pasting them into the message box (docs/decisions/089, `media`). Nothing is
 * shown beside the box: a file is a marker in the text itself, `[attached: report.pdf]`, which the user can move or delete
 * like any words. Only a file whose marker is still in the message when it is sent goes with it, so deleting the marker
 * is how a file is taken back. The bytes are read when the message is sent and are never kept in the browser or on disk.
 */

/** The endings the server reads (`sympose/engine/media.py`, `EXTENSIONS`; a test keeps the two lists the same). */
export const FILE_EXTENSIONS = [
  ".pdf",
  ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif",
  ".mp3", ".wav", ".aac", ".ogg", ".flac", ".aiff", ".m4a",
  ".mp4", ".mov", ".webm", ".mpeg", ".mpg", ".avi", ".wmv", ".3gp",
] as const

/** The most files, and the most bytes together, one message carries (`media.MAX_FILES` and `media.MAX_BYTES`). */
export const MAX_FILES = 3
export const MAX_BYTES = 50 * 1024 * 1024

/** A file waiting for the message that names it. */
export interface PendingFile {
  /** The name its marker carries, made different from the others' when two files were named alike. */
  name: string
  file: File
}

const extensionOf = (name: string) => {
  const dot = name.lastIndexOf(".")
  return dot < 0 ? "" : name.slice(dot).toLowerCase()
}

/** The marker a file leaves in the text. */
export const marker = (name: string) => `[attached: ${name}]`

/** The name to show for a file: its own, or a numbered one when `taken` already has it. */
export function freeName(name: string, taken: string[]): string {
  if (!taken.includes(name)) return name
  const dot = name.lastIndexOf(".")
  const stem = dot < 0 ? name : name.slice(0, dot)
  const end = dot < 0 ? "" : name.slice(dot)
  for (let n = 2; ; n++) {
    const next = `${stem} (${n})${end}`
    if (!taken.includes(next)) return next
  }
}

export type Taken = { ok: true; added: PendingFile[] } | { ok: false; error: string }

/** The files to add to those already waiting, or the reason none can be: a kind that is not read, too many, too large. */
export function take(offered: File[], waiting: PendingFile[]): Taken {
  const added: PendingFile[] = []
  let bytes = waiting.reduce((sum, p) => sum + p.file.size, 0)
  for (const file of offered) {
    if (!(FILE_EXTENSIONS as readonly string[]).includes(extensionOf(file.name))) {
      return { ok: false, error: `Can't attach ${file.name}: Sympose reads PDFs, images, sounds and videos.` }
    }
    if (file.size === 0) return { ok: false, error: `Can't attach ${file.name}: it is empty.` }
    if (waiting.length + added.length >= MAX_FILES) return { ok: false, error: `At most ${MAX_FILES} files can go with one message.` }
    bytes += file.size
    if (bytes > MAX_BYTES) {
      return { ok: false, error: `Can't attach ${file.name}: the files together are over ${MAX_BYTES / (1024 * 1024)} MB.` }
    }
    added.push({ name: freeName(file.name, [...waiting, ...added].map((p) => p.name)), file })
  }
  return { ok: true, added }
}

/** `text` with the markers of `added` put in at `caret` (or at its end), each on a space of its own. */
export function withMarkers(text: string, added: PendingFile[], caret: number | null): string {
  const at = caret == null || caret > text.length ? text.length : Math.max(0, caret)
  const put = added.map((p) => marker(p.name)).join(" ")
  const before = text.slice(0, at)
  const after = text.slice(at)
  return `${before}${before && !/\s$/.test(before) ? " " : ""}${put}${after && !/^\s/.test(after) ? " " : ""}${after}`
}

/** The waiting files whose marker is still in `text`. */
export function named(text: string, waiting: PendingFile[]): PendingFile[] {
  return waiting.filter((p) => text.includes(marker(p.name)))
}

/** A file's bytes as base64, for the request. */
export async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ""
  for (let at = 0; at < bytes.length; at += 0x8000) binary += String.fromCharCode(...bytes.subarray(at, at + 0x8000))
  return btoa(binary)
}
