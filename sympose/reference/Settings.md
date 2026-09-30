# Settings

Settings are stored in `settings.json`, in the folder where Sympose runs. `SYMPOSE_SETTINGS_PATH` in `.env` moves the file. The common ones can be changed with /settings in the chat, the rest by hand. Restart the chat after editing the file to be sure a change applies.

## Changing them in the chat

Type /settings for a list of the common ones, each with its value. Choose a row to change it: a true or false one flips, one with a few values moves to the next, and for a number the chat box asks for it. Enter saves, an empty line puts the default back and Esc leaves it as it was. A number that cannot be used is refused.

The list has `show_grounding`, `show_trim_notice`, `show_context_meter`, `show_background_status`, `status_typing`, `reply_reveal`, `context_window`, `reply_limit`, `grounding_followups`, `session_recaps`, `grounding_search`, `embedding_min_similarity`, `embedding_margin`, `vault_lookup` and `vault_lookup_rounds`.

`memory_remember`, `memory_rewrite` and `memory_auto_refresh` are the memory settings. The model, the persona and what a cloud model may receive have /model, /persona and /share.

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

The `context_window` setting is the size in tokens of the conversation a local model is given. By default it follows the model's own window, up to 32768. A number you set is used as your own ceiling, and a value below 2048 is raised to 2048.

## reply_limit

The `reply_limit` setting is the tokens kept back for the reply. By default a quarter of the window, up to 4096.

## reply_reveal

The `reply_reveal` setting is how fast a reply is written out in the chat, in words per second. The default is 50, and 0 shows the whole reply at once.

## cloud_helper_limit

The `cloud_helper_limit` setting is how many tokens a cloud model may use for the two small background steps, the follow-up search and the recap of a finished chat. By default 4000. Only the tokens actually used are billed, so it is a ceiling, and a value below 64 leaves the default. A local model keeps its own small limits.

## cloud_share

The `cloud_share` setting lists what a cloud model may receive from your vault: `"notes"`, `"properties"` and `"recaps"`. It is empty by default, so it receives none. Change it with /share, or edit it by hand, for example `["notes"]`. A local model always receives everything.

## show_grounding

Setting `show_grounding` to `false` hides the notes in the reply header.

## show_trim_notice

Setting `show_trim_notice` to `false` hides the notice that older turns were left out.

## show_context_meter

Setting `show_context_meter` to `false` hides the meter under the chat box.

## session_recaps

Setting `session_recaps` to `false` stops Samantha writing and reading recaps of your earlier conversations. Each recap is written by the model from your own messages, so with a cloud model those messages are sent to the provider, and only when `cloud_share` allows `"recaps"`.

## grounding_followups

Setting `grounding_followups` to `"off"` stops the extra search for follow-up questions.

## vault_lookup

The `vault_lookup` setting is who looks in your notes. `"auto"` (the default) is Sympose, before each reply. With `"ask"` Samantha decides, using tools that only read; it needs a model that can call tools, and any other model keeps `"auto"`. See How Samantha uses your notes.

## vault_lookup_rounds

The `vault_lookup_rounds` setting is how many lookups Samantha may make for one message when `vault_lookup` is `"ask"`: a whole number from 1 to 8, 3 by default.

## grounding_search

The `grounding_search` setting is how Samantha finds notes. The default, `"auto"`, matches by meaning with a small model in Ollama (`ollama pull nomic-embed-text`, once) and uses keywords when it is missing. `"keywords"`, `"embeddings"` and `"hybrid"` force one way. Meaning search can miss a note you name only by a very short title; a few more words about it help.

## How long does the first meaning search take to start?

The first time, your notes are indexed in the background (a minute or two for a big vault) and the search uses keywords until it is done; an animated line above the chat box shows it is working. The index is the cache `embedding_cache.sqlite` beside `settings.json`, safe to delete. Setting `grounding_search` to `"keywords"` skips it.

## Can the search by meaning be made faster?

Installing numpy (`pip install "sympose[fast]"`) makes each search much faster on a big vault. Nothing needs it, and it is used automatically when it is installed.

## embedding_model

The `embedding_model` setting is the embedding model used by `grounding_search`. The default is `ollama/nomic-embed-text`. Another model needs its own `embedding_min_similarity`.

## embedding_min_similarity

The `embedding_min_similarity` setting is how close in meaning a note must be to your message to be used, a number between 0 and 1. The default is 0.72, for the default embedding model. A higher number attaches fewer notes and a lower number more. A big vault usually wants a higher number than a small one.

## embedding_margin

The `embedding_margin` setting keeps only the notes that are nearly as close in meaning as the best one, so a near neighbour does not come along with the note you needed. It is a number from 0 to 1 and the default is 0.02. A larger number attaches more notes, and 1 attaches every note that reaches `embedding_min_similarity`.

## folder_definition_min_notes

The `folder_definition_min_notes` setting is how many notes a top-level folder needs before `sympose vault --health` offers it a definition note. The default is 5.

## folder_template_share

The `folder_template_share` setting is the share of a folder's notes that must carry a property for it to go into the template of the folder's definition note, a number above 0 and up to 1. The default is 0.5.

## show_background_status

Setting `show_background_status` to `false` hides the animated line directly above the chat box. It is separate from `show_context_meter`.

This line shows what is happening while you wait: a recap refresh, a memory update, or the search index build running in the background, or, while a reply is being written, whether Samantha is searching your notes, reading one, or thinking through your message.

The words are typed out one letter at a time; the `status_typing` setting is how fast, in characters per second. The default is 40, and 0 shows each phrase at once.

## memory_remember

Setting `memory_remember` to `true` lets Samantha add a line to her decisions.md when you ask her to remember something, using a tool or a marker in her reply depending on the model. Off by default. Typing /remember yourself always works regardless of this setting.

## memory_rewrite

The `memory_rewrite` setting is how a context.md update is applied: `"ask"` (the default) stages it for you to review, `"auto"` writes it directly. profile.md is always staged for review either way.

## memory_auto_refresh

Setting `memory_auto_refresh` to `true` makes Samantha check for a context.md/profile.md update on her own at launch and when you switch persona. Off by default, since unlike recaps this shares the same model your first message needs. /memory refresh always works regardless of this setting.

## How do the true or false settings work?

Only an explicit `false` turns a setting off. Anything else leaves the default.

## Which settings go in .env?

`VAULT_PATHS` (your vaults, comma separated), `SYMPOSE_PROFILES_DIR` (where persona folders live, default `./profiles`), `SYMPOSE_SETTINGS_PATH`, `OLLAMA_API_BASE` (an Ollama server that is not at the default address) and `PORT` (the port `sympose web` listens on, default 8000).
