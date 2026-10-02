# How Samantha uses your notes

## How does Samantha find my notes?

Every message you send is looked up in your vault first. The best matching passages, a few sentences each and up to five, go to the model together with your message, and the answer is meant to come from them. This is called grounding. By default the lookup goes by meaning, not only by words.

## Can Samantha look in my notes herself instead of searching every message?

Yes, with a model that can call tools. The default, `vault_lookup` `"by_model"`, does it on tested models such as Gemini Flash; `"ask"` does it on any that can call tools. She then decides when to search, open a note, list a folder or find notes by tag, property or link. Each lookup is one more model call; /grounded shows them.

## Can Samantha count or filter my notes, like which are tagged idea?

Yes, when she looks in your notes herself: a tool finds notes by folder, tag, property value, a link to or from a note, or exact words, and gives the count with the matches, so only those use the model's window. She says how many notes mention backups from a real count, not a guess. It does not search by meaning.

## Why can't Samantha open the 5th note in my folder?

Only when she looks in your notes herself (`vault_lookup` `"ask"`, or the default on a tested model) with a model that can call tools: she then lists the folder's notes herself, alphabetically by file name, and opens the 5th. With `"auto"`, or a model without tools such as gemma2:9b, she cannot list a folder: she only gets what a search finds for your words.

## Does Samantha know the names of all my notes?

No. She is always given a map of the vault: its folders, how many notes each holds, and the most common tags. The full list of names does not fit a local model's window, and a cloud model would be charged for it on every message. She finds the rest by searching, or with the tools.

## What does searching by meaning mean?

Samantha compares what your message is about with what each passage is about, not just the words. A small model turns both into lists of numbers, and passages whose numbers are close to your message's are used. So "what did we settle on for backups?" can find a note that only says rsync.

## Do I have to set anything up for searching by meaning?

It is on by default, as `auto`. It needs one small model in Ollama, pulled once with `ollama pull nomic-embed-text`. Without it, or when Ollama is not running, Samantha quietly searches by keyword instead. Nothing breaks, the search is just less smart.

## Is my vault sent anywhere for searching by meaning?

No. The small model runs in your Ollama on your computer, and the numbers for each passage are kept in a cache file, `embedding_cache.sqlite`, beside `settings.json`. Only if you set an `embedding_model` from a cloud provider, and allow notes for cloud models with /share, would passages leave your computer; without that yes she searches by keywords.

## What does the animated line above the chat box mean?

The first time, Samantha reads all your notes into that cache in the background, a minute or two for a big vault, and the animated line above the chat box shows she's working on it. Until it is done she searches by keyword, so you can chat at once. Later launches only read notes that changed. The same line also shows while a recap or a memory update is being worked on.

## Why does she miss a note, or bring notes that have nothing to do with my question?

For fewer unrelated notes, raise `embedding_min_similarity` in `settings.json` (0.72 by default); if she misses notes, lower it. `embedding_margin` (0.02) drops notes that are not nearly as close as the best one. If nothing else matches, saying a note's whole title, file name or alias finds it, unless that name is a word a tenth or more of your notes use.

## How do I go back to searching by words only?

Set `grounding_search` to `"keywords"` in `settings.json`. She then never uses the small model and does not build the cache.

## What does the reply header show?

Above each reply Samantha shows a line like `@samantha · Gemma2:9b · TTFT 8.3s · from Notes/Example.md +1`. It gives the model, then TTFT, which is the time until the first word appeared.

## What does the from part in the reply header mean?

`from` names the note that grounded the reply, the note the answer was taken from, and `+1` says one more note was also used. If nothing follows the TTFT, no note matched.

## What does searched mean in the header?

`searched "..."` appears after a follow-up question and shows the search Samantha wrote for it.

## How does she handle follow-up questions?

A message such as "why did we pick it?" has no words to search for. When the first search finds nothing and there is earlier conversation, one small extra model call rewrites the question into a standalone search using the last two exchanges. The rewrite only feeds the search and is never shown to the model as something you said.

## What if nothing matches?

Samantha says she could not find it in your vault instead of inventing an answer. If the note is there, ask again with a few more words about it, or with the words the note itself uses.

## Does she read a note's properties?

Yes. When a note is found, its properties, the block between two --- lines at the top such as a role, a status or an email, come with it, so she can answer from a status or an email. A cloud model gets them only when `cloud_share` allows properties.

## Can she find a note by a property value?

Only when the search found nothing. If your message says a property's whole value, like a company's name or a status, the notes that hold it are used, up to five. A value held by more than five notes is a category and finds none.

## What about a note with only a title, or nothing in it?

It still counts. A note with no text under its title, like a quote, a card of properties or an outline, is found by its title, its aliases and its headings, and she is told it is empty rather than given something to make up.

## Which notes may she read?

Only the folders the persona is allowed to see (`vault_folders`), in the active vault.

## How do I hide the notes she used?

Type `/grounding` to hide or show the note line in the reply header. The `show_grounding` setting does the same.

## How do I turn off the follow-up search?

Set `grounding_followups` to `"off"` in `settings.json` to stop the extra search for follow-up questions.
