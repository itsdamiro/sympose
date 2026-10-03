import * as React from "react"

/**
 * Read mode's stand-in for stylo's own (hidden, see `MarkdownPanel`) formatting toolbar: the note's vault path, split
 * into segments. Only the first folder segment navigates: the content panel can only jump to root-level vault
 * sections today (`onNavigateToRootFolder`), so a deeper segment has nowhere real to send the click yet. The filename
 * is plain text, it is the note already open.
 */
export function NoteBreadcrumb({
  path,
  vaultName,
  onNavigateToRootFolder,
}: {
  path?: string
  /** The vault root's display name, leading the path; `null` or absent drops that segment. */
  vaultName?: string | null
  onNavigateToRootFolder?: (rootPath: string) => void
}) {
  const pathSegments = path ? path.split("/") : []
  const folderSegments = pathSegments.slice(0, -1)
  const fileSegment = pathSegments[pathSegments.length - 1]
  return (
    <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden font-mono text-xs text-fg-muted">
      {vaultName && <span className="shrink-0">{vaultName}</span>}
      {folderSegments.map((segment, i) => (
        <React.Fragment key={i}>
          <span className="shrink-0">/</span>
          {i === 0 ? (
            <button
              type="button"
              onClick={() => onNavigateToRootFolder?.(segment)}
              className="-mx-0.5 shrink-0 rounded px-0.5 transition-colors hover:bg-accent hover:text-foreground"
            >
              {segment}
            </button>
          ) : (
            <span className="shrink-0">{segment}</span>
          )}
        </React.Fragment>
      ))}
      <span className="shrink-0">/</span>
      <span className="truncate text-foreground">{fileSegment}</span>
    </div>
  )
}
