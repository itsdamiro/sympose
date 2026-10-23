# Settings

Settings are stored in `settings.json`, in the folder where Sympose runs. `SYMPOSE_SETTINGS_PATH` in `.env` moves the file. The common ones can be changed with /settings in the chat, the rest by hand. Restart the chat after editing the file to be sure a change applies.

## Changing them in the chat

Type /settings for a list of the common ones, each with its value. Choose a row to change it: a true or false one flips, one with a few values moves to the next, and for a number the chat box asks for it. Enter saves, an empty line puts the default back and Esc leaves it as it was. A number that cannot be used is refused.

The list has `show_grounding`, `show_trim_notice`, `show_context_meter`, `show_background_status`, `status_typing`, `reply_reveal`, `context_window`, `reply_limit`, `history_tokens`, `model_timeout`, `grounding_followups`, `session_recaps`, `recap_count`, `recap_chars` and `past_chats`.

It also has `grounding_search`, `embedding_min_similarity`, `embedding_margin`, `library_sync_limit`, `vault_lookup`, `vault_lookup_rounds`, `auto_compact`, `compact_at`, `compact_to` and `parallel_replies`.

`edit_mode`, `show_note_marker`, `open_note_cap` and `annotations_cap` are the editing settings. `memory_remember`, `memory_rewrite` and `memory_auto_refresh` are the memory settings. The model, the persona and what a cloud model may receive have /model, /persona and /share.

## Can Samantha change a setting for me?

In the web app, yes, as a proposal. Ask for what you want, such as faster replies or no notes sent to a cloud model, and she shows a card with the setting and the change. Nothing changes until you accept. It works for the settings in /settings, for her own model, and for one thing a cloud model may receive at a time. It needs a model that can call tools.

## Where are my settings stored?

In `settings.json`, in the folder where you run Sympose, or wherever `SYMPOSE_SETTINGS_PATH` points.

## active_vault

The `active_vault` setting is the vault in use. It is set by the web app's workspace switcher.

## added_vaults

The `added_vaults` setting holds the vaults you added from the web app's workspace switcher.

## chat_model

The `chat_model` setting is the model used when no persona or `/model` pick decides otherwise. The default is `ollama_chat/gemma2:9b`.

## default_persona

The `default_persona` setting is the persona Sympose starts with. It is set by `/default`.

## context_window

The `context_window` setting is the size in tokens of the conversation a local model is given. By default it follows the model's own window, up to 32768. A number you set is used as your own ceiling, and a value below 2048 is raised to 2048. A persona can have its own `context_window` in its `persona.yaml`; that wins over this setting for that persona.

## reply_limit

The `reply_limit` setting is the tokens kept back for the reply. By default a quarter of the window, up to 4096. A persona can have its own `reply_limit` in its `persona.yaml`; that wins over this setting for that persona.

## history_tokens

The `history_tokens` setting is the most tokens of the earlier conversation sent with each message, word for word, at least 500; empty means no cap. The oldest turns are left out until the rest fits, and the newest always stays. It makes replies start sooner on a slow computer and costs less on a cloud model, but what is left out is forgotten, not condensed, so `auto_compact` rarely starts.

## model_timeout

The `model_timeout` setting is the most seconds a model may take to answer before Sympose gives up, 30 to 3600. Empty means automatic: 120 seconds plus one for every 40 tokens of the prompt. A cold start of a local model can take over a minute, so raise it if you see "No answer from" on a slow machine.

## reply_reveal

The `reply_reveal` setting is how fast a reply is written out in the chat, in words per second. The default is 50, and 0 shows the whole reply at once.

## cloud_helper_limit

The `cloud_helper_limit` setting is how many tokens a cloud model may use for the two small background steps, the follow-up search and the recap of a finished chat. By default 4000. Only the tokens actually used are billed, so it is a ceiling, and a value below 64 leaves the default. A local model keeps its own small limits.

## cloud_share

The `cloud_share` setting lists what a cloud model may receive from your vault, one kind at a time. It is empty by default, so a cloud model receives none. Change it with /share, or edit it by hand, for example `["notes"]`. A local model always receives everything.

The kinds are `"notes"` (passages found for a message), `"properties"`, `"recaps"`, `"chats"` (earlier conversations word for word), `"vault_map"` (folder names, purposes and note counts) and `"connections"` (how a note links to others).

