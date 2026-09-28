# 037 — Hiding folders and notes from view in the web app

> **Status: Accepted.** Closes #80. Hiding is a **display preference**, not a privacy boundary: it changes what the web app lists, never what the persona can read or what a cloud model may receive (that is #79 and ADR 031).

## Context

A user wants some folders and notes out of sight in the web app (drafts, private notes, templates) without moving or deleting them. The persona should still be able to read them, as it already reads `Templates/` and the folder definition notes (ADR 033). Two things in the code shape the design:

- `vault_graph.get_vault_tree` and `get_vault_graph` serve both the web API and the engine (the vault map, connections and the health report call the graph). Hiding cannot live inside them, or the persona would lose the notes.
- The web app remembers the note last open (a cookie) and reopens it on load, and a note can be hidden by a folder far above it. Deciding "is this path hidden" in the client as well would give the rule two homes.

## Decision

**What is hidden, and where it is stored.**

- A hidden **folder** hides everything under it. A hidden **note** hides that note. The list is kept **per vault** in the settings file (`hidden_paths`: vault path → vault-relative paths), not in a cookie, so it is the same in every browser and does not outgrow a cookie's 4 KB. The CLI does not read it.
- Three routes: `GET /api/vault/hidden` (the list, and whether folder definition notes are shown), `POST /api/vault/hidden` (hide a path) and `DELETE /api/vault/hidden?path=` (unhide), each idempotent; `PUT /api/vault/hidden/definitions` sets the definition-notes knob.
- A path is stored as given after normalising (`\` to `/`, outer slashes dropped); an empty path, `.` and `..` segments are refused. A stored path that no longer exists is kept and listed, so it can always be unhidden.

**The server marks, the client obeys.** One function decides what is hidden (`vault_hidden.py`), so the web app never holds a second copy of the rule.

- **The tree** (`GET /api/vault/tree`) still returns every node, each with `hidden: "user"` when hidden by the list (a folder's children inherit it) or `hidden: "definition"` for a folder definition note while the knob is off. Neighbour lists (`links`) drop the ids of user-hidden notes. The client prunes both kinds from everything it lists and resolves links and embeds among what is left, and keeps the full tree only to know whether a remembered note may reopen.
- **The graph** (`GET /api/vault/graph`) drops user-hidden notes and every line to them, recomputes the sizes so a hidden neighbour is not counted, and drops a ghost node left with no line. Definition notes stay in the graph: the knob is about the tree only.
- **Search** (`GET /api/vault/search`) still finds hidden notes and marks each hit `hidden: true` (user-hidden only) with `hidden_by`, the entries of the list that hide it (its own path and/or the folders above it). The web app lists such a hit greyed, labelled "Hidden", with an **Unhide** action that removes every entry in `hidden_by`; it cannot be opened. A definition note is found and opened normally.
- **The editor and links.** A user-hidden note is not opened from anywhere the user can reach: not from the tree, Recent or Pinned (pruned), not from search (greyed), not by clicking a `[[link]]` to it (the link stays in the text; it is resolved among the notes the user sees, so the click does nothing, or opens a visible note of the same name), and not as an `![[embed]]` (left literal, resolved the same way). A note hidden while it is open closes at once; unhidden, it is what was open again.
- **A note open when the page loads** that is hidden (the last-open note is remembered) does not reopen.
- **Renaming** still rewrites links inside hidden notes; hiding changes nothing on disk.
- **Entries are exact, case-sensitive paths.** A folder or note renamed or moved outside Sympose leaves its old entry, which keeps showing in the settings list (and would hide a new note created at that path) until it is unhidden; the web app cannot rename a folder, and a hidden note cannot be reached to rename. Two spellings that differ only in case are two entries.
- **Writing.** Hide and unhide run one at a time (the list is read and written back whole), and change only the current vault's entry: other vaults' entries are written back exactly as they were, and a `hidden_paths` setting that is not a mapping (hand-edited) is never overwritten: the change is refused with a 500.

**Not enforced by the server.** `GET /api/vault/note` still returns a hidden note to anything that asks for it. That is what "a display preference" means here, and the persona and CLI never go through the web API. If hiding should ever be a lock, it becomes a different feature with its own ADR.

**Folder definition notes** (`Folder/Folder.md`, ADR 033) are hidden in the tree by default; **Settings > Hidden from view** has a switch to show them (`show_definition_notes`, off by default). The persona reads them either way.

**Settings screen.** A section, **Hidden from view**, says in one line that hiding is for the view only (the persona can still read it), lists every hidden path with an **Unhide** button, and carries the definition-notes switch.

**Menus.** Notes and folders get **Hide from view** in the row menu, the existing one (a `⋯` button and right-click or long-press share one item list, per the context-menu standard).

## Consequences

- Hiding a note does not change what the persona says: it can still ground a reply on it, and a cloud model may still receive it if `cloud_share` allows notes (ADR 031). The setting's own label says so.
- The tree response is slightly larger (a `hidden` field where it applies). Nothing else about it changes for a client that ignores the field.
- A hidden note that a visible note links to is still counted as a link by the health report (`sympose vault --health`); the report is for the owner and reads the vault, not the view.
- Deleting a hidden note sends it to the bin, which lists it by name as any deleted note; restoring it puts it back, still hidden.

## Alternatives rejected

- **Filtering in `vault_graph`.** The engine reads the same functions; the persona would lose the notes.
- **Removing hidden notes from the tree response.** The web app could not tell "hidden" from "missing" for a remembered path, and would need its own copy of the rule for it.
- **Resolving links against the full tree, then refusing a hidden match.** A first match in tree order that happens to be hidden would block a link that has a visible target (`[[Todo]]` with `Archive/Todo.md` hidden and `Work/Todo.md` visible). Resolving among the visible notes is simpler and does the right thing.
- **Doing the filtering in the client from the list.** The rule (a folder hides what is under it, neighbour ids, ghost nodes, definition notes) would exist twice.
- **A cookie for the list.** Per browser, capped near 4 KB, and lost with the cookies (the list is the only way back to a hidden note).
- **Server-side refusal of a hidden note's content.** It would make a preference into a security feature the CLI and persona do not honour, which is worse than an honest label.
- **Hiding definition notes in the graph too.** Its connections are useful there; the clutter is in the tree.

## Not built

- Hiding from the terminal chat, and a "show hidden" toggle in the tree (unhide from the settings list instead).
- Hiding by pattern (a name or a tag).
