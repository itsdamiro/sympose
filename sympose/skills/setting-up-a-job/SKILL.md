---
name: setting-up-a-job
description: Writes the file of a scheduled job, when it runs and what the persona does each time, for the user to add in Settings under Jobs. Use when the user asks to set up, create, write, change or schedule a job, or asks the persona to do something on its own every day, week or month.
---
Steps:

1. Get two things from the user's words: what to do each time, and when. If one is missing, ask for it in one sentence. Never guess a time or a task.
2. Write the schedule only in one of these forms, on the 24-hour clock and the user's own time: `daily 07:30`, `weekdays 07:30`, `weekly sun 18:00`, `monthly 1 09:00` (a day from 1 to 28), `every 6 hours` (1 to 168). Anything else ("twice a day", "every other week", "the first Monday") has no form: say so and offer the nearest one.
3. Use `kind: ask` unless the user wants a mechanical job: `health` runs the notes check and `refresh` rebuilds the search index. Those two call no model and need no prompt.
4. Leave `model`, `max_runs_per_day` and `max_waiting_drafts` out unless the user names them. Never invent a model name.
5. For `ask`, write the prompt in plain words as the user gave the task. A run can propose new notes, which wait in Drafts for the user to accept. It cannot change a note that exists: if the user wants that, say so.
6. Answer with the file as one fenced block, with `enabled: false` so it stays off until the user switches it on. After the block, one sentence on where it goes: Settings, Jobs, Add a job, open the new row with the pencil, paste the file over the template, save, then switch it On.
7. You cannot see the user's job files. To change one, ask the user to paste it, and give back the whole changed file.

Go back to step 2 and check the schedule against the list before you answer.

Example: for "every Sunday evening, list the open tasks in my journal", the answer holds

```
---
schedule: weekly sun 18:00
kind: ask
enabled: false
---
List the open tasks and loose ends in my Journal notes, and draft a weekly note with them.
```
