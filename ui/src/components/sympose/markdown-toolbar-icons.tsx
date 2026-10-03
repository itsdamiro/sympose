import { HugeiconsIcon } from "@hugeicons/react"
import {
  CodeIcon,
  FloppyDiskIcon,
  Heading01Icon,
  Heading02Icon,
  Heading03Icon,
  LeftToRightListBulletIcon,
  LeftToRightListNumberIcon,
  LinkIcon,
  ListTodoIcon,
  MathIcon,
  ParagraphIcon,
  QuoteDownIcon,
  RedoIcon,
  Search01Icon,
  SecondBracketIcon,
  SeparatorHorizontalIcon,
  SigmaIcon,
  SourceCodeIcon,
  TableIcon,
  TextBoldIcon,
  TextItalicIcon,
  TextStrikethroughIcon,
  TextUnderlineIcon,
  UndoIcon,
} from "@hugeicons/core-free-icons"

/** Stylo's own glyph for "frontmatter" on its built-in toolbar — literal
 *  `fm` text in `<code>` (`src/toolbar/icons.tsx` in `@damiro/stylo`; the
 *  package also has an unrelated SVG path under the same name used only for
 *  its in-place YAML-block decoration, not the toolbar). Sizing/weight
 *  copied from stylo's own `._toolbarButton_ code` CSS rule so it sits at
 *  the same visual weight as the mono glyphs elsewhere in that toolbar. */
function FrontmatterIcon() {
  return (
    <code aria-hidden="true" className="font-mono text-[13px] font-medium">
      fm
    </code>
  )
}

/** One Hugeicons glyph per stylo built-in — the full `ToolbarCommandId` set,
 *  not just sympose's own curated default, since `<StyloToolbarSettings>`
 *  lets any user add any of them from "Available" (Settings > Markdown
 *  editor). Leaving one out isn't a bug — stylo's `DEFAULT_ICONS` falls back
 *  cleanly — but it renders as a visibly different (stylo's own default)
 *  icon style sitting next to these, which is the inconsistency this map
 *  exists to avoid. */
export const TOOLBAR_ICONS = {
  undo: <HugeiconsIcon icon={UndoIcon} className="size-4" />,
  redo: <HugeiconsIcon icon={RedoIcon} className="size-4" />,
  save: <HugeiconsIcon icon={FloppyDiskIcon} className="size-4" />,
  search: <HugeiconsIcon icon={Search01Icon} className="size-4" />,
  h1: <HugeiconsIcon icon={Heading01Icon} className="size-4" />,
  h2: <HugeiconsIcon icon={Heading02Icon} className="size-4" />,
  h3: <HugeiconsIcon icon={Heading03Icon} className="size-4" />,
  body: <HugeiconsIcon icon={ParagraphIcon} className="size-4" />,
  bold: <HugeiconsIcon icon={TextBoldIcon} className="size-4" />,
  italic: <HugeiconsIcon icon={TextItalicIcon} className="size-4" />,
  strike: <HugeiconsIcon icon={TextStrikethroughIcon} className="size-4" />,
  underline: <HugeiconsIcon icon={TextUnderlineIcon} className="size-4" />,
  code: <HugeiconsIcon icon={CodeIcon} className="size-4" />,
  codeBlock: <HugeiconsIcon icon={SourceCodeIcon} className="size-4" />,
  link: <HugeiconsIcon icon={LinkIcon} className="size-4" />,
  wikilink: <HugeiconsIcon icon={SecondBracketIcon} className="size-4" />,
  quote: <HugeiconsIcon icon={QuoteDownIcon} className="size-4" />,
  bulletList: (
    <HugeiconsIcon icon={LeftToRightListBulletIcon} className="size-4" />
  ),
  orderedList: (
    <HugeiconsIcon icon={LeftToRightListNumberIcon} className="size-4" />
  ),
  task: <HugeiconsIcon icon={ListTodoIcon} className="size-4" />,
  hr: <HugeiconsIcon icon={SeparatorHorizontalIcon} className="size-4" />,
  frontmatter: <FrontmatterIcon />,
  table: <HugeiconsIcon icon={TableIcon} className="size-4" />,
  math: <HugeiconsIcon icon={MathIcon} className="size-4" />,
  mathBlock: <HugeiconsIcon icon={SigmaIcon} className="size-4" />,
} as const
