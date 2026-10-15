---
type: decision
status: accepted
date: 2026-10-14
projects: [sympose]
concepts: [Vault upkeep]
amends: [034, 064]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/consent]
---

# 084 — `sympose vault --fix` walks the repairs one at a time, and `--health` goes back to read-only

> **Summary.** `sympose vault --fix` is one interactive walk over every repair the report can offer (a title that is not the file name, a link whose folder no longer matches, a folder definition with no icon): each is shown, applied only on a yes, and the report is asked again after each one. `--health` only reports again, as ADR 034 first said. It costs a new check for links with a stale folder, and a new place a note can change from the terminal.

## Context

ADR 034 documented `--fix` and left it unbuilt: an interactive walk, one note at a time, never in bulk, its first fix the title rename, "only after the rename layer has been measured on a scratch copy of a vault" (62 renames on the measured vault, each rewriting links elsewhere). Its 2026-10-01 amendment gave `--fix` the stale folder-qualified links of #101, and the rename and move path itself was fixed on 2026-10-14. ADR 064 made `--health` ask about a folder's missing icon, the one write the report had, which left two places in the terminal that can write a note.

Facts about the code:
- The graph resolves a link by its last segment, so `[[Projects/Idea]]` to a note that moved to `Ideas/Idea.md` is not a ghost and the "Links to no note" check never reports it. Obsidian reads the qualifier as a path and does not find it.
- `rename_note_to_path` renames a note and rewrites the links to it; the web app then calls `note_changes.rename_everywhere` so a persona's pending changes follow. The terminal has to do the same.
- `Finding.fix` carries the icon lines the web dialog shows.

## Decision (the vault owner chose the scope and the icon, 2026-10-14)

**The command.** `sympose vault --fix [--persona <handle>]` reads what that persona can read, like the other two options. It needs a terminal (input and output both), since it asks; run into a pipe it says so and exits 1. Each repair is shown as what changes, and the prompt is `[y/N/q]`: yes applies it, anything else leaves the note as it is, `q` stops. It is never bulk, never automatic, and there is no "yes to all".

**The walk.** The vault is scanned, the first finding with a repair that was not answered yet is offered, and after an answer the vault is scanned again, so a rename that moved a note or changed links is never acted on from stale information. A repair answered once is not offered again in the same run, so a refused or failed one cannot loop. The run ends with one line: how many were changed and how many left. Exit code 0, or 1 when a repair failed.

**The repairs.**

1. **A title that is not the file name** (check 4 of ADR 034): the file is renamed to `<title>.md` in its folder through `rename_note_to_path`, which rewrites the links that point at it, and the persona's pending changes follow. Offered only when the rename can work: the title is safe as a file name and as a wikilink (none of `\ / : * ? " < > | [ ] #`, no control character, not ending in a dot, not too long) and no other note anywhere has the new name and no other note has the old one. In those two cases a bare `[[link]]` names more than one note, and a rename changes which one the link reaches (measured below), so it is left to the person. A finding with no repair stays in the report, and the closing line says how many have none. A title that differs from the file name only in case or spacing is not a finding (ADR 034), so it is not renamed.
2. **A link whose folder no longer matches** (a new check, "Links with a folder that no longer matches", a problem): a `[[Folder/Note]]` link where no note is at that path (any note whose path ends with it counts, as in Obsidian) but exactly one note has the name. The repair rewrites that link, in that note, to the folder where the note is now, keeping as many folder segments as the link had (none if the note is at the vault root), and leaves any `#heading` and `|alias` alone. Every occurrence of the identical link target in the note is rewritten together (with its `#heading` and `|alias` kept, and an embed `![[...]]` too), and the line after the yes says how many. When several notes have the name, nothing is offered and the finding says so: a target is never guessed. A link to a name no note has is the existing "Links to no note" check and stays unfixed.
3. **A folder definition with no icon** (ADR 064): unchanged, the same lines added on a yes. It moves from `--health` to `--fix`; the web app's button stays.

**`--health`.** Read-only again: the prompt and its `ask` parameter are removed. When a finding has a repair, the report ends with one line saying `sympose vault --fix` offers it.

