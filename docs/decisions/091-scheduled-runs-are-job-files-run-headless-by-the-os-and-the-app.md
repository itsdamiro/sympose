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

# 091 — Scheduled runs are job files, run headless by the OS scheduler and by the open app

> **Summary.** A scheduled run is a job: one Markdown file in the persona's data folder (outside the vault) holding a schedule, a model and a prompt, listed in Settings and opened in the editor. Anything that changes a note arrives as a draft, so a run never writes the vault. `sympose run --due` runs what is due and exits; launchd calls it, and the open web app calls the same function. Some jobs are mechanical (no model), and every job picks its own model, local or cloud, under a per-job cap.

> **Status: Accepted (2026-10-21), designed with damiro.** Shares the headless turn with the Slack channel (#36). Builds on ADR 006 (`run_turn`), ADR 031 (what a cloud model may receive), ADR 061 (a persona's files open in the editor), ADR 070 (proposals and drafts) and ADR 086 (a draft in `Sessions/`).

## Context

- `run_turn` is one atomic unit (ground, build, call, persist) and is called only by the web server (`server_chat_handlers`) and the terminal (`cli/turns`). Nothing starts a turn on its own.
- A proposal or a new-note draft already waits in the persona's folder for the user's Accept (`note_changes`, ADR 070 and 086), so an unattended turn cannot change the vault by construction (CLAUDE.md: no persona mode writes the vault on its own).
- A cloud model receives only the categories listed in `cloud_share` (ADR 031). Nobody watches an unattended run, so a notice about what was held back must be kept for later.
- Measured cost (ADR 089): a turn that searches is 1.5 to 3 cents; prices double on 2027-01-01. A wrong schedule or a retry loop is the risk, not one run.
- What damiro asked for (2026-10-21): jobs listed in Settings and each opened in the editor; local and cloud models both allowed; the trigger both from the OS and from the app; some runs mechanical; a model chosen per run.

## Decision

**A job is a file.** `profiles/<handle>/jobs/<name>.md`, never in the vault (persona helper state stays out of it). The front matter holds the settings, the body is the prompt:

```yaml
---
schedule: weekly sun 18:00
model: gemma4:e4b          # omitted: the persona's model
kind: ask                  # ask (a model turn) or a mechanical kind
enabled: true
max_runs_per_day: 1
---
Look at the notes I changed this week. List open tasks and loose ends, and draft a weekly note in Journal/.
```

Settings gets a Jobs section: one row per job (name, schedule, model icon, last run's state and time, an on/off switch), a row opens the file in the editor (ADR 061's route), and a new job starts from a template. No new strip, card or notice.

**Schedules are plain words, not cron:** `daily 07:30`, `weekdays 07:30`, `weekly sun 18:00`, `monthly 1 09:00`, `every 6 hours`. A line that does not parse leaves the job off and the row says why.

**A run is a fresh conversation.** `jobs.run(handle, name)` calls `run_turn` with `edits=True` and the job's model, in a new session marked as scheduled, so it shows in the conversation list and can be read and replied to. Whatever the persona proposes lands in Drafts; the reply stays in that conversation. The caller supplies what the web chat supplies (approvals read from the same `cloud_share`), and a run that was held back records which categories, in the job's last-run line.

**Mechanical jobs call no model.** `kind: health` runs the vault health check and files its report as a new-note draft; `kind: refresh` rebuilds the search index and the persona's recaps. The `kind` list is closed and built in; adding one is a code change. Their `model` field is ignored.

**Two triggers, one function.**
- `sympose run --due` runs every enabled job whose time has passed since its last run, one at a time, and exits. `sympose run <handle>/<job>` runs one now. `sympose schedule install` writes one launchd entry (every 5 minutes, calling `--due`) and `sympose schedule remove` takes it away; Settings has the same two buttons. macOS only in this slice (Windows is #117).
- The open web app calls the same `due` function on a timer, so a missed run is caught up when the app is open and the Mac was asleep.
- Both go through one file lock and one last-run record per job, so the same job never runs twice. A missed time runs once when next seen, not once for each miss.

**Cost guard, on every job.** `max_runs_per_day` (default 1 for a cloud model, none for a local one), a pause after 3 failures in a row (the row shows it, the switch turns it back on), and a run for a cloud model sends only what `cloud_share` already approves. The web and media approvals apply as in chat.

**Run state** (last run, outcome, runs today, failures in a row, the held-back categories) is one small JSON file per job beside it, untracked and out of the vault.

## Consequences

- Easier: the persona can do work between visits at the price of a model call, and everything it produces is something the user Accepts or declines, as always.
- Easier: Slack (#36) reuses `jobs.run`'s headless turn.
- Harder: a persona's data folder now holds files the user writes (jobs), beside the ones the app writes; the editor route must serve `jobs/`.
- Harder: an unattended turn has no user to answer a tool that asks one (`ask`-mode skills are not built, so none today).
- Open: a run that finishes while nobody has the app open has no way to say so beyond its row and Drafts. A notification is not designed here.

## Settled with damiro (2026-10-21)

- The first mechanical kinds are `health` and `refresh`.
- A local model's runs have no daily cap.

## Settled: new notes only

- **A job drafts new notes only.** An edit proposal quotes a passage of the note open in the editor (`edit_turn.OpenNote`), and a run has no editor; the new-note tool (`edit_tools`) needs no open note. So a run can propose new notes but not changes to an existing one. A later `notes:` list in a job's front matter could open named notes for edits; not in this slice. A persona whose edit mode is `plan` proposes nothing, so its jobs only reply.

## Alternatives rejected

- **Scheduler only inside the web app.** A weekly review would run only if the app happened to be open at that moment. Right if damiro would rather have no OS integration.
- **A daemon.** Sympose is a program he opens; a background process is a new thing to start, stop and update.
- **Cloud models refused for jobs.** Simplest, but he wants cloud jobs; the caps and `cloud_share` carry the risk. Right again if a cloud run ever spends more than expected.
- **One note per job in the vault.** Visible in Obsidian, but it puts Sympose's own state in his vault.
- **Cron expressions.** Exact, but unreadable in a settings row; plain words cover the cases named. Right if a schedule is asked for that the words cannot say.
