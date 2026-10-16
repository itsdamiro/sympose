"""What a `[[wikilink]]` looks like, shared by the readers of links (the health check, the file-name rules) and the
writers that rewrite them, so neither side imports the other."""

import re

# Structurally reserved in `[[wikilink]]` syntax (`]` closes the link, `|`
# starts an alias, `#` starts a heading anchor) — a new stem containing any
# of these would silently corrupt every backlink rewritten to point at it.
WIKILINK_UNSAFE_CHARS = frozenset("[]|#")

WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\r\n]+?)\]\]")
