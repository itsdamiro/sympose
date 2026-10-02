# Not built yet

Sympose is early. These things do not exist yet, so Samantha cannot do them and should say so.

## Can Samantha write or edit my notes?

No. In the chat Samantha only reads your notes. She cannot write, create, edit, move or delete a note. The web app's editor is the only way to change a note, except that a folder definition note is created when you say yes, by `sympose vault --draft` or by the web app's setup step for a new folder.

## Can Samantha do things for me?

No. The only tools she has read your notes, and only when she looks herself (`vault_lookup` `"ask"`, or by default on a tested model), plus one for adding a line to her decisions file when you ask her to remember something. She cannot create a persona, change your settings, run commands or browse the web. Creating a persona and editing `settings.json` are done by hand.

## Can Sympose fix the problems it finds in my notes?

No. `sympose vault --health` only reports them, and there is no health command in the chat yet. A fix is planned as a walk through the findings one note at a time, each change shown and made only when you say yes, never in bulk.

## Does Sympose work in Slack?

Not yet. Slack is planned as the first remote way to reach your vault, and Telegram or others may follow. Today Sympose is the terminal chat and the web app.

## Does Samantha remember me between conversations?

In two ways. At the start of a conversation she is given short recaps of your last conversations, written from what you said, so she can pick up where you left off. And each persona has memory files, profile.md, context.md and decisions.md, which she reads every time. She cannot browse past conversations yet.

## Does Samantha review my session logs or read past conversations?

No, not the logs. Every conversation is saved as a session log in `profiles/<handle>/sessions/`, but she never reads them. She only gets short recaps of your last conversations, so she cannot quote what was said or search old conversations. She should say what she has and never agree that she reads the logs. Searching past conversations is planned, not built.

## What else is missing?

The rarely used settings are still edited in `settings.json`. Skills, playbooks a persona could follow, are not built. Notes are found by meaning when the small search model is installed, and by keywords otherwise.
