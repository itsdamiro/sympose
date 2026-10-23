# Setting up a persona in Slack

How to make a persona its own Slack user that you message like a teammate. Each persona is a Slack App of its own, so repeat the steps for every persona you want in Slack. The design is ADR 093 (`docs/decisions/093-*.md`).

**Tried once in a real workspace (direct messages).** The Slack side below is written from Slack's documented setup and its app manifest reference, and Slack may name or place a screen differently. If a step does not match what you see, trust the code's needs (the lists in step 2) over the wording here, and fix this note.

## What you need first

- Sympose installed with its dependencies: `.venv/bin/pip install -e ".[dev]"` (this brings in `slack-bolt`).
- A Slack workspace where you may create an App.
- Your persona's handle: the name of its folder under `profiles/` (for the default persona, `samantha`).
- A model that runs: Ollama up with the persona's model pulled, or a cloud key in `.env`.

## 1. Print the persona's manifest

```bash
sympose slack manifest samantha
```

- It prints the App's settings as JSON, so nothing is typed by hand in Slack. The App is named as the persona is named in Sympose (cut at Slack's 35 characters); renaming the persona later does not rename it in Slack.

## 2. Make the Slack App from it

- Open https://api.slack.com/apps, choose Create New App, then From a manifest, pick your workspace, paste the JSON and create the App.
- What the manifest asks for, and all the code needs: the bot scopes `app_mentions:read`, `chat:write`, `commands`, `files:read` and `im:history`; the bot events `app_mention` and `message.im`; the slash command `/new`; Socket Mode on (Sympose connects out to Slack, so there is no public address and no request URL); the Messages tab of App Home on, with users allowed to message the bot.
- It does not ask to read other channel messages, because Sympose answers only direct messages and mentions. `files:read` is only so a file you share with a message to the persona can be downloaded. Interactivity is on (no request URL is needed in Socket Mode) so the Accept and Decline buttons under a proposed note work.
- An App made before files were supported: add `files:read` under OAuth & Permissions, reinstall the App (step 4), and copy the bot token again if it changed.
- An App made before the Accept and Decline buttons: switch Interactivity on under Interactivity & Shortcuts in the App's settings (Socket Mode needs no request URL), or paste the new manifest. Until then a press gets Slack's own "not configured" warning and nothing is saved.
- If Slack rejects the manifest, say which line and fix `sympose/slack_manifest.py` from what Slack says.

## 3. Make the app token

- In the App's settings, open Basic Information, then App-Level Tokens, and generate one with the scope `connections:write`. Give it any name.
- Copy the token, which starts with `xapp-`. This is the persona's app token.

## 4. Install it and copy the bot token

- Open Install App and choose Install to Workspace, then Allow.
- Copy the Bot User OAuth Token, which starts with `xoxb-`. This is the persona's bot token.
- If you change a scope or an event later, Slack asks you to reinstall; do, and copy the bot token again if it changed.

## 5. Find your own Slack user ID

- In Slack, open your own profile, choose the three dots, and Copy member ID. It looks like `U0123456789`.
- Only this user is answered. A message from anyone else is dropped before it reaches Sympose's engine, with no reply.

## 6. Put the tokens in `.env`

Add these lines to the `.env` beside Sympose, with the handle in capitals (a dash in a handle becomes an underscore):

```
SLACK_OWNER_USER_ID=U0123456789
SLACK_SAMANTHA_BOT_TOKEN=xoxb-...
SLACK_SAMANTHA_APP_TOKEN=xapp-...
```

- A persona needs both tokens. With only one, or none, it is not in Slack. There is no shared token that falls back for every persona, because that would make two personas one Slack user.
- `SLACK_OWNER_USER_ID` is one line for all personas.
- Keep tokens in `.env` only. Never put them in the vault, in a note, in `settings.json` or in a chat: anyone with the bot token can speak as the persona.

## 7. Switch Slack on in Sympose's settings

- A Slack reply carries note text to Slack's servers whichever model wrote it, so Slack is an approval that is off until you switch it on. It applies to every persona and to local models too.
- In the web app open Settings, find the Slack section and switch it on. In the terminal chat it is the `slack` row of `/settings`. A persona cannot ask you to switch it on: it is not among the settings a persona may propose.
- With it off, a message from you is answered with one line naming the setting, and `sympose slack` refuses to start.

## 8. Check it

```bash
sympose doctor
```

- It names what is still missing: a persona with only one token, a token for a persona that does not exist, no owner ID, or Slack still switched off. For each persona that has both tokens it also says whether it is connected now, which is only true while `sympose slack` is running.

## 9. Start it

```bash
sympose slack
```

