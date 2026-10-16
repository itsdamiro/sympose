---
type: decision
status: accepted
date: 2026-10-16
projects: [sympose]
concepts: [Conversation history, Persona edits]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app, topic/consent]
---

# 086 — A conversation is archived to a note on the user's request, as a draft the user accepts

> **Summary.** A conversation's `⋯` menu has "Archive to note": one model call writes a short summary from the user's own messages, and it arrives as a new-note draft in `<her first folder>/Sessions/`, named by date and title. The user reads it in the editor and Accepts or Declines; the vault changes only on Accept. Nothing happens on its own, and the vision's "final memory update" half is dropped.

> **Status: Accepted, built** (2026-10-16, #20). Settled in a design talk with damiro on 2026-10-16. Builds on ADR 042, 070 and 071 (drafts), ADR 023 (recaps) and ADR 057 (the list of conversations).

## Context

The vision's fourth memory layer is "session-close archival": at the end of a session, one pass writes a final memory update and a real vault note. Two things in it do not fit what exists:

- **There is no session close.** The web app never ends a conversation; the list keeps them all, and a new one is just another row. The terminal's `/quit` is not a close either (recaps avoid it for that reason, ADR 023).
- **A persona never writes the vault** (ADR 042; the rule that no mode writes without Accept). A note written at "close" by the engine itself would be exactly that.

The write path already exists: a persona's new note is a draft in her own folder, listed in the Drafts section, opened in the editor before any file exists, and made only when the user clicks Accept (ADR 071). Memory files already have their own reviewed rewrite (ADR 041).

## Decision

**The user asks for it.** "Archive to note" is an item on a conversation's `⋯` menu and right-click menu in the list (ADR 057), beside Rename, Pin and Delete. No new strip, card or setting. Nothing archives on its own: a new conversation, a quit and a restart do nothing.

**One model call, from the user's messages only.** The persona's model (the model picker saves its pick on the persona, so that is the one the user chose) is given the user's own messages in order and asked for a short note: what the conversation was about, what was decided, what was left open, in plain sentences and short lists, using only what the user wrote. The persona's replies are left out for the reason ADR 055 and 023 found: a summary of them recorded something she made up as the user's own words. A long conversation is written from its newest turns that fit the model's window, as a recap is. A conversation with fewer than 2 turns is refused. A cloud model is asked only when the user has approved the `recaps` category for it (ADR 031), the same data going to the same place.

**It arrives as a draft.** The result is a new-note proposal (`note_changes.propose_create`) with the folder `<the first folder of her scope>/Sessions` (`Sessions` at the vault's root when her scope is the whole vault), and the name `YYYY-MM-DD <title>` (the day the conversation began and a title the model writes as the first line of its reply, else the conversation's own title). It carries a `type: session` property block, the date and the persona's name (quoted, so any name is valid YAML), and the summary (the session log itself stays in her own folder, outside the vault). The user finds it in Drafts, edits it freely, then Accepts (the note is made, the folder with it if needed) or Declines. A persona with no vault (ADR 079) cannot archive. An identical draft already waiting is not made twice (`propose_create` refuses it, and the user is told).

**Being a note once accepted,** it is read by the retriever, appears in the graph and respects the persona's folders like any other note. Archiving the same conversation again after it has grown makes a new draft; whether the first was accepted is the user's business (the same name in the same folder is refused at Accept, as for any note).

**The "final memory update" half is dropped.** ADR 041 already has the persona propose a rewrite of her memory files from recent recaps, for the user to review. A second proposal on the same click would be a second thing to review for no new information.

**API and terminal.** `POST /api/chat/session/{id}/archive` with the persona; answers `{draft: {path, name, folder}}`, 404 (no such conversation), 409 (a reply is being written in it, or the same draft is waiting), 422 (too short, no vault, the model not allowed to receive it), 502 (the model failed or wrote nothing, or spent its whole reply limit thinking). The terminal gets no command: editing and reviewing notes is web-app only, and a draft made from the web app is there to review.

## Consequences

- Archiving costs one small model call, only when asked. Round-trips stay as frugal as before.
- Zero-hallucination holds by construction: the note says only what the user wrote, and the vault's own notes are not summarised or cited. The user reads it before it exists.
- The Drafts section is where an archive waits, so a user who archives five conversations has five drafts to settle. Accepted: each one was asked for.
- A conversation is not marked as archived. The list does not say so; the Drafts section and the note itself do. Revisit if two archives of one conversation turn out to be a nuisance.

## Alternatives rejected

- **Automatic on a new conversation.** It matches the vision's "superseded by a new one", but it spends a model call and adds a draft the user did not ask for each time they start over, and "the user left it" is not a real end of a conversation.
- **An opt-in setting that archives on leaving.** A setting for something the menu does in one click; the first need to show up decides this.
- **A transcript in the note.** No model call and no invention, but it duplicates the session log and is not a summary. Where it would be right: a user who wants a readable copy of a conversation to keep in the vault.
- **Summary and transcript in one note.** The longest note, and half of it a copy.
- **A `session_folder` setting.** More configuration for something that has a sensible default (`Sessions/` under her first folder, so personas do not collide in one shared folder).
- **Writing the note directly.** Forbidden: no mode writes without Accept.

## As built (2026-10-16)

- `engine/session_archive.py` (`archive`), route `POST /api/chat/session/{id}/archive` in `server_session_handlers.py`, `ARCHIVE_INSTRUCTIONS` in `prompt_text.py`. The answer is `{draft: {path, name, folder}}`; the refusals are the ones listed above.
- The model is asked for a title line (up to six words), a blank line, then the note. A first line of more than ten words, or with no note after it, is not taken as a title: the conversation's own title names the note and the whole reply is the note. A first line that is a list item (`-`, `*`, `1.`) or starts with a tag is never a title. A reply cut by the reply limit loses its unfinished last line and any heading left with nothing under it.
- The local reply limit is 2,500 tokens, not the recap's 200: `gemma4:e4b` spent 450 thinking before writing a word (`model_failed` on 2 of 3 cases) and passes at 2,500. The user asked and is waiting, so the larger ceiling is paid only on the click. The request is sized to the window minus that reply (`_prompt_room`), not the chat turn's smaller reserve, so a long conversation cannot push a thinking model past its window. A model that spends the whole limit thinking gets its own 502 ("Try another model"), not "Try again".
- Web app: "Archive to note" on the row's `⋯` and right-click menu (disabled with a reason while a reply is written or with fewer than 2 messages). A click shows "Writing the note…" and then "<name> is waiting in Drafts" and refreshes the Drafts section; a second click while the call is out does nothing. The first message is one toast with no timeout, and the result replaces it.
- Measured on three invented conversations (a database choice, small talk, a visit), one run each, `gemma2:9b` and `gemma4:e4b`: both wrote a note from the decision conversation with every decided and open item taken from the user's messages and nothing from a planted reply ("the budget is 5000 dollars"); `gemma4:e4b` answered the small talk with `NONE`, `gemma2:9b` wrote a note called "Testing AI". `gemma2:9b` listed "I need to clean the guest room" under Decided, a mild overreach; the user reads the draft before it exists. 13 and 20 seconds for the three cases on `gemma2:9b` and `gemma4:e4b`. A sample, not a figure; no cloud model run.
- Reference library: one entry in `The web app.md` ("Can I archive a conversation?"), two cases in `tests/reference_cases.py`. The first wording of the entry, "keep a conversation as a note", took the passage of "can she write or edit my notes" away from its answer (`writes-notes`), so it avoids "write" and "new note". It is found by a question that names "Archive to note"; "where is the note from the conversation I archived?" finds nothing (a limit of how the retriever matches, not fixed). Retrieval eval unchanged (`auto` 62 of 68).
