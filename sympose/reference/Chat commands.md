# Chat commands

The chat commands are /help, /model, /persona, /default, /grounding, /grounded, /context, /remember, /memory, /compact, /sessions, /history, /share, /settings, /clear and /quit. Type / in the chat to see them; Tab, or the Down and Up arrows, cycle through them.

## /help

/help lists the commands and then the Sympose guide: the same notes Samantha answers questions about Sympose from. Pick one to read it in the chat, or press Esc to close the list.

## /model

/model opens a picker to switch the model.

## /persona

/persona opens a picker to switch the persona.

## /default

/default makes the current persona the default one.

## /grounding

/grounding shows or hides which notes grounded each reply.

## /grounded

/grounded lists every note that grounded the last reply, with a similarity score where it was found by meaning, plus anything else that turn sent: a recap, a rewritten search, what she looked up herself when `vault_lookup` is `"ask"`, dropped turns, a cloud model's categories. It says so plainly when there is nothing to show.

## /context

/context explains the number in the meter under the chat box: the tokens in use and the space available in full, what is counted, and whether the figure is an estimate after a model switch. It says so plainly when there is no figure yet.

## /compact

/compact condenses the earlier part of a long conversation into short notes now, keeping the newest three turns as they were. It shows how many tokens that saved and what the notes say. The conversation file keeps every turn word for word. The web chat has a Condense button for the same thing.

## /sessions

/sessions, also typed as /history, lists your conversations with this persona, numbered, with the pinned ones first. /sessions open 2 continues number 2 and shows where it stopped; rename 2 New title, pin 2, unpin 2 and delete 2 work the same way. Delete moves the files to a trash folder, `sessions/.trash`, nothing is destroyed.

/sessions bin lists the deleted conversations, the Bin of the web app. /sessions restore 2 puts number 2 of that list back, and /sessions purge 2 deletes it for good.

## /remember

/remember, followed by whatever you type, saves it as a dated line in your persona's decisions.md, in your own words. No model is involved and no setting gates it — typing it always works, even with `memory_remember` off.

## /memory

/memory opens a picker. "Refresh now" asks the model to propose an update to your persona's context.md and profile.md from its recent conversation recaps, right away instead of waiting for the next launch.

If a proposal is staged for review, "Review pending change" also appears: it shows the change as a diff and asks whether to save it or discard it. profile.md changes are always staged for review; context.md follows the `memory_rewrite` setting (`ask`, the default, stages it too; `auto` writes it directly).

## /share

/share lists what a cloud model may receive from your vault (your notes, their properties, your recaps, your earlier conversations word for word) and whether each is allowed. Choose a row to allow or stop it; Esc closes the list. Nothing is allowed by default.

## /settings

/settings opens a list of the common ones, each with its value. Choose a row: a true or false one flips, and a number is typed into the chat box. Esc closes the list.

## /clear

/clear clears the transcript on screen. It is refused while a reply is being written or messages are waiting for it.

## /quit

/quit exits the chat.

## Can I send messages while she is writing?

Yes. You can keep typing and sending while a reply is being written. Messages you send while a reply is being written appear at once and wait. When that reply is done, everything that waited is sent together as one message and answered together.
