import { Stylo } from "@damiro/stylo"

import { cn } from "@/lib/utils"
import { openMarkdownLink } from "@/lib/open-markdown-link"

const noEdit = () => {}

interface ChatMarkdownProps {
  children: string
  /** A `[[wikilink]]` in the reply was clicked; the target is the bare name. */
  onWikiLinkClick?: (target: string) => void
  className?: string
}

/**
 * A persona's reply as rendered Markdown, through stylo's read-only preview: the same renderer the editor's
 * read mode uses, so a reply looks like a note. Headings, lists, code, tables and `[[wikilinks]]` come out as
 * they do there; a link is opened only when it is http(s) or mailto (`openMarkdownLink`), and a wikilink
 * opens the note it names when the reader can see it. Never editable, and nothing here writes anywhere.
 */
function ChatMarkdown({ children, onWikiLinkClick, className }: ChatMarkdownProps) {
  return (
    <div data-slot="chat-markdown" className={cn("sy-chat-markdown", className)}>
      <Stylo
        value={children}
        onChange={noEdit}
        mode="preview"
        toolbar={false}
        readOnly
        softBreaks
        onWikiLinkClick={onWikiLinkClick}
        onLinkClick={openMarkdownLink}
      />
    </div>
  )
}

export { ChatMarkdown }
