---
type: decision
status: accepted
date: 2026-11-02
projects: [sympose]
concepts: [Chat engine, Cloud privacy]
amends: [36, 44]
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app, topic/engine]
---

# 097 — Settings are grouped by what the user is trying to do, and a feature's switch and its permission sit together

> **Summary.** The Settings page has about twenty sections in an order that grew by accident, and one feature (searching the web) is split between a permission near the top and a one-row group called Links near the bottom. The page is regrouped into seven sections by what the user is trying to do, in one fixed order, with the cloud permissions and `web_access` side by side. No new element is added: the same collapsible sections, the same search field, the same rows. The terminal's `/settings` reads the same list, so it changes with it.

## Context

- damiro (2026-11-02), after asking Samantha to search the web and being told she could not: he had the model (`gemini/gemini-flash-latest`) and the `web` permission on, and did not know where the third switch was. "The state of settings is totally in chaos."
- What the page holds, top to bottom (read from `settings-view.tsx` and `settings_registry.py`): eight sections of the app itself (Workspace, Markdown editor with Toolbar buttons, Notifications, Knowledge Nebula, Recent notes, Hidden from view, Chat, Cloud models), then ten engine groups: Conversation memory (14 rows), Search (4), Searching notes (2), Memory (3), Conversations (1), Editing (4), Skills (2), Links (1), Slack (1), Jobs (1). The registry has 33 rows in all.
- What is wrong with it: the permission to reach the web (`web`, in Cloud models) and the setting that makes it happen (`web_access`, in Links) are about fifteen sections apart under three different names; Conversation memory mixes model limits, recaps, related-note suggestions and compaction; four groups have one row; the names Search, Searching notes, Memory and Conversation memory overlap; and settings that change how the app looks (this browser) are mixed with limits, permissions and a persona's own files.
- What already exists and stays: collapsible sections with collapse-all, the toolbar search that hides rows and sections without a match (ADR 065), rows that come from one registry shared with the terminal (ADR 036, 044), the persona-owned rows (Skills, Jobs) drawn as `extras` under a group by its name, and `user_only` rows (Slack, ADR 093).
- damiro's rule for the app (memory and `PREFERENCES.md`): fewer places, no new strip, card or chip row; reuse what the app has. So this is a regrouping, not a new screen.

## Decision

1. **Seven sections, in this order:**
   1. **Look and feel** (what this browser draws): Workspace, Markdown editor and Toolbar buttons, Notifications, Knowledge Nebula, Recent notes, Hidden from view, Chat display.
   2. **Models and privacy**: the cloud permission switches (`cloud_share`) with `web_access` directly under `web`, then `model_timeout`, `context_window` and `reply_limit`.
   3. **Finding notes**: `grounding_search`, `embedding_min_similarity`, `embedding_margin`, `library_sync_limit`, `vault_lookup`, `vault_lookup_rounds`, `connections_by_meaning`, `connections_relevance`, `grounding_followups`.
   4. **Memory and past chats**: `session_recaps`, `recap_count`, `recap_chars`, `past_chats`, `history_tokens`, `auto_compact`, `compact_at`, `compact_to`, `memory_remember`, `memory_rewrite`, `memory_auto_refresh`, `parallel_replies`.
   5. **Editing**: `edit_mode`, `show_note_marker`, `open_note_cap`, `annotations_cap`.
   6. **Persona**: the Skills rows (`skill_lookup`, `skill_cap` and the persona's skills) and the Jobs rows (`waiting_drafts` and the persona's jobs), the two that already belong to the persona that is open.
   7. **Slack**: `slack` stays a section of its own, because it is the one place where replies leave the computer and only the user changes it (ADR 093).
2. **A feature's switch and its permission sit together.** `web_access` is drawn in Models and privacy next to the `web` permission it depends on, and its description names the permission. No setting is split from the switch that makes it work.
3. **Within a section the choices and switches come first and the numbers last.** A number is folded under the rest only if the section component already can, without a new element; the slice looks at the real page before deciding.
4. **The sections open when first seen are the ones a user changes; Look and feel starts closed.** The slice checks what each section does today and changes only that.
5. **The group names are the registry's `group=`.** The web app, the terminal and the persona's own `propose_setting` (which names a key, not a group) read the same registry, so the regrouping is one change to the group constants and their order, plus the web page's section order. No key is renamed, so no stored setting changes.
6. **The reference library follows the change.** Whatever `sympose/reference/` says about where a setting is found is brought up to date in the same slice, and the retrieval eval is run before and after, because the persona quotes it as truth.

## Consequences

- A person looking for "search the web" finds `web` and `web_access` in one place, in a section whose name says what it is for.
- The terminal's `/settings` changes with the web page; both show seven groups, and the terminal's own display settings (`cli/display_settings.py`) are unchanged.
- Rows that used to be one-row groups (Conversations, Links, Jobs) are folded into larger sections. Slack stays a one-row section on purpose and may grow.
- A test that names a group or the order of groups changes with it; a grep of docs and tests for the old names (Conversation memory, Searching notes, Links, Conversations) is part of the slice.
- `extras` (Skills, Jobs) and the cloud permission switches are drawn by the page, not the registry, so putting a registry row inside the cloud section or the cloud switches inside a registry group needs a small change to how the page composes them. How is for the slice to find; the outcome is fixed here.

## Alternatives rejected

- **Leave the groups and add a "where is it" index or a new first-run guide.** A new surface, which damiro rejects; the page would also stay long and mis-named. Right only if the page grows past what seven sections hold.
- **Tabs or a left-hand navigation** (App and Persona as two pages). A new element and a second place to look. Right if the sections themselves grow to where the page needs two levels; it would be a decision of its own.
- **Rename the keys to match the groups.** Breaks stored settings and the persona's `propose_setting` for no gain; the key is what a person reads in `settings.json`, and the group is only a heading.
- **Group by who owns the setting (engine, app, persona).** It is how the code is organised, not how a user thinks; the user asked where to turn on a search.
