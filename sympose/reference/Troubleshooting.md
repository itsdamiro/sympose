# Troubleshooting

## It says it cannot connect to the model

Make sure Ollama is running (open the Ollama app, or run `ollama serve`) and that the default model is pulled with `ollama pull gemma2:9b`. If Ollama runs at another address, set `OLLAMA_API_BASE` in `.env`. For a cloud model, check that its API key is set in `.env`.

## Why is the first reply so slow?

Ollama loads the model into memory on the first message, and again after it has sat idle for a while, so the first reply takes longer than the rest. A long or resumed conversation is also slow to start, because the whole conversation is read again.

## A cloud model takes minutes to start replying

On some networks the route to a provider over IPv6 does not answer, and each attempt waits before the next address is tried, so even a one-word reply can take two minutes. Sympose connects to models over IPv4 only, which avoids it.

If the first word still takes long, the cause is elsewhere: a slow connection, a very long conversation, or a busy provider. A network that has only IPv6 can turn this off by setting `SYMPOSE_ALLOW_IPV6=1` in `.env`.

## It says there was no answer from the model

The model took longer than Sympose waits. The wait is 120 seconds plus one for every 40 tokens of the prompt, and a cold start of a local model on a slow computer can pass it. Try again, since the model is then loaded, or raise `model_timeout`. Condensing a long conversation shortens the wait too.

## How do I make a long conversation start faster?

Condensing helps most: type /compact, or leave `auto_compact` on, and the earlier part is sent as short notes. A smaller `context_window`, or `history_tokens` which caps the earlier turns, also shortens the wait, at the price of remembering less.

## She says she cannot find something that is in my vault

Searching by meaning can miss a note you name only by a short title. If nothing else matched, saying its whole title, file name or an alias finds it; otherwise give a few more words about it or use the words the note itself uses. Also check that the right vault is active and that the persona is allowed to see that folder (`vault_folders`).

## The search seems to work only by keywords

Check that the small search model is installed: run `ollama list` and look for `nomic-embed-text`, or pull it with `ollama pull nomic-embed-text`. On the first launch wait for the animated line above the chat box to finish.

## She says she cannot see my notes

No vault may be configured. Set `VAULT_PATHS` in `.env` to your vault folder.

## A persona says it cannot change my notes

It can propose changes, but only in the web app, with a note open in the editor. If it says it cannot edit the note you have open, check four things. The chat must be the web app's, not the terminal. The note must be open in the editor. The persona's `edit_mode` must not be `plan`.

And with a cloud model, the open note is held back until you allow `open_note` with /share (and `annotations` for your comments).

If a persona still says it cannot, it may be a small model that edits poorly: try a larger one. Nothing it proposes reaches the file until you click Accept.

## A reply stops mid-sentence

It reached its length limit. Raise `reply_limit` in `settings.json`.