**What is not fixed here.** Empty notes (never deleted, ADR 034), a link to a name no note has (no target to suggest), Markdown links, and a note outside what the persona can read. A `[[link]]` shown as code (a fenced block or an inline span) is a sample, not a link: the stale-link check does not read it and the repair does not rewrite it (the rename's own rewrite still does, the limit recorded on #42).

## Measured (2026-10-14, scratch copies, nothing of the real vaults written)

The whole walk was run, answering yes to everything, on a scratch copy and the link graph compared before and after (every edge as source title and target title, and the ghosts).
- A copy of the `garden` vault (186 notes): one repair offered (an icon), 0 failures, graph identical. It has no title mismatch and no stale link, so it did not exercise the rename.
- A generated vault of 285 notes in 6 folders with 1710 links in seven forms (bare, qualified, alias, heading, embed, qualified with heading and alias, and a stale folder), a fifth of the notes with a different title, a tenth sharing a name across folders: 254 repairs in 9.9 s (the vault scanned again after each), 0 failures, edge count 1710 before and after, every edge identical, no ghost made. The first run also renamed notes whose name another note shares: 9 of the 1710 links then reached a different note, all of them bare links to a name several notes have. That is why the rename is not offered for those (the Decision above); with it, the graph is identical.
- Not measured: a vault with 600 notes of the owner's own (`~/obsidian`; a copy was not made, since the sandbox declined it). The 62 renames ADR 034 predicted for it are the owner's to run with `--fix`, one yes at a time.

## Update (2026-10-15, after a `/code-review xhigh` of the slice)

- **A title is refused as a name by one set of rules** (`vault_file_names.py`), read by the report and by the repair, so they cannot disagree: besides what a disk refuses and what a wikilink cannot hold, a name that starts with a dot (the note would be hidden), one that starts or ends with a space, one that is a Windows device name (`CON`, `AUX`, `COM1` to `LPT9`, with or without an extension), and one that starts or ends with an apostrophe (the rename drops a quote at the edge of a name, so `'90s music` would become `90s music.md` and the report would flag it again). The report says which reason applies.
- **The summary counts a repair that failed apart** from one left as it is ("1 changed, 1 left as they are, 1 could not be made"), and Ctrl-C at the prompt stops like `q` and still gives the summary.
- **A link shown as code is left alone** by the stale-link check and by `retarget_link` (`markdown_code.py`: fenced blocks, inline spans closed by as many backticks as opened them, within a paragraph). Measured by tests, including a fence that never closes and a run of backticks of another length.
- **A refused relink says why**, as a rename does: the persona may not write there, or the note is not there any more.

## Consequences

- One command makes every repair the vault owner has agreed to; `--health` can be piped and run anywhere without a prompt.
- The terminal changes a note on an explicit yes only, as the web's Accept does; this is not a persona writing, so the rule that no persona mode writes on its own is untouched.
- The vault-wide scan #101 asked for exists, and a new problem can turn up in a vault that was clean: its exit code goes from 0 to 1 until the links are fixed.
- A title rename is not undoable from Sympose (the notes are the person's, and the rename layer is the only thing that knows every link it touched); the prompt shows both names so the person can say no.

## Alternatives rejected

- **A "yes to all" or a preview of everything first.** ADR 034: never in bulk, since a rename rewrites links elsewhere and is the most fragile write.
- **Keeping the icon prompt in `--health`.** Two places write a note from the terminal; the owner chose one.
- **Rewriting a stale link to the bare name (`[[Idea]]`).** It would resolve, but changes the person's style; the rename layer keeps the qualifier and so does this.
- **Offering a best guess for a link whose name matches several notes.** A wrong target is a silent wrong link; the condition for reconsidering is a way to show the person the candidates, which the one-line prompt cannot.
- **Fixing a link to a name no note has.** No target exists to offer; a suggestion by similarity is a guess.

## Update (2026-10-15, after a second `/code-review xhigh`, of the fixes above)

Eight findings, none severe. Fixed: Ctrl-C while a repair is being made (a rename can have moved the note and not yet rewritten its links) now says "Stopped while changing <note>: it may be half made, so look at that note", counts it as one that could not be made and exits 1; the code finder no longer splits lines at U+2028, a form feed or the like, which Markdown does not, so a fence marker after one opened a code block to the end of the note and hid every later link; a note taken away between the check and the read is reported as not found and not as "may not write there". Each has a test, checked by putting the old line back. Not fixed, and why: a block indented by four spaces is code in Obsidian and is not read as code here (a gap in what counts as code, small); a backslash-escaped backtick can open a span (the error is a link left alone); the rename's own rewrite still reads links shown as code (#42, above); the report says a title "cannot be" a file name for the reasons that are only Sympose's rename or Windows (wording). A plain Ctrl-C at the prompt still exits 0, as `q` does.

## Update (2026-10-16, the third review, of the fixes above)

`/code-review xhigh` of the last commit, six findings. Fixed, each test failing without its fix: the line split no longer drops a bare carriage return as a line end (the first fix had replaced `splitlines` with a split at `\n` only, so a note with old Mac line endings lost its fences), the separator test covers six characters, and the Ctrl-C message says where a rename may have moved the note. Not fixed: a Ctrl-C between the rename and the move of the persona's pending changes leaves those changes under the old path (a narrow window, the message already says to look at the note; making `apply` interrupt-safe is a larger change); the vanished-note branch logs nothing and also catches a vanished folder at the write (both are "not found" to the person); the vanished-note test patches the shared `os.path.isfile` for its whole run.

