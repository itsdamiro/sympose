# Slack

## Does Sympose work in Slack?

Yes. A persona can be its own Slack user that you message like a colleague, in a direct message or by mentioning it in a channel. A command called `sympose slack` runs on your computer and connects out to Slack, so there is no public address to expose. A persona answers only while that command is running.

It is new: it follows Slack's documented setup but has not yet been tried in a real workspace, so a Slack screen may differ from the steps.

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

A persona can make a note from Slack, as a proposal: the reply shows the whole text, the folder and a line saying it waits in Drafts. Nothing is saved from Slack; you Accept the note in the web app, on your computer. It cannot change a note, comment, open a note or propose a persona or a setting, and a file attached in Slack is not read.

## What does /new do in Slack?

In a direct message to the persona, `/new` starts a fresh chat; until then a direct message is one long chat. In a channel, write in a new thread, because each thread is a chat of its own. Each one also shows in the web app's list, where you can open, rename or archive it.

## How do I know a persona is connected to Slack?

The Persona page in the web app shows a green dot labelled Slack while `sympose slack` has that persona connected, and nothing when it does not. So a persona with no Slack App, or a stopped command, shows no dot.

`sympose doctor` lists each persona that has both tokens as connected or not connected, and names what is missing for the ones that cannot connect.