- Expected: a line `samantha is in Slack.` for each connected persona, then `Slack is connected (Ctrl-C to stop).`
- While a persona is connected, the web app's Persona page shows a green dot labelled Slack. It goes out within about a minute of the command stopping.
- It stays running in that terminal; stop it with Ctrl-C. It is not a background service yet, so start it again after a restart of the Mac.
- A persona you add later is picked up when you restart the command.
- A persona that is refused (a wrong or revoked token) is named on screen and the others carry on.

## 10. Try it

- In Slack, find the persona under Apps (or search its name) and send it a direct message. A reply is a conversation like any other: it shows in the web app's conversation list and can be opened and renamed there. `/new` in a direct message starts another conversation.
- In a channel, invite the bot first, then mention it. Each thread is one conversation; start a new thread for a new one. Anyone in the channel can read the reply, though only you are answered.
- Ask for a note, for example "write me a short note on sowing seeds". The reply shows the proposed text under it, the folder it will go to (`Inbox` in the persona's first folder unless you named one), and a line saying it waits in Drafts.
- Under a note shown in full, a short message asks `Save <name> to <folder>?` with Accept and Decline. Accept saves the note in that folder, named by its title (numbered if the name is taken); Decline forgets it; the message then becomes one line saying which. Only you can press them, even in a channel. A note that was cut, or only named, has no buttons: read and accept it in the web app under Drafts.
- Nothing is saved to your vault until you accept: a note proposed from Slack waits in Drafts until you press Accept here or in the web app.

## What the persona can and cannot do in Slack

- It can propose new notes and a folder's definition. It cannot change an existing note, comment on a passage, open a note in an editor, or propose a persona or a setting, because Slack has no editor or card to show them in.
- A cloud model is held back from what the cloud approvals do not allow, as in the web chat. Slack replies do not say what was held back; the web chat's cloud icon does.
- A PDF, image, sound or video shared with a message is read like one attached in the web chat: the `media` approval, the models that can read files and the limits (3 files, 50 MB together) are the same, and the file is held in memory for the next few messages and kept nowhere else. A type it cannot read, too many or too large files, or a missing `files:read` permission is answered in one line and nothing else happens. A message with only a file and no words is answered too.

## If it does not work

- **You are not sure whether a message arrived:** `sympose slack` prints one line in its terminal for each message it receives, with the time and the persona, never the words. No line means Slack never delivered it (a connection that dropped, a message in a place the bot is not in); a press of Accept or Decline under a note has lines too: `button pressed (accept)`, then `saved`, `declined`, `no longer waiting, said so` or `could not be saved, said so`, and with no line at all Slack never sent the press (Interactivity off); `ignored, not from the owner` means the user ID in `.env` is not yours; `the files could not be taken, said so` means a file was refused (the reply in Slack says why); `the reply could not be sent` or `the answer failed` mean it arrived and failed, and the lines under it say why.
- **Nothing happens when you message it:** run `sympose doctor`; check that you used your own user ID, that the Messages tab is on, and that `sympose slack` is still running and printed the persona as in Slack.
- **"Slack is switched off in Sympose's settings":** step 7.
- **`sympose slack` stops at once:** it names the missing piece: the owner ID in `.env`, Slack switched off, or no persona with both tokens.
- **`sympose: command not found`:** the command lives in the project's virtual environment. Run `source .venv/bin/activate` in the project's folder first, or call `.venv/bin/sympose`.
- **A persona is "not connected":** the pair is wrong, revoked, or from another App. Make the app token with `connections:write` and copy the bot token after installing.
- **It does not answer in a channel:** invite the bot to the channel and mention it by name; other messages in the channel are ignored.
- **A file gets a reply about `files:read`:** the App cannot download files. Add the `files:read` bot scope under OAuth & Permissions, reinstall the App, copy the bot token into `.env` if it changed, restart `sympose slack`, and send the file again.
- **The Slack dot is missing though it is connected:** the dot is read from a small file `sympose slack` refreshes every 20 seconds in the persona's folder, so it can lag by a minute; it only shows on the Persona page.
- **A reply says Sympose could not reach the model:** start Ollama or check the cloud key, then ask again. A note it had already filed before the failure is shown under that line.
- **A new display name or picture does not show:** both are set in Slack (Basic Information, Display Information, for the App icon; App Home, Your App's Presence in Slack, for the bot's Display Name). Reinstall the App (Install App, Reinstall to Workspace), restart the Slack app on your computer, which caches them, and if the bot token changed, copy it into `.env` and restart `sympose slack`.
- **To stop a persona being in Slack:** remove one of its two tokens from `.env` and restart the command, or uninstall the App from the workspace. To lock a leaked token out, regenerate it in the App's settings.
