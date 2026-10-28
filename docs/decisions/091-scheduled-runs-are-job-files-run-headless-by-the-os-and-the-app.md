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

**A job has one conversation (amended 2026-10-21, see "Amendment: a job keeps one conversation"; first written as a fresh conversation for each run).** `jobs.run(handle, name)` calls `run_turn` with `edits=True` and the job's model, in the session marked as the job's, so it shows in the conversation list and can be read and replied to. Whatever the persona proposes lands in Drafts; the reply stays in that conversation. The caller supplies what the web chat supplies (approvals read from the same `cloud_share`), and a run that was held back records which categories, in the job's last-run line.

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

## Settled with damiro (2026-10-21, later)

- A job conversation's recap feeds the persona's recaps like any other conversation's. `recap_refresh` scans every session and has no job filter, so nothing is built for it. The cost is one recap call for a job's conversation (the persona's own model, under the same cloud rules as any recap).

## Settled: new notes only

- **A job drafts new notes only.** An edit proposal quotes a passage of the note open in the editor (`edit_turn.OpenNote`), and a run has no editor; the new-note tool (`edit_tools`) needs no open note. So a run can propose new notes but not changes to an existing one. A later `notes:` list in a job's front matter could open named notes for edits; not in this slice. A persona whose edit mode is `plan` proposes nothing, so its jobs only reply.

## As built: running a job (slice 2, 2026-10-21)

- `job_run.run` runs one job and `run_due` every due one; `sympose run --due` and `sympose run <persona>/<job>` (a manual run) call them. A manual run ignores the schedule, the off switch and a pause, and a run that works lifts the pause; it keeps the daily cap and refuses a file with a problem.
- The cap is looked at in `run`, once the job is held (`job_state.claim`: the operating system's file lock plus a guard inside the process), together with "is it still due", so a run another process finished meanwhile is not repeated. A failed run counts as a run, so a failing job is not tried again every five minutes.
- A run's conversation carries `job: <name>` in its meta line. The web app never lands in such a conversation on a refresh (`_latest_session` skips it), and the conversation list rows say which job (`job`); showing that mark is slice 3.
- `refresh` rebuilds the search-by-meaning index through the embedder, not the chat model; with that knob on `keywords` or a cloud embedder it does nothing and says so. The persona's recaps are not part of it: opening a chat already refreshes them.
- `health` drafts a note in `Jobs/` under the persona's first folder. A second report while the first still waits is refused (a failure the row shows), as for any identical draft.
- Checked on a scratch install: `sympose run --due` made a health draft and left the vault alone; a real `gemma4:e4b` job (`ask`) took 49 s, opened a marked conversation and drafted one new note. That model put three tasks in the draft that the journal did not mention; the user reads every draft before Accept, and a bigger model is the job's own choice.
- The launchd entry and the app's timer came in slice 4 (below), and the reference-library text with them.

## As built: the Settings list (slice 3, 2026-10-21)

- Settings has a Jobs section (`jobs-rows.tsx`, rows like the Skills ones): a row for each job with its name, its schedule, how the last run went (a tick and when, or the failure and its reason, or "not run yet"), the model's mark (computer or cloud, none for a mechanical job), a pencil that opens the file in the editor, and an On/Off switch. A file with a problem shows the problem in place of the schedule. A paused job shows as Off with "Paused after 3 failures in a row", and On takes the pause off. "Add a job" makes `new-job.md` (then `new-job-2`) from a template and opens it in the editor; the template is off until the user has written what to do.
- Routes: `GET`/`POST /api/personas/{handle}/jobs` and `PUT /api/personas/{handle}/jobs/{name}` (`job_manage.py`, `server_job_handlers.py`). The switch changes only the `enabled:` property (a file with none is on) and keeps line endings and a byte-order mark; the old text goes to `<name>.md.bak`.
- The editor opens a job through ADR 061's routes: the name `jobs/<name>.md` is the one more name `persona_editable` allows (a plain job name, an existing file, saved in place with the `.bak` and the mtime check; a save never creates a job). `{name:path}` carries the slash; the pending-rewrite route is declared first so it keeps its path. The editor's strip says what a job file is, and the rows are read again after a save.
- A conversation a job opened has a clock in place of the speech bubble in the conversation list and its job's name in the detail line (a pin still wins). No new strip or card.
- Not built: a "Run now" button (`sympose run persona/job` does it). Removing a job was built later (see "As built: a job's `⋯` menu, rename and delete").
- Checked: 16 of 16 Python and 14 of 14 web mutants caught; the real app on a scratch install (the rows, the pencil, a save, the pause lifted, a new job opened, the clock in the list).

## As built: the OS entry and the app's timer (slice 4, 2026-10-21)

- `job_launchd.py` writes `~/Library/LaunchAgents/com.sympose.jobs.plist` and loads it (`launchctl bootstrap gui/<uid>`; `bootout` first, so installing again replaces the entry). The entry runs `<this Python> -m sympose.launcher run --due` every 300 seconds, from the folder `sympose` was run in (its `.env` is read as for every command), with `VAULT_PATHS`, `SYMPOSE_PROFILES_DIR` and `SYMPOSE_SETTINGS_PATH` carried over when set and when the folder's `.env` does not already give that value (so an edit of `.env` applies without installing again; a value exported in the shell that differs from `.env` is kept, as it wins in the web app too) and nothing else of the environment (no API key reaches the file). Its output goes to `~/Library/Logs/Sympose/jobs.log`. A refused load puts the previous entry back and loads it again (or deletes the file if there was none) and says why. Anywhere but macOS it refuses in one line.
- `sympose schedule install|remove|status`, and `GET`/`PUT /api/schedule` (`{supported, installed}`) behind one On/Off row in Settings → Jobs, "Run while Sympose is closed", shown only where it is supported. No new strip or card.
- `job_timer.py`: `sympose web` starts a daemon thread that calls `job_run.run_due` at once (a time missed while the app was closed or the Mac slept is caught up) and every 5 minutes after; a failed pass is logged and the thread goes on. It is started by `sympose web` only, not by `python -m sympose.main` (the development server), so `npm run dev` never runs a job. `job_state.claim` keeps the OS entry and the app from running one job twice.
- Moving Sympose (a new folder or Python) needs Off then On, or `sympose schedule install` again; the entry names the paths it was made with.
- Checked: 18 Python and 7 web tests added; 17 of 17 Python and 7 of 7 web mutants caught (one equivalent mutant of my own, a `return 0 if True else 1`, was not counted). **Found by a mutation run:** with the platform check removed a test reached the real `launchctl` and registered a service in damiro's login session (pointing at a temporary test folder); it was unloaded at once, and an autouse fixture now makes any test that has not replaced `launchctl` fail instead. Real checks on a scratch install: `schedule install` made a plist `plutil` accepts, `launchctl kickstart` ran a due `health` job (a draft in the persona's folder, the vault untouched), `remove` left no entry; in the web app on a scratch server the row loaded, On added the entry and Off removed it, and the app's timer had already run the same due job at start.
- Reference library: three entries in `The web app.md` (what a job is and that it starts off, whether jobs run while Sympose is closed, why a job stopped) and two reference cases. Retrieval `auto` 74 of 84 before (four of the five new messages failing) and 78 of 84 after, the same six failures as before; in `keywords` mode "how do I schedule a weekly meeting with my team?" now attaches the web app entry (a keyword limit; `auto` does not). The entries avoid "write", "edit" and "new notes": the first wording took `writes-notes` away from its answer (as in ADR 086).
- Not built: a notification when a run finishes with nobody watching; Windows (#117); a "Run now" button in Settings (removing a job was built later).

## As built: review fixes and the persona writing a job's file (2026-10-21)

- From `/code-review high` of slice 4: the entry no longer copies a value the `.env` file gives (it went stale against later edits, and the CLI and the web app wrote different entries); a refused reinstall no longer loses a working entry; the timer's per-job log line is gone (the outcome is in the job's own run state, which Settings shows, and the web process shows no `info` logs); the On/Off row is disabled while a change is made. `jobs.log` was not rotated then (`run --due` prints only when a job ran, so it grows slowly); see the amendment of 2026-10-28.
- **The persona helps to set up a job, by the skill `setting-up-a-job`** (ADR 077; no tool, carried by Samantha). It asks for the task and the time if either is missing, writes only the five schedule forms, leaves `model` and `max_runs_per_day` out unless the user names them, and gives the file as one block with `enabled: false`; the user adds a job in Settings, pastes it over the template, saves and switches it On. She cannot see, create or change a job file herself. `The web app.md` has an entry with the schedule forms and the properties.
- Next, not built: a confirmation card (ADR 078 and 080) so the persona files the job herself and the user clicks Accept, which amends ADR 080's "not a persona's files". It needs its own decision with damiro.

## As built: a job's `⋯` menu, rename and delete (2026-10-21)

- A job's row in Settings → Jobs has one `⋯` menu in place of the pencil: Open in the editor, Rename, Delete. The row keeps the model's mark and the On/Off switch, so the row is no wider. No new surface: rename is an inline field in the name's place (Enter commits, Esc or a click away cancels), delete asks first (`confirm`).
- Rename (`POST /api/personas/{handle}/jobs/{name}/rename`, `job_manage.rename`): what is typed becomes a file name (lower case, spaces as dashes, a trailing `.md` dropped; anything that is not letters, numbers, dashes and underscores is refused), the file, its `.bak` and its record in `.state/` move together so a pause and the last run carry over, a name that is taken is refused. The editor, if it holds that file, is pointed at the new one, after its unsaved edits are saved under the old name.
- Delete (`DELETE /api/personas/{handle}/jobs/{name}`, `job_manage.delete`): the file becomes `<name>.md.bak` (the backup a switch keeps, so the text is not lost and the list no longer shows it), its record and lock go. The editor lets go of the file. There is no Bin for it: the Bin is the vault's.
- Both are refused while a run of the job holds its claim (`job_state.claim`), with a line that says so.
- Checked: 4 Python and 5 web tests added; 5 of 5 Python and 5 of 5 web mutants caught; the menu, a rename and a delete in the real web app on a scratch install.
- Not built: a "Run now" button.

## As built: fixes from the review of slices 1 to 3

From `/code-review high` of `cd2335c~1..aa62775` (findings 1, 2 and 4; finding 3, grounding in unattended `ask` jobs, waits for damiro).

- A failure a later try may mend (an exception from the model or the disk, recorded with `retry`) is tried again after 30 minutes, and a second one after 2 hours (`job_run.RETRY_AFTER`), instead of at the job's next scheduled time. The third failure pauses the job as before. A failure of "nothing to do" (a report is waiting already) is not retried. A cloud job's daily limit still holds, so a cloud job fails once a day at most.
- A job whose record folder cannot be written is not run and the run is reported as failed (`job_state.can_record`): with no record the daily limit and the schedule could not hold, and a cloud job would run every 5 minutes.
- `monthly` and `every` read the number with `isdecimal`, so a superscript digit is refused with the usual line instead of raising in `int()` (before: `GET /jobs` answered 500 and `run_due` stopped). `run_due` also catches an error from one job's check and goes on to the next.
- Finding 3, partly (his go, 2026-10-21): a job's turn is told, in the text the model alone is sent, that it is a scheduled run, to write only what notes it searched for and opened say, to propose nothing when they say nothing, and to begin a note it proposes with "Drafted by a scheduled run from:" and the paths (`run_turn(unattended=True)`, `turn.UNATTENDED`; the search and the saved conversation keep the job's own words). A model can still ignore it, and nothing checks the paths. **Not built, and why:** failing a job whose model cannot search the vault. By default only `gemini-flash-latest` searches the vault itself (`lookup.MEASURED`); every other model, the local ones too, is grounded by Sympose's search on the job's prompt, so that rule would stop every local job at default settings. The options were (a) run a job in `ask` mode on any model that can call tools, (b) fail a job whose prompt finds no notes (rejected: the draft may already be filed by then), or (c) leave it with the line above. (a) is built and measured, see "As built: a scheduled run looks in the notes itself".
- Checked: 7 tests added (and 4 for the unattended line); 8 of 9 mutants caught, the survivor (no upper bound on the failure count in the retry check) is equivalent, because a job with 3 failures is paused first. The reference library is unchanged (it says 3 in a row switch a job off, still true).

