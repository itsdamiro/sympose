# Setting up a persona in Slack

How to make a persona its own Slack user that you message like a teammate. Each persona is a Slack App of its own, so repeat the steps for every persona you want in Slack. The design is ADR 093 (`docs/decisions/093-*.md`).

**Checked against the code, not against a real workspace.** Nothing has run against a real Slack workspace yet. The Slack side below is written from Slack's documented setup and the scopes and events the code uses, and Slack may name or place a screen differently. If a step does not match what you see, trust the code's needs (the lists in steps 3 to 6) over the wording here, and fix this note.

## What you need first

- Sympose installed with its dependencies: `.venv/bin/pip install -e ".[dev]"` (this brings in `slack-bolt`).
- A Slack workspace where you may create an App.
- Your persona's handle: the name of its folder under `profiles/` (for the default persona, `samantha`).
- A model that runs: Ollama up with the persona's model pulled, or a cloud key in `.env`.

## 1. Make the Slack App

- Open https://api.slack.com/apps and choose Create New App, then From scratch.
- Name it as you want the persona to appear in Slack (for example Samantha) and pick your workspace. Slack shows this name; renaming the persona in Sympose later does not rename it in Slack.

## 2. Turn on Socket Mode and make the app token

- In the App's settings, open Socket Mode and switch it on. Sympose connects out to Slack, so there is no public address and no request URL to give anywhere.
- When asked for an App-Level Token, give it any name and the scope `connections:write`. Copy the token, which starts with `xapp-`. This is the persona's app token.

## 3. Give the bot its permissions

- Open OAuth & Permissions and, under Bot Token Scopes, add `chat:write`, `im:history`, `app_mentions:read` and `commands`.
- Sympose answers direct messages to the bot and messages that mention it in a channel. It does not read other channel messages, so it needs no channel history scope.

## 4. Subscribe to the two events

- Open Event Subscriptions and switch them on. Socket Mode means no request URL is asked for.
- Under Subscribe to bot events add `message.im` and `app_mention`.

## 5. Add the `/new` command

- Open Slash Commands and create `/new` with a short description such as "Start a new conversation". No request URL is needed with Socket Mode.
- In a direct message, `/new` starts another conversation. In a channel, write in a new thread instead.

## 6. Let people message the bot

- Open App Home, switch on the Messages Tab, and tick the option that lets users send messages and slash commands from it. Without this, Slack shows the bot with no message box.

## 7. Install it and copy the bot token

- Open Install App (or OAuth & Permissions) and choose Install to Workspace, then Allow.
- Copy the Bot User OAuth Token, which starts with `xoxb-`. This is the persona's bot token.
- If you change a scope or an event later, Slack asks you to reinstall; do, and copy the bot token again if it changed.

## 8. Find your own Slack user ID

- In Slack, open your own profile, choose the three dots, and Copy member ID. It looks like `U0123456789`.
- Only this user is answered. A message from anyone else is dropped before it reaches Sympose's engine, with no reply.

## 9. Put the tokens in `.env`

Add these lines to the `.env` beside Sympose, with the handle in capitals (a dash in a handle becomes an underscore):

```
SLACK_OWNER_USER_ID=U0123456789
SLACK_SAMANTHA_BOT_TOKEN=xoxb-...
SLACK_SAMANTHA_APP_TOKEN=xapp-...
```

- A persona needs both tokens. With only one, or none, it is not in Slack. There is no shared token that falls back for every persona, because that would make two personas one Slack user.
- `SLACK_OWNER_USER_ID` is one line for all personas.
- Keep tokens in `.env` only. Never put them in the vault, in a note, in `settings.json` or in a chat: anyone with the bot token can speak as the persona.

## 10. Switch Slack on in Sympose's settings

- A Slack reply carries note text to Slack's servers whichever model wrote it, so Slack is an approval that is off until you switch it on. It applies to every persona and to local models too.
- It is not on the Settings screen yet (that comes with slice 3). Add `"slack": true` to the settings file by hand: `settings.json` in the folder you run Sympose from, or the file `SYMPOSE_SETTINGS_PATH` names. Keep the other keys as they are, for example:

```
{
  "slack": true
}
```

- With it off, a message from you is answered with one line naming the setting, and `sympose slack` refuses to start.

## 11. Start it

```bash
sympose slack
```

- Expected: a line `samantha is in Slack.` for each connected persona, then `Slack is connected (Ctrl-C to stop).`
- It stays running in that terminal; stop it with Ctrl-C. It is not a background service yet, so start it again after a restart of the Mac.
- A persona you add later is picked up when you restart the command.
- A persona that is refused (a wrong or revoked token) is named on screen and the others carry on.

## 12. Try it

- In Slack, find the persona under Apps (or search its name) and send it a direct message. A reply is a conversation like any other: it shows in the web app's conversation list and can be opened and renamed there.
- In a channel, invite the bot first, then mention it. Each thread is one conversation; start a new thread for a new one. Anyone in the channel can read the reply, though only you are answered.
- Ask for a note, for example "write me a short note on sowing seeds". The reply shows the proposed text under it, the folder it will go to (`Inbox` in the persona's first folder unless you named one), and a line saying it waits in Drafts.
- Nothing is saved to your vault from Slack. Open the web app, find the note in Drafts, and Accept it there.

## What the persona can and cannot do in Slack

- It can propose new notes and a folder's definition. It cannot change an existing note, comment on a passage, open a note in an editor, or propose a persona or a setting, because Slack has no editor or card to show them in.
- A cloud model is held back from what the cloud approvals do not allow, as in the web chat, and a held-back notice is added under the reply.
- Files attached in Slack are not read.

## If it does not work

- **Nothing happens when you message it:** check that you used your own user ID, that `message.im` is subscribed, that the Messages Tab is on, and that `sympose slack` is still running and printed the persona as in Slack.
- **"Slack is switched off in Sympose's settings":** step 10.
- **`sympose slack` stops at once:** it names the missing piece: the owner ID in `.env`, Slack switched off, or no persona with both tokens.
- **A persona is "not connected":** the pair is wrong, revoked, or from another App. Make the app token with `connections:write` and copy the bot token after installing.
- **It does not answer in a channel:** invite the bot to the channel and mention it by name; other messages in the channel are ignored.
- **A reply says Sympose could not reach the model:** start Ollama or check the cloud key, then ask again. A note it had already filed before the failure is shown under that line.
- **To stop a persona being in Slack:** remove one of its two tokens from `.env` and restart the command, or uninstall the App from the workspace. To lock a leaked token out, regenerate it in the App's settings.
