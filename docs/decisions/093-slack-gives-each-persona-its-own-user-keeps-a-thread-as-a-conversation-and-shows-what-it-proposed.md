---
type: decision
status: accepted
date: 2026-10-21
projects: [sympose]
concepts: [Persona, Apps]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/engine]
---

# 093 — Slack gives each persona its own user, keeps a thread as a conversation, and shows what it proposed

> **Summary.** `sympose slack` is a thin adapter over the engine: Socket Mode, one owner-only allowlist, each persona its own Slack identity that the user DMs like a teammate, a thread (or a DM) as one conversation. The persona may propose notes from Slack, and its reply carries the proposed text, because the web app that holds Drafts cannot be reached away from the Mac. Accept stays in the web app. A new `slack` approval is off by default.

> **Status: Accepted (2026-10-21), designed with damiro.** He read the defaults I had chosen and kept all of them but one: he wants a green dot labelled "Slack" on the persona page while that persona is connected (see "Settled with damiro"). Revised the same day: he wants each persona to be a Slack user he can message, which replaced routing by name inside one bot. Shares the headless turn with scheduled runs (ADR 091, #36). Builds on ADR 006 (`run_turn`), ADR 008 (message queueing), ADR 031 (what a cloud model may receive), ADR 070 (proposals and drafts) and ADR 089 (capture).

## Context

- VISION: one engine, many channels; Slack is next, "the way to reach the vault remotely, away from the desktop web app". Socket Mode (an outbound connection, no public address), a Bot Token and an App-Level Token from a Slack App made once, and one owner-only allowlist check before anything reaches the engine (legacy checked which events to react to but never who sent them).
- `sympose-legacy/sympose/slack.py` is the reference for the shape, not code to copy. It ran one Slack App per persona (`MultiPersonaSlackRunner`: one Socket Mode daemon for each persona on the roster, side by side, tokens `SLACK_<HANDLE>_BOT_TOKEN` and `SLACK_<HANDLE>_APP_TOKEN`, a persona with none skipped) and, inside one app, could also switch persona by the first words of a message. damiro's word: "like the legacy Slack". It kept a heartbeat file so its dashboard could say whether Slack was live. It keyed a channel conversation on Slack's `thread_ts` and a DM on the channel alone, because nobody clicks "reply in thread" when messaging a bot and keying a DM on the thread made every plain follow-up start from nothing.
- The engine has no idea which channel it is in. Only a scheduled run says anything about itself to the model (`turn.UNATTENDED`, ADR 091), in the model's text alone.
- A proposal or a new-note draft waits for Accept in the web app, and the web app listens on `127.0.0.1` only. Away from the Mac, a draft filed from Slack cannot be seen or accepted. A persona's Slack reply is the only place the user can read it.
- The approvals so far (`cloud_share`, `engine/sharing.py`) say what a cloud model may receive, and a local model gets everything. A Slack reply leaves the machine whatever model wrote it, so `slack` is a different kind of approval from the others.
- damiro's standing rules apply: no persona mode writes the vault on its own, and Samantha is the only persona that ships.

## Decision

**A channel, not an engine change.** `sympose slack` is a long-running command beside `sympose web` and `sympose cli`. It turns a Slack event into `run_turn(handle, text, session_id, edits=True)` and the reply into Slack's text format, nothing else. It holds no vault logic of its own.

**Each persona is its own Slack user.** A persona is a Slack App of its own (a bot user with the persona's name), so the user finds it in the sidebar and messages it as he would a colleague. Which bot received the message is which persona answers: there is no routing by name and no `/switch`. `sympose slack` opens one Socket Mode connection for each persona that has a token pair, found by looking at the roster (`profiles/`), so no persona is named in the code. The pair is read from the environment as `SLACK_<HANDLE>_BOT_TOKEN` and `SLACK_<HANDLE>_APP_TOKEN` (`.env.example` shows the pattern with the default persona), and a persona with none is simply not in Slack. Legacy's fallback to one shared `SLACK_BOT_TOKEN` for every persona is not kept: it would make two personas one Slack user. A persona added later is picked up when the command is restarted. To make the App for a persona is a one-time step in Slack; `sympose slack manifest <handle>` prints the App manifest (name, Socket Mode, the scopes and events it needs) to paste into Slack, so nothing is typed by hand (the persona's picture is set in Slack by the user; it is not sent).

**Connection and who may talk.** Socket Mode through `slack-bolt` (a new dependency, as `youtube-transcript-api` was). The owner's Slack user ID is read from the environment once and applies to every persona. A message from any other user is dropped before the engine, with no reply and no log of its text. A persona's missing token stops that persona's connection with the sentence that names it, and the others carry on (`sympose doctor` lists each persona's state). Where a persona listens: direct messages to its bot, and messages that mention it in a channel it was invited to. Two personas mentioned in one thread answer separately, each in its own conversation.

**A conversation is a thread; a direct message is one conversation.** In a channel the key is the persona, the channel and Slack's thread (the message's own time stamp for the first message, so a reply in its thread continues it). In a DM the key is the persona and the DM channel alone, so every plain follow-up continues, as legacy found it must. `/new` in a DM starts another. The key maps to a session id in one small file in that persona's data folder, beside the job records and out of the vault. The conversation is an ordinary one, so it shows in the web app's conversation list and can be opened, renamed, archived and replied to there.

**The persona is told it is in Slack.** `run_turn` takes a channel, and `turn.SLACK` is added to the model's text only, as `UNATTENDED` is: you are answering in Slack; keep the reply short; no open note, no editor; a proposal is shown here and waits in Drafts, and only the user accepts it, in the web app. It is not saved in the conversation, and it costs a few tokens a turn.

**The persona may propose notes from Slack, and the reply shows them (damiro's choice B).** `edits=True` as in the web chat. After the reply, the adapter appends a block built from the pending record the turn filed, not from the model's paraphrase: for a new note, its path and its text; for a change to a note, the note and each change as old text → new text; then one line saying it is waiting in Drafts for Accept in the web app. What the user reads is therefore what Accept would write, even if the model described it badly. A block longer than Slack takes is cut at a limit measured when it is built, and says how much was left out and where to read it. There is no Accept or Decline in Slack in this slice. Nothing writes the vault without the user's Accept in the web app.

**The `slack` approval, off by default.** A Slack reply carries note text to Slack's servers whichever model wrote it. The new `slack` approval is listed in Settings with the others, off until the user switches it on, and it applies to local models too. It is one switch for every persona. The check is the adapter's, before the engine, because `sharing.gate` lets a local model through. With it off, a message from the owner is answered with one line that names the setting and contains nothing from the vault, and a persona's connection is not even opened until it is on. The cloud-model approvals still apply on top, as in chat, and a held-back notice is passed on as a line under the reply.

**A green dot says the persona is connected (damiro's call).** While a persona's Socket Mode connection is up, `sympose slack` refreshes a small heartbeat file in that persona's data folder (out of the vault); the persona page shows a green dot labelled "Slack" when the file is fresh and nothing when it is not, so a persona with no tokens, or a stopped command, shows no dot. It is the existing page, one dot and one word, no new strip or notice.

**One turn at a time per persona.** A Slack turn takes the same per-persona lock as the web chat. A message that arrives while a reply is running waits its turn in order (ADR 008), and Slack's own redelivery of an event is recognised by its id and ignored.

**Not in this slice.** Files attached in Slack (the `media` approval and a hosted download are a second design), Accept in Slack, a Slack-side listing of Drafts, and any persona that is not on the roster.

## Consequences

- Easier: the engine and every guard (grounding, the cloud gate, proposals, the lock) are reused as they are; Slack adds only the adapter, the `slack` approval and one line of text for the model.
- Easier: capture from a phone works as link now, Accept at the desk (ADR 089). The reply shows the proposed note, so the user knows what is waiting.
- Harder: drafts can wait unattended until the user is at the Mac. The cap on waiting drafts that was offered for jobs applies here too, and is not built.
- Harder: a reply in a channel is visible to every member of that channel. The bot answers only the owner, but what it says is not private. The owner decides which channels it joins; the reference entry says so.
- Harder: one Slack App to make for each persona, and a token pair for each in the environment file, like the cloud keys, never in the vault or the settings file. The manifest command makes each a paste, not a form. A persona's name in Slack is the App's, so a rename in Sympose does not rename it in Slack.
- Open: the exact limit of a Slack message and how Slack renders a table or a wiki link in the reply, to be measured against a real workspace when the adapter exists. Tests before that use recorded event shapes; the real check needs a Slack App that damiro creates once and cannot be made from here.

## Settled with damiro (2026-10-21)

- Each persona is its own Slack user that he messages directly, like a teammate (revised the same day; this replaced routing by name inside one bot).
- A conversation is a thread, and a DM is one conversation (his agreement to the legacy fix).
- A new `slack` approval, off by default.
- The persona may propose notes from Slack, and its reply shows the proposal (option B). Accept stays in the web app.
- A green dot labelled "Slack" on the persona page is the connection indicator (he asked for it; my default had been none).
- The other defaults below, read and kept.

## Defaults I chose, read and kept by damiro

- One switch (`slack`) for every persona, not one per persona.
- ~~No heartbeat or live indicator in the web app~~ Changed by damiro: a green dot labelled "Slack" on the persona page (above); `sympose doctor` also says which persona is connected.
- `sympose slack manifest <handle>` prints the App manifest to paste into Slack.
- The roster is read at start, so a new persona needs a restart.
- Direct messages and channel mentions both work; the alternative is direct messages only, which would remove the channel-visibility risk and the thread keying.
- `/new` starts another conversation in a DM.
- The adapter, not the model, writes the proposal block under the reply.
- No attached files and no Accept in Slack in the first slice.

## Alternatives rejected

- **No edit tools in Slack (option A).** The least to build and nothing can pile up unseen, but it loses capture from a phone. Becomes right if drafts pile up unread.
- **Accept and Decline buttons in Slack (option C).** A second path to the never-writes-on-its-own rule and a poor place to review a diff. Becomes right if the user finds himself away from the Mac for days with drafts waiting; it needs its own design talk and an ADR amendment.
- **Incoming webhooks.** Needs a public address and signature checks. Socket Mode needs neither.
- **One bot that routes a persona by name in the message.** One App to make and one token pair, but personas are not people in the sidebar and a mistyped name sends a private question to the wrong persona. Becomes right if making an App per persona proves too much work.
- **One persona for all of Slack, set once.** Simpler, but the user wants to talk to different personas.
- **A DM keyed on Slack's thread.** Every plain follow-up would start a new conversation (the bug legacy had).
- **The model describes its own proposal.** A small model paraphrases badly; the user would approve something other than what Accept writes.

## Slices

1. The adapter: a connection for each persona with tokens, owner check, thread and DM keys (with the persona), the session map, the `slack` approval, the per-persona lock. Tests on recorded events; mutants.
2. `turn.SLACK` and the proposal block under the reply, with the cut.
3. `sympose slack manifest`, the heartbeat file and the green dot on the persona page, Settings row for the approval, `sympose doctor` check for each persona, reference entry and cases (retrieval eval before and after), the real check against a workspace once he has made the App.

## As built: slice 1, the adapter

- `slack_events.py` (the one `Incoming` shape; `parse` answers a direct message to the bot or a mention of it and nothing else, no bot, no subtype such as an edit or a file share; `conversation_key`), `slack_sessions.py` (the map in `<persona>/.slack/sessions.json`, `Seen` for redelivered ids), `slack_text.py` (Markdown to `mrkdwn`, cut at 39,000 characters with a line saying so), `slack_channel.py` (`answer`, `new_conversation`, the `slack` flag in the settings file, `SLACK_OWNER_USER_ID`, `SLACK_<HANDLE>_BOT_TOKEN`/`_APP_TOKEN`), `slack_connect.py` (`listeners`, `connect` through `slack-bolt`, `run`), and `sympose slack` in the launcher.
- A turn takes the web chat's own lock (`server_chat_locks`), so a Slack message and a web message to one persona run one after the other.
- `run_turn` is called without `edits` until slice 2, so in this slice a persona in Slack proposes nothing (a proposal could not be shown yet).
- `sympose slack` refuses to start with Slack switched off or no owner set; a message that arrives after the switch is turned off gets the one-line answer. A persona whose tokens Slack refuses is named and the others carry on.
- `/new` is a Slack slash command (the manifest of slice 3 must declare it); typed in a channel it asks for a new thread instead.
- Checked: 79 tests on documented event shapes and through `slack-bolt`'s own dispatch (arguments by name, `message`, `app_mention`, `/new`), 32 of 33 mutants caught (the other is equivalent). Not checked: a real workspace (needs the App he makes once).