## As built: a scheduled run looks in the notes itself (2026-10-21)

A job's turn runs in `ask` mode on any model that can call tools, whatever `vault_lookup` says (`persona_tools.resolve(..., unattended=True)`, passed from `run_turn`): the job's text is a fixed instruction, a poor search query for Sympose's own search, and nobody is there to check a draft. A model that cannot call tools falls back to `auto` as an explicit `ask` does (ADR 040), and a persona with no vault has nothing to look in. The `cloud_share` gate on what a tool returns is unchanged. The setting still governs every turn somebody is at.

Measured on `gemma4:e4b` (local, an invented vault of two plant notes and five unrelated ones, the unattended line on, 3 runs each of 4 job-style prompts, so 12 runs a mode; a sample, not a figure). `auto` (the default for that model): 2 of 12 turns looked in the notes, 2 drafts were filed, and one was invented (example tasks for "Sarah" and a "Q3 budget" with made-up source paths). `ask`: 9 of 12 looked, 1 draft was filed, with nothing invented (it says no open tasks were found, and lists no paths), and the one real review it wrote (plants and their watering and light) matched the notes line for line. Checked afterwards through the real code path with the setting left on `auto`: both runs of the review prompt looked in the notes. Limits seen: a model asked for "notes I changed this week" cannot know, since no tool shows when a note changed, and in both modes it said so rather than guessing; a question about a property (`water: weekly`) found nothing 3 of 3 in both modes (search of front matter, not a grounding fault); one reply of the checking run answered the instruction line with an acknowledgement ("Got it...") instead of the task, which the line cannot prevent on a small model. Not measured: a cloud model, a larger vault.

