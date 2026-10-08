---
type: decision
status: accepted
date: 2026-10-01
projects: [sympose]
concepts: [Chat engine]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/responsiveness, topic/cli, topic/web-app]
---

# 054. A reply in flight can be stopped

> **Summary.** A reply in flight can be stopped, in the web chat and the terminal. Before the reply is complete it is thrown away and nothing is saved; during the terminal's reveal it jumps to the whole saved reply. Cancelling takes effect at the model's next chunk, and a new message for that persona waits behind the stopped one until then.

Status: Accepted (damiro, 2026-10-01). Closes #121.

## Context

Nothing stops a reply that is being generated, in the web chat or the terminal: a long local-model reply has to be waited out. What the code does today, which decides what "stop" can mean:

- `call_model` (ADR 007, 013) streams from the provider but returns the whole reply as one string. Nothing is on screen until the reply is complete.
- The terminal then reveals the finished reply word by word (`cli/turns.py`, ADR 032). The web chat shows it whole, at once; it has no reveal.
- A turn is saved (`session.append_turn`) only at the end of `run_turn`, so a turn that stops before that leaves nothing behind.
- Messages sent while a persona's reply is running wait and go out together as one turn when it lands (ADR 008 and 044, amendments of 2026-10-01), in both surfaces.
- `turn_status` already keeps a per-persona registry that one thread writes (the turn) and another reads (the status poll).

## Decision

**What stopping means.**
- Before the reply is complete (the whole wait): it is thrown away. Nothing is saved, the user's message is not part of the conversation file, and the model's partial text is dropped. Stopping is not billed back or avoided: the request to the model is closed as soon as possible, and whatever the provider already generated is its own business.
- After the reply is complete but still being revealed (the terminal only): the reveal jumps to the whole reply at once. The reply is already saved; stopping the reveal does not edit the conversation.
- Messages that were waiting still go out, as one turn, in both surfaces. Only the stopped reply is dropped.
- The stopped message comes back to the writer: in the web chat its bubble is removed and its text put back at the front of the message box; in the terminal it is put back in the input when that is empty. Either way a line says the reply was stopped.

**Engine.** A new `engine/turn_cancel.py`, shaped like `turn_status`: a per-persona registry behind a lock, plus a thread-local naming the persona whose turn the current thread is running, so `call_model` needs no new parameter and a background job that also calls it (recaps, memory, phrases) is never affected. `run_turn` runs inside `turn_cancel.running(handle)`; `request(handle)` is a promise: `True` means nothing of that turn will be saved, `False` means no turn is running (so a late click cannot cancel the next turn) or the reply is already past its last check and will be saved and shown. `check()` raises `TurnCancelled`. It is checked between the chunks of the stream in `call_model` (which then closes the stream), between a turn's tool calls in `lookup.converse`, and by `commit()` in `run_turn`, the last check before the reply is applied and saved: atomic with `request`, so a stop is never both accepted and ignored. `TurnCancelled` is not an `EngineModelError`, so a caller cannot show it as a failure by accident.

**Web.** `POST /api/chat/cancel` with the persona calls `request` and answers `{"stopping": true|false}`; the turn's own request then answers `{"cancelled": true}` instead of a reply. The Stop button sits at the far right of the message box and shows only while a reply is in flight. Clicking it asks the server first; only when the server accepted does the client abort its wait and free the chat (so a stop that arrives after the reply is complete does not throw away a reply the server has saved: it simply arrives).

**Terminal.** A `■ Stop` line under the input (above the context meter), shown only while a reply is being written or revealed, clickable: it asks the engine to stop every reply being written (the line says `■ Stopping…` until the engine ends its call, since a reply whose model has produced nothing yet is only noticed at its next chunk) and shows every reveal in progress whole at once.

## Consequences

- Cancelling takes effect at the model's next chunk. In the web chat the screen is free at once; the engine's thread ends when the next chunk (or the call's own timeout, for a model that has produced nothing yet) arrives, and a new message for that persona waits behind it (the per-persona lock) until then. In the terminal the Stop line says `Stopping…` for that time. In a real check against a local model the thread ended within about two seconds.
- A tool call the turn already made before the stop is not undone: a `remember` (ADR 041) that was applied stays in `decisions.md`, which is append-only, visible in `/memory` and in the file itself. The marker form is applied only after the check, so it is dropped with the reply.
- A turn stopped in the middle of the persona's lookups (`vault_lookup` set to `ask`) leaves no trace of those lookups in the session record, since the record is written with the reply.
- No new setting: stopping is always available, and it changes nothing for anyone who never presses it.

## Alternatives rejected

- **Keep the partial text.** There is none to keep: nothing reaches the screen before the reply is complete, and a half-written reply saved as if the persona had said it would make her appear to have said it.
- **Cut the saved reply to what the reveal had shown.** It means editing a saved conversation after the fact for the sake of an animation; showing the rest at once is what the user asked for.
- **Clear the queued messages on stop.** They are things the user said and wants answered; stopping one reply does not unsay them.
- **A cancel parameter threaded through `call_model` and every caller.** The thread-local keeps the change to the places that stop, and cannot be forgotten by a new caller.
- **Cancel on the server only.** The web's request would keep the chat looking busy until the next chunk arrived; the client aborts its own wait at once.
