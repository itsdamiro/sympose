# Slack

## Does Sympose work in Slack?

Yes. A persona can be its own Slack user that you message like a colleague, in a direct message or by mentioning it in a channel. A command called `sympose slack` runs on your computer and connects out to Slack, so there is no public address to expose. A persona answers only while that command is running.

Slack may label or arrange a screen differently from the steps here.

## How do I set up a persona in Slack?

Each persona is a Slack App you make once. Run `sympose slack manifest samantha` (with the persona's handle) to print the App's settings, and paste them into Slack's "create an app from a manifest". Make an app token with the scope `connections:write`, install the App, and copy its bot token.

Then put `SLACK_OWNER_USER_ID` (your own Slack user ID), `SLACK_<HANDLE>_BOT_TOKEN` and `SLACK_<HANDLE>_APP_TOKEN` in `.env`, switch Slack on in Settings, run `sympose doctor` to see what is still missing, and run `sympose slack`. The full steps are in `docs/SLACK_SETUP.md`.

## Who is answered in Slack?

Only you. Sympose answers the one Slack user whose ID is in `SLACK_OWNER_USER_ID`, and a message from anyone else is dropped with no reply.

## Why does a persona say Slack is switched off?

Slack is off until you switch it on, in Settings or as the `slack` row of /settings. It is one switch for every persona and every model. While it is off, a message from you is answered with one line that names the setting, and `sympose slack` will not start. A persona cannot switch it on for you.

## Does Slack get my notes?

Slack gets what a persona says. A reply can quote your notes, and it is sent to Slack's servers whichever model wrote it, even one on your own computer, so `slack` is off by default. Everyone in a channel can read a reply there; a direct message is between you and the persona. A cloud model is still held back from what the cloud approvals do not allow.

## Can a persona make a note from Slack?

A persona can make a note from Slack, as a proposal: the reply shows the whole text, the folder and a line saying it waits in Drafts. Nothing is saved until you accept it, with the buttons under it in Slack or in the web app. It cannot change a note, comment, open a note or propose a persona or a setting.

Once 10 notes made from Slack are waiting, it makes no more and says so in its reply. The `slack_waiting_drafts` setting changes the 10.

## How do I accept or decline a note in Slack?

Under a note shown in full, a short message asks to save it, with Accept and Decline. Accept saves it in the folder named, under its title; Decline forgets it. Either way the message becomes one line saying which. Only you can press them, even in a channel.

A note that was cut, or only named, has no buttons: read and accept it in the web app, under Drafts.

## Pressing Accept in Slack does nothing, why?

If Slack warns that the app is not configured, the App was made before the buttons. Switch Interactivity on under Interactivity & Shortcuts in the App's settings, or paste the manifest again, then press once more. If the line says the draft is not waiting any more, it was decided already, in the web app or by an earlier press.

## Can I send a file to a persona in Slack?

Yes. Share a PDF, image, sound or video with your message and the persona reads it as in the web chat: the `media` approval, a model that can read files and the same limits (3 files, 50 MB together) apply, and the file is kept in memory only. A file Sympose cannot read is answered with one line saying why.

If the line mentions `files:read`, the Slack App cannot download files. Add that bot scope under OAuth & Permissions, reinstall the App, copy the bot token into `.env` if it changed, restart `sympose slack` and send the file again.

## What does /new do in Slack?

In a direct message to the persona, `/new` starts a fresh chat; until then a direct message is one long chat. In a channel, write in a new thread, because each thread is a chat of its own. Each one also shows in the web app's list, where you can open, rename or archive it.

## How do I know a persona is connected to Slack?

The Persona page in the web app shows a green dot labelled Slack while `sympose slack` has that persona connected, and nothing when it does not. So a persona with no Slack App, or a stopped command, shows no dot.

The dot can lag by up to a minute, and it shows on the Persona page only.

## What do the Slack lines of sympose doctor mean?

`sympose doctor` lists each persona that has both tokens and says whether it is in Slack right now, and names what is missing for the ones that cannot join.

The line "not connected (is `sympose slack` running?)" means the command is not running, or it is running and Slack refused the tokens: wrong, revoked, or from another App.

A persona with only one of its two tokens is not in Slack until the other is added to `.env`. A token whose handle matches no persona is ignored. Without `SLACK_OWNER_USER_ID`, or with the `slack` setting off, `sympose slack` will not start.

## Slack does not answer me, what do I check?

Run `sympose doctor` first, because it names most of the causes. Then check that `sympose slack` is running in a terminal and printed the persona as in Slack: it stops when that terminal closes or the Mac restarts.

Check that Slack is switched on in Settings, and that `SLACK_OWNER_USER_ID` in `.env` is your own Slack user ID, because a message from anyone else is dropped with no reply.

In the App's settings the Messages tab of App Home must be on. In a channel, invite the bot and mention it by its name; other messages there are ignored.

If the reply says Sympose could not reach the model, start Ollama or check the cloud key and ask again. If the App was reinstalled or a token regenerated, copy the fresh bot token into `.env` and restart `sympose slack`.

## Did my Slack message arrive?

`sympose slack` prints one line in its terminal for each message it receives, with the time and the persona, never the words. No line means Slack never delivered it, and a press of Accept or Decline has its own lines. `ignored, not from the owner` means the user ID in `.env` is not yours. `the answer failed` or `the reply could not be sent` mean it arrived and failed.

## Why did Slack refuse my file?

`sympose slack` prints `the files could not be taken, said so` when a file you shared was refused, and the reply in Slack says why: a type it cannot read, too many or too large files, or the App missing the `files:read` permission.

## How do I change the Slack bot's display name or picture?

The display name and the picture are set in Slack, not in Sympose, and Sympose never reads them back. At api.slack.com/apps open the App: Basic Information, then Display Information, holds the App icon (the picture: a square image, 512 to 2000 pixels). The display name shown on its messages is the bot name, under App Home, Your App's Presence in Slack, Display Name (Bot Name); save it there.

If a change does not show, reinstall the App (Install App, Reinstall to Workspace) and restart the Slack app on your computer, which keeps old names and pictures for a while. Older messages may keep the old one. A reinstall can give the bot a different token: if so, copy it into `.env` and restart `sympose slack`.

## How do I take a persona out of Slack, or lock out a leaked token?

To stop a persona being in Slack, remove one of its two tokens from `.env` and restart `sympose slack`, or uninstall the App from the workspace.

To lock out a token that leaked, regenerate it in the App's settings (the bot token under Install App, the app token under Basic Information) and put the replacement in `.env`. Keep tokens in `.env` only: never in a note, a setting or a chat.