## Amendment (2026-10-21): a job keeps one conversation

His call, 2026-10-21: an hourly job would open 24 conversations a day, and a job that sees what it said before can build on it (a weekly review that knows last week's, a run that notices a draft is already waiting) instead of starting blind. So a run goes on in the conversation the job's last run used (`job_run._conversation`), and a new one is opened only when there is none, the user deleted it, or it is not marked as this job's (a renamed job starts a new one, labelled with its new name). It shows in the conversation list as before, with its clock, and the user can reply in it; the replies and the runs share the one file (append-only, so a run and a reply at the same moment lose nothing, they only interleave).

- **What a run carries.** The last `job_run.HISTORY_TURNS` (6) turns of the conversation word for word (`run_turn(history_turns=)`), not the 20 a chat sends, so a cloud job's cost does not grow with the months; the existing compaction (ADR 055) and the user's history limit still apply on top.
- **The risk, and the line against it.** Earlier replies are the model's own words, not the notes, and a reply that was wrong once could be repeated. `turn.UNATTENDED` now says earlier replies "are what earlier runs said, not facts about the notes: look in the notes again". Not measured on a model yet: whether a small model obeys it better or worse than before when history is present.
- **The record** keeps the job's conversation when a run has none of its own (`job_state.record`), so a failure before the conversation is found, or a switch to a mechanical kind, does not lose the thread.
- **Measured** on `gemma4:e4b` (a scratch install, an invented vault of two plant notes and four unrelated ones, a job run twice by hand with a change to a note between them; one sample, not a figure). Both runs were in the one conversation (2 turns, 1 file). With the prompt "Search my notes for the Fern and the Cactus and quote the line in each that says when to water it": run 1 quoted both lines, run 2 quoted the changed Fern line ("every Friday now") and not the earlier reply's "Tuesday". With a prompt that said "Open my note" the model called `show_note` (it shows the note to the user, it does not read it) and invented the content, in both runs, so the history did not cause it; with "Review my plant notes and tell me when each plant needs water" it found no watering lines in both runs. A job's prompt is a poor query for a small model whichever way the conversation goes. Not measured: a cloud model, a dozen runs in a row, a conversation that has been compacted.
- **Not changed:** a run still takes no part in the web chat's per-conversation lock (review finding 5), so a reply typed while a run is writing is not held back.

## Amendment (2026-10-22): the model on a job's row is a picker

The model's mark on a job's row in Settings is the same `ModelPicker` the composer and the Persona page use (ADR 044), opening below: it shows the model's short name with the on-computer or cloud mark, lists the offered models, and ends with "Use the default (the persona's model)" while the job has a model of its own. A pick calls `PUT /api/personas/{handle}/jobs/{name}/model` (`{model}` or `null`), which writes only the `model:` property of the file (`job_manage.set_model`; the backup beside it is kept as for a switch, nothing is written if the text would not change) and answers with the row. As for a persona's model, the route accepts a listed model, the one the job already has, or the persona's own, and a model with a line break is refused. The row carries a new `own_model` (what the file says, `null` when the job follows the persona), next to `model` (what a run would use). A mechanical job has no picker. Until the persona's model list is known (or if it cannot be read) the row keeps the plain mark. Nothing new on screen: the mark became the control. Not changed: the cap and the cloud rules, a cloud pick runs once a day by default as before.