Also `"memory"` (the persona's own memory of you), `"open_note"` (the text of the note open in the editor, which lets a persona propose changes to it) and `"annotations"` (your open comments on that note).

Also `"web"`: the links in your messages, which Google opens for the persona, and what it searches for (see `web_access`).

Also `"media"`: the PDFs, images, sounds and videos you attach to a message, which Google reads for the persona. When a kind is held back the persona is told it was not sent, and how to allow it.

## show_grounding

Setting `show_grounding` to `false` hides the notes in the reply header.

## show_trim_notice

Setting `show_trim_notice` to `false` hides the notice that older turns were left out.

## show_context_meter

Setting `show_context_meter` to `false` hides the meter under the chat box.

## session_recaps

Setting `session_recaps` to `false` stops Samantha writing and reading recaps of your earlier conversations. Each recap is written by the model from your own messages, so with a cloud model those messages are sent to the provider, and only when `cloud_share` allows `"recaps"`.

The call that writes a recap also gives a conversation a short title, unless you have already renamed it yourself: a title you chose is never replaced. Conversations that were opened and never used are deleted at the next launch after a day.

## recap_count and recap_chars

The `recap_count` setting is how many recaps of earlier conversations she reads, 1 to 10, 2 by default. The `recap_chars` setting is how much of each she reads, 200 to 2000 characters, 800 by default. More of either gives her a longer memory of past chats and takes room in every prompt, so a small local model may need less.

## past_chats

The `past_chats` setting lets her look in your earlier conversations, word for word. It is `"off"` by default, which means recaps only. With `"auto"`, before each reply Sympose looks for the few exchanges of earlier conversations that match your message and shows them to her, with her own old replies marked as hers and possibly wrong.

With `"ask"` she gets two tools, one to search earlier conversations and one to read one in full, and decides herself; it needs a model that can call tools, and any other runs `"auto"`. `"auto"` suits small local models, which rarely search on their own; `"ask"` suits capable cloud models. A cloud model gets them only if `cloud_share` allows `"chats"`.

A small local model can repeat something she once made up, so check what she says when you use `past_chats`.

## grounding_followups

Setting `grounding_followups` to `"off"` stops the extra search for follow-up questions.

## vault_lookup

The `vault_lookup` setting is who looks in your notes. `"by_model"` (the default) lets Samantha look herself on models that were tested for it, today Gemini Flash, and leaves Sympose to search before each reply on the others. `"auto"` always has Sympose search. `"ask"` always lets her decide, with tools that only read; it needs a model that can call tools, and any other keeps `"auto"`.

## vault_lookup_rounds

The `vault_lookup_rounds` setting is how many lookups Samantha may make for one message when `vault_lookup` is `"ask"`: a whole number from 1 to 8, 3 by default.

## auto_compact

The `auto_compact` setting, on by default, condenses a long conversation by itself: after a reply that leaves the prompt nearly full, the oldest turns are replaced by short notes written by the model in use from your own messages. Without it the oldest turns are dropped silently. /compact works either way. A cloud model is asked to write the notes, which costs one small call.

## compact_at and compact_to

The `compact_at` setting is how full the prompt is, in percent of its budget, when `auto_compact` starts, 80 by default. The `compact_to` setting is how full it is left, 40 by default, always below `compact_at`. Both are whole numbers from 10 to 95. Condensing in one big step keeps the start of the prompt the same for several turns, so a local model replies faster.

## grounding_search

The `grounding_search` setting is how Samantha finds notes. The default, `"auto"`, matches by meaning with a small model in Ollama (`ollama pull nomic-embed-text`, once) and uses keywords when it is missing. `"keywords"`, `"embeddings"` and `"hybrid"` force one way. Meaning search can miss a note you name only by a very short title; a few more words about it help.

## How long does the first meaning search take to start?

The first time, your notes are indexed in the background (a minute or two for a big vault) and the search uses keywords until it is done; an animated line above the chat box shows it is working. The index is the cache `embedding_cache.sqlite` beside `settings.json`, safe to delete. Setting `grounding_search` to `"keywords"` skips it.

## Can the search by meaning be made faster?

Installing numpy (`pip install "sympose[fast]"`) makes each search much faster on a big vault. Nothing needs it, and it is used automatically when it is installed.

## embedding_model

The `embedding_model` setting is the embedding model used by `grounding_search`. The default is `ollama/nomic-embed-text`. Another model needs its own `embedding_min_similarity`.

Others that work, with a number to start from: `ollama/all-minilm` (very small, for a computer short of room) 0.64, `ollama/bge-m3` 0.68, `ollama/mxbai-embed-large` 0.74, and `gemini/gemini-embedding-001` 0.76, a cloud model, so passages of your notes leave your computer and only if you allow notes for cloud models with /share.

`ollama/embeddinggemma` brought more notes that did not belong and is not recommended. These numbers are starting points from two small vaults: raise one if you get notes that have nothing to do with what you ask, lower it if she misses notes.

## library_sync_limit

The `library_sync_limit` setting is how many of the help passages Sympose may prepare for searching by meaning at once, the first time they are needed. The default is 512, enough for the whole built-in help.

Below the help's size, about 260, the first questions about Sympose are answered by keyword search until a background build finishes. A bigger number never hurts the search; it only makes that first preparation, a few seconds once, happen while you wait.

## embedding_min_similarity

The `embedding_min_similarity` setting is how close in meaning a note must be to your message to be used, a number between 0 and 1. The default is 0.72, for the default embedding model. A higher number attaches fewer notes and a lower number more. A big vault usually wants a higher number than a small one.

## embedding_margin

The `embedding_margin` setting keeps only the notes that are nearly as close in meaning as the best one, so a near neighbour does not come along with the note you needed. It is a number from 0 to 1 and the default is 0.02. A larger number attaches more notes, and 1 attaches every note that reaches `embedding_min_similarity`.

## connections_by_meaning

The `connections_by_meaning` setting decides whether Sympose finds notes close in meaning to a note. `"auto"`, the default, finds them from the passages already indexed for search, with no extra model call; `"off"` finds none.

Samantha is told of them on a separate line, "possibly related", as a guess from the text. The web app's notes panel lists them under Related notes. A cloud model is told only if `cloud_share` allows `"connections"`.

## connections_relevance

The `connections_relevance` setting is how close in meaning a note must be to count as possibly related: `"close"` keeps few, nearly all clearly related, `"balanced"` (the default) is right about 85 to 89% of the time, and `"wide"` lets looser ones in.

The same level decides what Samantha is told and what the notes panel lists. It is a level and not a number because the right number depends on the embedding model.

## folder_definition_min_notes

The `folder_definition_min_notes` setting is how many notes a top-level folder needs before `sympose vault --health` offers it a definition note. The default is 5.

## folder_template_share

The `folder_template_share` setting is the share of a folder's notes that must carry a property for it to go into the template of the folder's definition note, a number above 0 and up to 1. The default is 0.5.

## show_background_status

Setting `show_background_status` to `false` hides the animated line directly above the chat box. It is separate from `show_context_meter`.

This line shows what is happening while you wait: a recap refresh, a memory update, or the search index build running in the background, or, while a reply is being written, whether Samantha is searching your notes, reading one, or thinking through your message.

The words are typed out one letter at a time; the `status_typing` setting is how fast, in characters per second. The default is 40, and 0 shows each phrase at once.

## parallel_replies

The `parallel_replies` setting decides whether replies in different conversations of one persona are written at the same time. `auto`, the default, does it on a cloud model, where it costs no speed, and one after the other on a local model, whose graphics chip and memory they would share. `on` always runs them together (Ollama must allow it) and `off` always one at a time.

A message waiting for its turn says so, and Stop cancels it. Two messages in the same conversation always run in order.

## memory_remember

Setting `memory_remember` to `true` lets Samantha add a line to her decisions.md when you ask her to remember something, using a tool or a marker in her reply depending on the model. Off by default. Typing /remember yourself always works regardless of this setting.

## memory_rewrite

The `memory_rewrite` setting is how a context.md update is applied: `"ask"` (the default) stages it for you to review, `"auto"` writes it directly. profile.md is always staged for review either way.

## memory_auto_refresh

Setting `memory_auto_refresh` to `true` makes Samantha check for a context.md/profile.md update on her own at launch and when you switch persona. Off by default, since unlike recaps this shares the same model your first message needs. /memory refresh always works regardless of this setting.

## edit_mode

The `edit_mode` setting is what a persona does with your notes before your Accept: `"plan"` (it only talks about a change), `"manual"` (the default: it proposes tracked changes when you ask, and you accept or decline each), `"accept"` (its edits are applied in the editor as it makes them, and your save keeps them) or `"auto"` (it may propose a change on its own).

In every mode the file changes only when you click Accept or save. A persona can have its own `edit_mode` in its `persona.yaml` or in `persona.local.yaml`; that wins over this setting. This is the web app only.

## show_note_marker

The `show_note_marker` setting lets a model that cannot call tools, such as gemma2:9b, open a note in the web app's editor when you give it the note's name or path, off by default. Turned on, that model is told how to ask for a note to be shown, which costs it some of its edits. A model that can call tools opens notes without it.

## open_note_cap

The `open_note_cap` setting is how many characters of the open note a persona is sent with your message, 12000 by default (20 or more). A longer note is cut at the cap. The note is sent only when it is open in the web app's editor, and to a cloud model only if `"open_note"` is allowed in `cloud_share`.

## annotations_cap

The `annotations_cap` setting is how many of your open comments on the open note travel with one message, 20 by default (1 or more). Each comment is sent with the passage it is about and is marked new or earlier. To a cloud model they travel only if `"annotations"` is allowed in `cloud_share`.

## skill_lookup

The `skill_lookup` setting decides whether a persona follows a skill: `"auto"` (the default) picks the skill whose description fits your message, if there is one, and adds its steps to that message; `"off"` never does.

A skill is a folder with a `SKILL.md` that says what it does and the steps to follow. It is only text: nothing in it is ever run. In Settings, under Skills, every skill a persona could carry has a switch, and a persona follows only the skills that are on; Samantha starts with the bundled ones on.

To add a skill of your own, paste the full path of its folder in the same place. Sympose copies its `SKILL.md` (nothing else in the folder) into the persona's profile, turned off, and opens it so you can read it before you turn it on. A skill of your own goes only to a model on your computer, never to a cloud model.

To delete a skill you added, use the bin beside it in Settings, or /skills remove in the terminal; both ask first, and it cannot be undone. A skill that ships with Sympose can only be turned off. In the terminal, /skills also switches skills and adds them.

A skill that needs to propose a note is not used where the persona cannot propose notes: in the terminal, or when its `edit_mode` is `"plan"`. The skill that drafts a new note in a folder's style also needs a model that calls tools itself; a model that does not (the default local `gemma2:9b`) is not given it, and answers as it always did.

The skills that make a note from a video or a web page you linked (`capturing-from-a-link`, `capturing-from-a-page`) are not picked by your words: a message that watches a video or reads a page is given one, and it applies only when you ask for a note. So is `capturing-from-a-file`, for a file you attached.

## skill_cap

The `skill_cap` setting is the most characters of a skill's steps that go with one message, 3000 by default (500 or more). Longer steps are cut at a line. A smaller number suits a small model.

## web_access

The `web_access` setting decides whether a link you share is opened. `"asked"`, the default, opens a YouTube video or a web page when your message has its link, and keeps it in front of the persona for your questions about it afterwards. `"auto"` also lets the persona search the web by herself on every turn. `"off"` never does.

Gemini Flash watches the video, reads the page and searches: the link is sent to Google, and the persona sees what is shown as well as what is said.

Every other model, one on your computer included, is given a video's captions instead, fetched from YouTube by your computer, and cannot read a page or search. The same captions stand in when Google will not take a video.

All of it needs `"web"` allowed under `cloud_share`. When a search backs a sentence of the reply, the sentence is followed by numbered links to the pages, and a note made from it lists them as its source. What comes from the web is marked as outside your notes, and a turn that uses it cannot save anything to the persona's memory. Addresses that only your own network knows are never sent.

With captions the persona cannot see what is shown and not said, and a very long video is cut, with the persona saying where it stops. A video with no captions, or one YouTube will not hand out, cannot be read this way, and the persona says so and why.

With a cloud model, `"web"` must be allowed in `cloud_share`, which it is not until you allow it with /share or in Settings under Cloud models; the link goes to Google, or the captions go to the model's maker. Without that permission she says she could not open the link, and how to allow it. A model on your computer needs no permission.

A video costs more than a message: with Gemini Flash each question that needs the video makes Google look at it again, and with captions they ride with every message while the conversation is about the video. What a persona says about a video comes from the video and not from your notes. In a message with a video link it does not add anything to its memory.

A note made from a video is a proposal that waits for your Accept, like any other. Ask for one: a link or a summary alone files nothing. The note has the video's address in its properties, and the times in its outline are links to that moment of the video.

## slack

The `slack` setting switches Slack on. It is off by default, for every persona and every model, because a Slack reply leaves your computer whichever model wrote it. Set it in Settings (the Slack section) or as the `slack` row of /settings.

While it is off, `sympose slack` will not start and a message in Slack is answered with one line naming this setting. A persona cannot propose switching it on; only you can. See the Slack page.

## waiting_drafts

A job or Slack that nobody watches could leave a pile of drafts. `waiting_drafts` is how many each may leave waiting before it stops making new ones: 5 unless you change it, for each scheduled job and for Slack as a whole, each counted on its own. It is a whole number from 1 to 100; set it in Settings, under Jobs.

Accepting or declining a draft makes room again; nothing is deleted for you. A draft you asked for in the chat is never counted.

## How do the true or false settings work?

Only an explicit `false` turns a setting off. Anything else leaves the default.

## Which settings go in .env?

`VAULT_PATHS` (your vaults, comma separated), `SYMPOSE_PROFILES_DIR` (where persona folders live, default `./profiles`), `SYMPOSE_SETTINGS_PATH`, `OLLAMA_API_BASE` (an Ollama server that is not at the default address) and `PORT` (the port `sympose web` listens on, default 8000).
