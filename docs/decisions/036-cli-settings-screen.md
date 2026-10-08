---
type: decision
status: accepted
date: 2026-09-28
projects: [sympose]
concepts: [Settings]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 036 — `/settings` in the terminal chat: a list of the settings a user would tune, edited in place

> **Status: Accepted.** Closes #25. Builds what ADR 015 ("Not built yet: a CLI settings screen") and ADR 017 ("a settings screen for the follow-up knob") left open, and what ADR 032 pointed at.

## Context

`/settings` was a canned message. The knobs a user would tune (`context_window`, `reply_limit`, `show_trim_notice`, `show_grounding`, `grounding_followups`, `reply_reveal`, the search knobs) lived only in `settings.json`, edited by hand. A slash command per knob was rejected on purpose (ADR 015, 018): it does not scale. The pattern already in the chat for a list of switches is `/share` (ADR 031): a numbered picker where choosing a row changes it and the list stays open until Esc.

Every module already reads, validates and defaults its own knob (`reveal.words_per_second`, `budget.context_setting`, `embeddings.min_similarity`, and so on), and a value that is not usable quietly leaves the default. A screen must not copy those rules, or there would be two definitions of what a valid `embedding_margin` is.

## Decision

**`/settings` opens a numbered picker, one row per setting, `key — value: what it does`, in three groups.** Each row is a `Setting` in `cli/settings_registry.py`: the key (taken from the module that owns it, never re-typed), its kind, a one-line summary, and the module's own accessor that returns the value in force.

- **Display:** `show_grounding`, `show_trim_notice`, `show_context_meter`, `show_index_notice`, `reply_reveal`.
- **Context:** `context_window`, `reply_limit`, `grounding_followups`, `session_recaps`.
- **Search:** `grounding_search`, `embedding_min_similarity`, `embedding_margin`.

**Left out on purpose.** Settings with a home of their own: `chat_model` (`/model`), `default_persona` (`/default`), `cloud_share` (`/share`), and the vault settings (the web app). Settings a user rarely has a reason to touch: `embedding_model` (a different model needs its own `embedding_min_similarity` and a rebuilt index), `cloud_helper_limit`, `folder_definition_min_notes`, `folder_template_share`. They stay in the file, documented in the reference note "Settings".

**Three kinds of row, three ways to change one.**

- **A toggle** (the `show_*` knobs, `session_recaps`) flips when its row is chosen. Every toggle carries its default explicitly (all ship on today), and reaching the default removes the key, so the default applies again and a later change of it follows.
- **A choice** (`grounding_search`, `grounding_followups`) moves to the next of its few values. Reaching the default's value removes the key, as above.
- **A number** (`context_window`, `reply_limit`, `reply_reveal`, `embedding_min_similarity`, `embedding_margin`): choosing the row turns the chat box into a one-line prompt (`context_window: tokens, 2048 or more; empty for automatic · Esc cancels`). Enter saves; an empty entry removes the key (the default); Esc cancels. A value that is not a number is refused with the same hint and the prompt stays open.

After a change the list opens again on the same row, so several can be changed in a row; Esc closes it. Each change says what it is now, in one line in the chat.

**The module decides what is valid, the screen asks it.** A number is saved, then read back through the module's own accessor:

- read back as typed: saved;
- read back as the setting's default (the module ignored it: `reply_limit` 10, `embedding_margin` 7, a negative `reply_reveal`): put back as it was and say the value is not valid, with the hint;
- read back as something else (`context_window` 1000 is raised to 2048): kept, and the line says what is in force.

A toggle or choice is checked the same way (read back what was written). If the old value cannot be put back after a refusal, the line says so. The hint text is the one thing written twice (the rule itself stays in its module); it is documentation for the person typing, and the round trip makes a wrong hint harmless.

**Two small changes next to it.** `budget.py` gets `reply_setting()` (the bare `reply_limit` setting, as `context_setting()` already is for the window) and public names for its two keys, so the screen and `reply_reveal` read a setting the same way; `reply_reserve` uses it. `dispatch.py` sends a submitted line to the prompt while one is open; `state.py` holds which setting is being asked for.

**Settings take effect on the next message** (every module reads the file fresh; `reply_reveal` on the next reply). No restart.

## Consequences

- One more input mode in the chat box, only between choosing a number row and Enter or Esc. Slash-command autocomplete is off while it is open.
- The list has twelve rows (fourteen since ADR 040 added `vault_lookup` and `vault_lookup_rounds` at the end, under Search) and the picker shows about ten: the rest are reached with the arrow keys (digits select rows 1 to 9).
- The screen changes no default and no validation. A knob added later is one row in the registry.
- **Not built:** editing `embedding_model` and the other left-out settings; a "reset all"; a web settings screen (#79, needs #29).

## Alternatives rejected

- **A slash command per knob.** Rejected in ADR 015 and 018: twelve commands, none discoverable.
- **Presets instead of a typed number** (automatic, 4096, 8192, 16384, 32768). No input mode, but it cannot set `embedding_min_similarity` 0.74 or a `reply_reveal` of 35, and the search knobs are exactly the ones a user tunes by small steps.
- **Copying each module's range check into the screen.** Two definitions of a valid value; they drift the first time a rule changes.
- **A full-screen Textual settings page.** A new screen and focus model for what a list and one prompt do, and unlike the rest of the chat.
- **Writing the default explicitly when a toggle is switched back on.** A stale copy of the default in the file once the default changes.

## Review findings, before commit

`/code-review` (high) found six, all fixed and pinned by a test that fails without the fix: a number shown with `:g` (1048576 read `1.04858e+06`; now `str`); `math.isfinite` on a huge whole number raised `OverflowError` and would have ended the chat (only floats are checked now); Esc left the half-typed number in the chat box, and the next Enter would have sent it as a message (Esc clears it); Tab and the arrow keys still filled in a command while a number was asked for, leaving a stray count that swallowed the next keystroke (the composer's cycle does nothing while the prompt is open); a refusal that could not put the old value back still said it had; and the toggle default was an assumption inside `_flip` (now explicit, as for choices).