## Amendment (2026-10-23): a cap on the drafts a job leaves waiting

**Decided with damiro.** A job runs with nobody there, and whatever it proposes waits in Drafts for the user's Accept. A daily job away for a week leaves seven drafts, often repeating each other, and a pile that size gets declined in bulk unread. So a job stops filing new drafts once it has a number of them waiting, until some are decided.

- **Each draft carries where it came from.** `propose_create` stamps `source` (`job:<name>`, or `slack`, ADR 093) on a draft made inside `note_changes.from_source(...)` (a thread-local, since replaced by a `Filing` passed down, see the amendment below), so the model's tool, the vault health report and the Slack turn are all tagged without a change to any call. A draft made in the web chat has no source and is never capped; neither is one that was already waiting (it has no tag). A draft is "waiting" while it is in Drafts, so Accept and Decline free the room and nothing else is kept.
- **Stop, do not replace.** `job_run.run` skips a run (`SKIPPED`, "N drafts from this job are waiting to be accepted or declined, which is the limit, so no new one was made") before the model is called when the job is at its cap, after the daily cap, so a full job costs nothing. `propose_create` also refuses at the cap (the same `CannotAnchor` a repeated draft gets, so the model is told in the tool's own error and says so in its reply), for a run that files several in one turn. Replacing the oldest was rejected: it deletes a draft the user has not read. A `refresh` job files nothing and is never held by it.
- **The numbers are settings (replaced by one setting, see the amendment below).** `job_waiting_drafts` (default 5, 1 to 100) in Settings, and `max_waiting_drafts:` in a job's own file overrides it for that job, as `max_runs_per_day` does. `slack_waiting_drafts` (default 10, 1 to 100, in the Slack group) is for all Slack drafts together: they are captures the user chose to make, so more room. A persona may propose either setting like any other.
- **Where the user sees it.** On a job's row in Settings, the existing last-run line gains the draft icon and the number of the job's drafts waiting, in the alert colour at the cap. It is counted when the list loads, so it is always true and nothing is stored. A job stopped by its cap otherwise looks like a job that broke, because "ran 3d ago" stops advancing.
- **A rename keeps the count.** `job_manage.rename` retags the drafts the job left waiting (`draft_limit.rename_job`), so a renamed job does not get a fresh allowance.

## Amendment (2026-10-23): one limit for the drafts a job or Slack leaves waiting, and where a draft's source travels

**Decided with damiro (review item 10 of the whole Slack feature, "do all in one pass").** Three knobs set one number: `job_waiting_drafts`, `slack_waiting_drafts` and `max_waiting_drafts:` in a job's file. They are now one setting, `waiting_drafts` (default 5, 1 to 100, in the Jobs group), the limit for each job and for Slack as a whole, each counted on its own. This replaces the bullet "The numbers are settings" of the amendment "a cap on the drafts a job leaves waiting".

- **Cost, his to reverse:** a job can no longer have a limit of its own, and Slack's default went from 10 to 5 (a default I chose; the one number is what the user changes). A `max_waiting_drafts:` line left in a job's file is ignored, not a problem; a value saved under the old setting names is not read. The Settings row of a job shows the one number as its limit.
- **The source no longer rides on the thread.** `note_changes.from_source` and `new_notes_made` (two thread-locals) are gone. A turn is given a `draft_limit.Filing` (`source`: `slack` or `job:<name>`, and `made`, the drafts it filed in order), passed from `run_turn` down to `propose_create` through the tool, the marker and a folder's definition, and given to the health job's report. A draft filed with no `Filing` is untagged and never counted, as a web chat's was; a tool run on another thread now lists its drafts too, which the thread-local could not.

## Amendment (2026-10-28): the jobs log is kept under a size

**Decided with damiro ("lets build it").** This replaces "Not changed: `jobs.log` is not rotated" in the review fixes. `sympose run --due` moves `jobs.log` to `jobs.log.1` (replacing an older one) when it holds more than 1 MB, before it runs the jobs. launchd opened the file before the run started, so that run's own lines go to `jobs.log.1` and the next run starts a fresh `jobs.log`: at most two files, about 2 MB and one run's output over, in all. Rotating is best-effort: a file that cannot be moved is left as it is and the jobs still run.

- **From `/code-review high` of the rotation:** the entry also carries `SYMPOSE_LOG_DIR` over when it is set, so a run finds the folder launchd writes to (without it a run looked in the default folder and the real log never rotated).
- **Cost, his to reverse:** the lines older than the previous file are gone for good. Nothing reads the log (a job's outcome is in its own run state, which Settings shows), so this loses nothing the app uses.

## Alternatives rejected

- **Scheduler only inside the web app.** A weekly review would run only if the app happened to be open at that moment. Right if damiro would rather have no OS integration.
- **A daemon.** Sympose is a program he opens; a background process is a new thing to start, stop and update.
- **Cloud models refused for jobs.** Simplest, but he wants cloud jobs; the caps and `cloud_share` carry the risk. Right again if a cloud run ever spends more than expected.
- **One note per job in the vault.** Visible in Obsidian, but it puts Sympose's own state in his vault.
- **A conversation for each run.** Simple, and no run can lean on an earlier one, but an hourly job fills the list with 24 a day. Right if reusing is seen to repeat wrong claims.
- **Cron expressions.** Exact, but unreadable in a settings row; plain words cover the cases named. Right if a schedule is asked for that the words cannot say.
