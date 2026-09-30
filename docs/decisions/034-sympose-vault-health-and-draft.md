# 034 — `sympose vault`: a read-only health report on the notes (`--health`) and the offer of a folder definition (`--draft`)

> **Status: Accepted** (2026-09-27, after the design talk with the vault owner on issue #77). Not built yet; this record comes first, as the standards ask. Settles the first list of checks of #77 and where ADR 033's stage 3 is offered.

## Context

`sympose doctor` (ADR 029) looks after Sympose's own files. Nothing looks at the notes: an empty note is invisible to search until ADR 030, a link left pointing at nothing after a rename or a move is found only by reading the graph (#42, #43, #46), and a folder that has grown to fifty notes has no definition until someone thinks of writing one (ADR 033). Issue #77 asked for a read-only report on the vault that adapts to what the vault already does, and the design talk settled the name, the shape and the first checks.

Facts about the code as it stands:
- The link resolver already exists and is the one the Knowledge Nebula uses (`vault_manifest_build`): it drops a note extension, ignores links to attachments, and yields a "ghost" node for a link that names no note. A second link parser would disagree with the graph.
- A note's title is `title:`, else `name:`, else the file name (ADR 030), so a note is never without one. A blank `title:` (nothing after the colon, or empty quotes) reads as no text and falls through to the file name.
- The drafting functions of ADR 033 exist and have no surface: `folder_definitions_write.due(profile)`, `draft`, `write`, and `engine/folder_purpose.propose`.

## Decision

**The command.** `sympose vault` is a fourth subcommand of `sympose` (ADR 028). It has two options, and run with neither it prints its help:

- `sympose vault --health` scans the notes and reports. It is read-only, makes no model call, and changes nothing.
- `sympose vault --draft <folder>` drafts the folder's definition (ADR 033), shows it, and writes it only when the person types yes. The model call for the purpose paragraph (`propose`) happens here and nowhere else.

Both read what one persona can read: the persona named by `--persona <handle>`, else the `default_persona` setting (Samantha over the whole vault unless it is set). It is one option because `due` and `draft` already take a profile, and a persona scoped to one folder must not be shown findings about notes it cannot see. Why `vault` and not `health`: the name says what the command reads (doctor reads Sympose's files, this reads the vault), where "doctor" and "health" are synonyms nobody can tell apart.

**Findings.** Each check is one function returning findings, the shape of ADR 029 without the fix: which check, the note or folder, and a plain sentence. A later check is one more entry in a list. The report groups by check, and inside a check by top-level folder: one line per folder with its count ("Daily: 365 of 365 notes"), then the first three notes of that folder, then how many more there are, so a vault with thousands of one kind is a summary and not a wall, and a folder where every note is affected reads as one fact. It is printed to the terminal only: note names appear in it, so it is never written to a file, a log or an issue.

**Exit code.** 0 when nothing is wrong, 1 when a problem was found, as the doctor. A folder due a definition is an offer, and clutter is an observation: each is listed under its own heading and neither changes the exit code (a check has a `problem` flag, true by default).

**The first checks.**

1. **A folder due a definition** (an offer): `folder_definitions_write.due(profile)`, with the note count. It says the folder can be drafted with `sympose vault --draft <folder>`.
2. **An empty note:** no text and no properties, so nothing but its file name (a note that is only a title, like a quote, has its title as content, so it is not empty if it has a heading or any text; a note that is only properties is not empty either). A note with no body text but with properties or headings is what ADR 030 handles and is not a finding.
3. **A link that points at no note:** a wikilink (`[[Name]]`) to a note that does not exist, read from the graph the Knowledge Nebula draws (`vault_graph.get_vault_graph`), so what is reported is what the graph shows as a ghost, including its rule that a link from a visible note to a note the persona cannot see is not broken. A link to an attachment is not a finding. Markdown-style links (`[text](Note.md)`) are not in the graph and are not checked; the report says so once. Links inside code blocks are not skipped, which is the known limit recorded on #42; the report says so once.
4. **A title that is not the file name.** The vault owner's rule: a note's title and its file name are one and the same, and the title wins. Compared ignoring case and spacing (`my note` and `My  Note` are the same title; see "Measured"). Only a note that declares a `title:` or `name:` with text can differ. The finding names the note, its title and its file name. It has no fix inside the report. A rename rewrites every link that points at the note, which is the most fragile part of the write layer (#42, #43, #46), so any fix is offered one note at a time, on request, through the rename layer, and is not built here. A title that cannot be a file name (it holds `/ \ : * ? " < > |`, or is longer than a file name may be) is reported as one that cannot match, saying why.

5. **Other files (clutter), an observation, not a problem.** A file that is neither a note (`.md`, exactly, as the snapshot reads it, so `Note.MD` is one), nor an attachment Obsidian opens (`ATTACHMENT_EXTENSIONS`), nor one of Obsidian's own types (`.canvas`, `.base`): `.txt` and `.markdown` files (#52), a file with no extension, a `.docx`. Hidden files, hidden folders and the folders the snapshot skips (`IGNORE_FOLDERS`) are left out, and only the folders the persona may read are walked. It is the vault owner's word, "clutter", and it is listed after the problems and never changes the exit code, since a stray file harms nothing. It counts files per folder and not "of N notes". Nothing is offered for it: no rename, no delete.

**What is not a finding.** A note with no `title:` property, or with a blank one: the file name is its title (the vault owner's decision), and it is already read that way, so Sympose writes nothing into the note. Unread frontmatter, notes with no tags, keys most notes in a folder carry that this one lacks, and notes nothing links to are left for later: they need the folder's convention inferred, which is #23's design (ADR 033 says the definition's template is what the notes are checked against), and on a large vault most of them would be noise. `.txt` and `.markdown` files are check 5, found by a file walk, since the snapshot skips them.

**A `--fix` is documented, not built.** Decided with the vault owner: this version is `--health` and `--draft` only. A later `sympose vault --fix` would be an interactive walk through the findings, one note at a time, each change shown as a diff and applied only on a yes, never in bulk and never automatic (the notes are the person's own content, which is why the doctor's `--fix`, limited to Sympose's own files, is not the model). The first fix would be the title rename (rename the file to the title, rewriting the links that point at it), and only after the rename layer has been measured on a scratch copy of a vault: on the measured vault it is 62 renames, each rewriting links elsewhere (#42, #43, #46). Empty notes are never deleted by a fix (a placeholder or a quote may be intended), and a broken link is only ever offered a suggested target, never guessed. `--draft` could fold into it as one of its offers.

**Nothing is written without a yes.** `--health` has no write path. `--draft` shows the draft (the purpose and the template and the note count it came from) and asks; a no or anything else ends without writing. If the model cannot give a purpose (unclear, withheld from a cloud model, failed), the draft is shown with the template and no purpose, and says why (ADR 033 item 7). What may go to a cloud model is decided where it already is, by the `notes` category of ADR 031.

## Measured (2026-09-27, a count on a personal vault of 619 notes; counts only, read-only)

309 notes declare a `title:` or `name:` (16 of those are blank and fall to the file name); the other 310 declare none, and the file name is their title. Of the 293 that declare text: 236 match the file name exactly, 11 differ only in case or spacing, 3 hold a character a file name cannot, and 59 differ otherwise (32 where one contains the other, 27 unrelated). So the rule as decided reports 62 notes (10% of the vault, 21% of those with a title) once case and spacing are ignored, 3 of them as "cannot match". The Obsidian help docs (176 notes) and the synthetic vault declare almost no titles, so they show nothing either way. That vault has no date-named notes, so the daily-note case (a template that writes the title in a different format from the file name, `Monday, 5 January` against `2026-01-05`) is not measured; it would be one finding per day, which is why a folder is summarized on one line. The count is a fact about that one vault.

## Consequences

- The person has one command for what is wrong in the notes and one for the next step that is offered, both named after what they read.
- The check functions are the ones the terminal chat (`/health`), the agent (#21) and the web app reuse later, as ADR 033 intended.
- The title rule means a vault whose titles differ from its file names (a daily note titled "Monday" in `2026-01-05.md`) gets one finding per note, shown as one line per folder. That is the rule the vault owner chose; the folder summary keeps it readable, and a later setting can narrow it if it proves too loud.
- The report reads every note through the cached snapshot, so a second run on an unchanged vault is cheap.

## Built (2026-09-27)

`sympose/vault_health.py` (the five checks and `scan`), `vault_health_report.py` (the text), `vault_command.py` (`health`, `draft`), and the `vault` subcommand in `launcher.py`; tests in `tests/test_vault_health.py` and `tests/test_vault_command.py`, 51 in all, each new check mutation-checked (35 mutations; the four survivors were tests to add, except a Windows-only path separator that cannot be tested on macOS). The reference library was brought up to date with it: a new note, "Checking your notes", ten retrieval cases, and four corrections of notes that had drifted (`.markdown` and `.txt` read as notes, the editor as the only writer, three settings missing from Settings, properties and empty notes not mentioned). On the measured vault the report finds 7 empty notes, 58 links to no note and 62 titles that are not the file name (the number predicted above), and offers 7 folders a definition; the clutter check was added after this run. A live run on the real vault found the due-folder line reading "Code: 1 of 125 notes" (the per-note grouping header applied to a finding that is about the whole folder, not a note in it); fixed with a `per_folder` flag on a check that skips that header, and the folder's name moved to the front of the finding's own message. `--draft` was run with the real model (`gemma2:9b`) on a scratch vault: a "no" writes nothing, a "yes" creates `Contacts/Contacts.md`, and a second run refuses because the note exists. One fix from the tests: the graph keeps `[[Gone]]` and `[[gone]]` as two ghosts, so the check counts them once, as Obsidian does.

## Alternatives rejected

- **`sympose health`.** Rejected by the vault owner as confusing beside `doctor`.
- **Folding it into `sympose doctor`.** `doctor --fix` changes Sympose's own files, and this command must never change a note; two commands keep that line hard to cross by accident.
- **A separate command for drafting.** The draft is the one write this area offers and is the report's own offer; one command with two options keeps them together.
- **Reporting notes without a `title:` property.** Nearly every vault is full of them, and the file name is the title; it would be a finding nobody acts on.
- **Writing the file name into a note's `title:`.** It changes the person's notes to record what is already true.
- **A second link parser in the report.** It would disagree with the graph about what is broken.
- **Inferring each folder's convention in this first version.** The issue's own risk (noise); waits for the definitions of #23.

**Amendment (2026-10-01): stale folder-qualified links are a `--fix` job (damiro, #101).** A rename or move rewrites only the last segment of a link like `[[Projects/Idea]]`, so a move leaves it pointing at nothing (or is missed on a move that keeps the name). Rather than reworking the rename layer's link rewrite now, the repair belongs to the future `sympose vault --fix`: the "Links to no note" check already finds such links, and `--fix` offers a suggested target one note at a time, each change shown and applied only on a yes (above). Until then the rename layer is unchanged and the check reports what it leaves behind.
