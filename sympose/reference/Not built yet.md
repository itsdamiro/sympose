# Not built yet

Sympose is early. These things do not exist yet, so Samantha cannot do them and should say so.

## Can Samantha write or edit my notes?

Yes, as proposals you accept. In the web app a persona can propose a change to the note you have open, a new note, and a comment on a passage. A change shows in the editor as a tracked change, and nothing reaches the file until you click Accept or save. A persona never writes to your vault on its own.

How much it does is set by `edit_mode`: `plan` (it only talks about a change), `manual` (the default: it proposes changes when you ask), `accept` (its edits are applied in the editor as it makes them, and your save keeps them) or `auto` (it may propose a change on its own, and it still waits for you).

It sees the note only when it is open in the web app's editor, and a cloud model only if you allow it with /share. Not built: deleting, moving or renaming a note, writing without your Accept, and editing from the terminal chat, where a persona can discuss a change but you review proposals in the web app.

Small models make more mistakes editing, so read each change before you accept it.

## Can Samantha do things for me?

Only a few things. She can look up your notes (`vault_lookup` `"ask"`, or by default on a tested model), add a line to her decisions file when you ask her to remember something, and in the web app propose changes, new notes and comments for you to accept or decline.

In the web app Samantha can propose a new persona, and you accept or decline it. She can also propose changing one setting, her own model, or one thing a cloud model may receive; nothing is changed until you accept. She cannot run commands or browse the web, and a few rarely used settings are still edited by hand in `settings.json`.

## Can Sympose fix the problems it finds in my notes?

No. `sympose vault --health` only reports them, and there is no health command in the chat yet. A fix is planned as a walk through the findings one note at a time, each change shown and made only when you say yes, never in bulk.

## Does Sympose work in Slack?

Not yet. Slack is planned as the first remote way to reach your vault, and Telegram or others may follow. Today Sympose is the terminal chat and the web app.

## Does Samantha remember me between conversations?

In two ways. At the start of a conversation she is given short recaps of your last conversations, written from what you said, so she can pick up where you left off. And each persona has memory files, profile.md, context.md and decisions.md, which she reads every time. She cannot browse past conversations unless you set `past_chats` to `"auto"`.

## Does Samantha review my session logs or read past conversations?

No. Every conversation is saved in `profiles/<handle>/sessions/`, but she never reads them herself. By default she gets only short recaps, so she cannot quote what was said. With `past_chats` on `"auto"`, Sympose shows her the few matching exchanges, word for word. She should never agree that she reads the logs.

## What else is missing?

The rarely used settings are still edited in `settings.json`. Skills, playbooks a persona follows, are built in a first form: the persona picks one by your message, or takes up several itself when `skill_lookup` is `"ask"` (see `skill_lookup`). A persona that changes settings for you is not built. Notes are found by meaning when the small search model is installed, and by keywords otherwise.
