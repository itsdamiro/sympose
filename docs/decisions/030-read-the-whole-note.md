# 030 — Read the whole note: a note with no body text is still a note, and its aliases and properties are read

> **Status: Accepted.** Stage 1 is built and measured (see "Measured, stage 1"); stage 2 is being built in two layers (see "Stage 2, as decided"): properties riding along with a note that was found, then, only if it measures well, a search over properties on their own. A note that a message names in full is found without a search (see "A note named in full"), which closes #81. This record came first, as the standards ask. Reverses "Not indexed, by choice" in ADR 014 and settles the design points of issue #1. It changes only what is indexed and how it is shown; retrieval, the thresholds of ADR 027 and the weak-evidence check of ADR 021 are unchanged until a measurement says otherwise.

## Context

The grounding index is built from body paragraphs only (ADR 014). A note with no body text has no paragraph, so neither the keyword search nor the search by meaning can return it, whatever its title says. That covers notes that are only properties (a card with a role and an email), outlines (headings with nothing under them) and notes that are only a title, which in some vaults is the whole content (a collection of quotes, each titled by the quote; a daily note titled by its date). Measured on a personal vault of 619 notes: about 156 (25%) have no indexable body, and 7 of the 14 needed notes that the search by meaning missed were of that kind; the two public and synthetic sets used to tune the search (176 and 26 notes) have none, so no earlier measurement showed it. A title-match rescue on top of the meaning search was measured and is not worth it (it fixed 1 of 76 messages), because the notes were not indexed at all.

Two more facts. `aliases` (Obsidian's property for other names of a note) is not read anywhere in the index, so a note is not found by an alias even when it has body text. And a note's other properties are never indexed: ADR 014 left them out because a value such as `status: draft` would surface as prose the user never wrote. That reason stands, and it decides how they are shown (below) and not whether. The vault owner's position is that every property should be read, since properties define a note and link it to other notes.

## Decision

**Every note is indexed, whatever it holds.** A note gets up to two passages beyond its body paragraphs:

- **A title passage, for a note with no text under its headings, or none at all.** It carries the note's title (`title:` or `name:`, else the file name), its aliases as its text, and its headings (as many as fit in one passage) as its heading, so an outline is found by what it lists. The title is the content of such a note when the title is the content (a quote), and is a label when it is not; the index cannot tell which, and does not need to. The prompt shows it as a note that exists with nothing else in it (`- Title (path): this note is empty: it has no text yet, only its title`, or `... only its title and these headings`, and `; also called <aliases>` when it has them), so the model is never handed an empty note as if it had content. This is what the issue called "exists, but empty", and it applies to a note with a title and nothing else, which is true of a quote and of an empty stub alike.
- **A properties passage, for a note with frontmatter.** Its text is one `key: value` line for every key with a value. A list is joined with commas; a link is written as the name of the note it points to, so `author: [[Anna Ruiz]]` reads `author: Anna Ruiz`, whether the link is quoted or not (an unquoted `[[Anna Ruiz]]` is read by the YAML parser as a nested list, and is flattened back to the name); a date is written as the date. The passage has the heading `Properties` and the prompt labels it as properties, so a value is shown as what it is and not as prose. It is cut to the size the embedding model takes whole.

**Aliases count as the title.** A note's aliases are added to the term set of its title and to its labels, for every one of its passages, so a message that names an alias is about that note in the same way a message naming its title is (ADR 019, ADR 024).

**What reaches a cloud model.** Properties often hold emails and phone numbers. Until the settings of issue #79 exist, a properties passage is dropped from a turn's grounding when the model is not local, and a title passage is not (a title already travels with every passage of its note). The rule sits where the prompt is put together, since that is where the model is known, and #79 replaces it with a per-category setting.

**Two stages, each kept only if it measures well.** The properties of a note that has a body could pull wrong notes in, since they now compete with the body for the same message. So the work is done in two steps, and the second is not kept unless it passes:

1. Title passages for notes with no body text, and aliases as part of the title. This is the measured gap.
2. Properties passages for every note that has frontmatter.

**How it is measured.** A labelled set of messages about notes of these kinds is built: one in this repository from the synthetic fixture vault (cards with properties, title-only quote notes, outlines, empty notes, notes with aliases, date-titled notes), and one from a real vault that stays private, as before (ADR 027). Each stage is run with the real embedding model on the existing sets and the new one. A stage is kept when the pass rate on the existing sets does not drop (today: 73% and 78% on two real vaults, 89% on the synthetic one, in the default mode) and the new set improves. The real chat model is then asked about a properties fact (an email), a quote by its title, and an empty note, and the replies are read: the fact is given from the note, and an empty note is described as having no text, not filled in.

## Stage 2, as decided: properties in two layers

Discussed with the vault owner after stage 1. Stage 2 as first written (one indexed properties passage per note, competing with the body for every message) risked pulling wrong notes in, and it is not what answers the most common question. "Is the project done?" needs the `status` of a note that search already found by its title or text; it does not need properties to be searched. So properties come in two layers, each kept only if it passes, and the first does not touch ranking at all.

**Layer 1: properties ride along with a note that was found.** When a turn attaches a note of the user's, its properties are attached with it as one passage of kind `properties`, category `properties` (ADR 031). Nothing about which note is found changes: properties are not in the index's terms or statistics and are not searched, so the scores and every existing measurement are unchanged by construction. The rules:

1. **Relevance is inherited, never judged again.** A note is relevant when the retrieval of ADR 014, 021 and 027 says so, and its properties come with it. If nothing is attached, nothing rides. The model decides what to use; no rule looks at the words of the message to choose a key.
2. **One properties passage per note**, however many of its passages were attached (up to two, ADR 014).
3. **They do not use up the passages of a turn.** The limit of five passages counts text only, so properties cannot push a body passage out. They are added after the notes and are the first to go when the prompt does not fit the window (ADR 015).
4. **The whole passage, every key with a value.** The key name is what tells the model what a value means (`status: in progress`), so a key is never sent without its name, and the model picks the one it needs. It is written as in stage 2's first draft (lists joined with commas, a link as the name of the note, a date as a date) each value on one line, a line cut at 120 characters with an ellipsis (a value that long is prose, and one long `description` must not push `status` out), and the whole kept to the size of one passage (400 characters) by leaving out a line that no longer fits while shorter ones after it still go in; the measured vaults stay under that at the 90th percentile (a median of 82 characters, about 20 tokens, on a personal vault of 625 notes; 61 on the Obsidian help notes). A note with no properties adds nothing.
5. **Cloud models.** The `properties` category decides (ADR 031). Without the user's approval a cloud model gets none, and the prompt says that properties were held back, as ADR 031 already provides. Since layer 1 embeds nothing, the embedding gate is not involved.

**Layer 2: properties searched on their own.** Only for a message that layer 1 cannot serve, because no note was found and the answer lives in a property ("who works at Acme?"). Properties become a passage of their own in the index and in the embeddings, so this layer has the cost that layer 1 does not (one more passage to embed per note, and the embedding gate of ADR 031's "Not built yet"), and the risk that a message like "I'm done for today" pulls in every note with `status: done`. It is consulted only when the search of layer 1 finds nothing convincing, and it is kept only if the existing sets do not drop and the messages that must attach nothing stay clean. Layer 1 is measured; the exact-name part of this layer is built as "A note named in full" below, and searching property values (or searching them by meaning) waits for a set of messages that ask for one.

**Measured, layer 1** (real chat model `gemma2:9b` through Ollama, three runs per message, a scratch vault of four notes, the same code with the properties switched off and on; a fact about that model and that vault, not a general rate):

| Message | Without properties | With properties |
|---|---|---|
| "What is Priya Nair's email?" (a card with only properties) | 0/3 (said it could not find it) | **3/3** |
| "Has the Atlas redesign of the marketing site been finished?" (`status: in progress`) | 0/3 | **3/3** |
| "When is the Atlas redesign due?" (`due: 2026-11-15`) | 0/3 | **3/3** |
| "Who owns the Atlas redesign?" (`owner: [[Ana Ruiz]]`) | 0/3 | **3/3** |
| "What does the Atlas team do on Tuesdays?" (a body fact, the properties beside it) | 3/3 | 3/3, unchanged |
| A message about a note with no properties, and "good morning" | nothing added | nothing added |

Cost: about 90 to 130 characters (roughly 25 to 35 tokens) per attached note with properties; the median time to first token stayed inside the run-to-run noise (about 0.9 s before and after). No test set needed re-running: properties are in no term count, and a test pins that a word found only in a property finds nothing, so which notes are found is unchanged by construction. The properties-only card is shown with the stage 1 wording ("this note is empty ... only its title") beside its properties, and the model answered from the properties three times of three without calling the card empty, so that wording is left as it is.

**Known and accepted, from the review of layer 1.** A properties passage names its note (title and path), so a user who has approved `properties` for cloud models but not `notes` sends the names of the notes whose properties were found; `/share` now says "with each note's name" so this is known (ADR 031). When the window is tight and only the properties are left out, the prompt's "N more matching passages were left out" counts them, which is true and is not worded apart. The index is asked again for its properties after the search (a cached lookup), rather than carried out of the follow-up step; computing every note's properties text at index build costs 0.08 s per 10,000 notes.

**What layer 1 cannot do, seen in the same run.** It only helps when the note is found. In this small vault "When is Atlas due?" and "Is the Atlas project done?" did not attach the Atlas note at all (the second attached a note about its owner instead): a short message about a note that is named in it is not always found by meaning alone, which is a limit of the retrieval that this change does not touch. That is the case layer 2 and the alias and title work of #81 are for, and it is a reason to build them next.

## A note named in full

Decided with the vault owner after layer 1, as the first part of layer 2 and as the answer to #81.

**Context.** A short message that names a note scores low against it by meaning: "tell me about Annie" (an alias of Anna Ruiz) scores 0.56, under the 0.72 bar and the 0.68 clear-winner floor, and "When is Atlas due?" was not found in the layer 1 run either. `auto` uses meaning alone for the user's notes (ADR 027), and a name is a word match. The title rescue measured on 2026-09-26 counted shared words and accepted half of a title (1 of 76 messages, not kept); this rule is narrower: the whole name, and only when nothing else was found.

**Decision.** When the search attached no note of the user's, and the message contains, as whole words in order and whatever their case, the title, the file name or an alias of a note, that note is attached (its first two passages, ADR 014's limit per note), marked `via: name` in the turn record (ADR 025) and with `matched` 2, like a hit by meaning, so the follow-up rewrite check does not second-guess it (ADR 021). No search is involved: the names are in the index, so nothing is embedded and nothing new reaches a cloud model beyond what any attached note is (the `notes` category decides, ADR 031). The rules:

1. **Rescue only.** It runs when the search attached nothing, and never changes a note the search chose. Attaching a named note beside the search's own choice was measured and lowers the pass rate.
2. **The whole name.** Every informative word of the name, in order. A name with no informative word (only filler words) or under three letters is not a name.
3. **Ambiguity.** A name that two notes carry attaches both; a name that three or more carry attaches none, since it is a category and not a note. In the three measured vaults 11 of about 1,050 names are shared, none by more than 3.
4. **A common word is not a name.** A name is skipped when its rarest informative word is in more than 10% of the notes, once the vault has 10 notes (the same reasoning as `_MAX_NOTE_SHARE` in ADR 014). In the Obsidian documentation "Search" is in 31% of the notes, and a note called Search was attached to "explain how a binary search works", a general question. The names that helped are in 3% or less; anything from 5% to 20% gave the same result, and 10% is the middle of that gap.
5. **Not the persona's own name.** A name made only of the words of the persona's name, handle and aliases attaches nothing (ADR 021), so "hi Samantha" does not attach a note called Samantha.
6. **Not in `keywords` mode**, which stays exactly today's search (ADR 027). At most `max_results` passages, longest names first.

The offsets (2 notes for one name, 10% and 10 notes) are internal, like the clear-winner numbers of ADR 027, and are not settings.

**Measured** (simulation on top of `auto`, scored with the same scorer as ADR 027, real embedding model; `gen/named_sim.py` in the private evaluation folder): synthetic set with the no-body messages, 72 messages: 63 to **65** ("tell me about Annie", "how did we go over budget?"); Obsidian documentation, 79 messages: 51 to 51; personal vault, 76 messages: 61 to **62** ("who is Steve Jobs in my notes?"); nothing broken on any set, no junk note attached. Without rule 4 the documentation set loses "explain how a binary search works" (51 to 50). Attaching the named note even when the search found others cost 3 to 8 messages (51 to 48 on the documentation), and is not built. The gain is 3 messages out of 227: the sets hold few short messages that name a note, so this measures that the rule is safe more than that it is large.

**Measured, as built** (`run_gen.py`, `MODES=auto`, threshold 0.72, and `tests/live_retrieval_cases.py`): synthetic 51/59 to **52/59**; Obsidian documentation 51/79 to 51/79; personal vault 61/76 to **62/76**; the no-body set of 13 messages 12/13 to **13/13** in `auto` (the alias message; `embeddings` 13/13, `hybrid` 12/13 unchanged, `keywords` unchanged by design). Messages that must attach nothing: 17/17, 15/15 and 14/15 as before. The real chat model (`gemma2:9b` through Ollama, a scratch vault of 22 notes, three runs per message, the rescue switched off and on): "tell me about Annie" (an alias of a card that holds only properties) 0/3 to **3/3**, "how did we go over budget?" 0/3 to **3/3**, "explain how a binary search works" with a note called Search among twelve that mention search 3/3 to 3/3 with nothing attached, and "hi Samantha" with a note called Samantha 3/3 to 3/3 with nothing attached. A fact about that model and that vault, not a general rate.

**Not built: property values as names.** A value that names something (a company, an email) could stand for the notes that hold it, with a cap of 5 notes (the passages of a turn) and leaving out values that are links to a note (that note's own name finds it). None of the sets has a message that asks for a note by a property value, so a run of it measured nothing (0 messages changed on all three sets), and a fixed cap cannot be chosen from one vault: values held by 2 to 5 notes are mostly real names, values held by 6 or more are enumerations (`unknown` 50 notes, a genre 18), but the count falls smoothly with no gap. It needs its own set of questions first.

**Alternatives rejected.** Adding the named note beside the search's choice (measured, worse). Accepting part of a name, as the 2026-09-26 rescue did (not worth it, and it is what let common words in). Boosting the meaning score of a note whose name is said, or embedding the names: the low score of a short message against a long passage is the thing that is low, and this needs no model. Property values now (above).

## Measured, stage 1

Built as decided: title passages (with headings and aliases as above) and aliases as part of the title; properties passages are not built. Measured with the real embedding model (`nomic-embed-text`, Ollama), default mode (`auto`, threshold 0.72), the same code with and without the change, on the same labelled sets. A pass means what it meant in ADR 027. The two real-vault baselines differ from ADR 027's figures (78% and 75%) because their label sets have grown since (79 and 76 messages); the comparison is of the two runs on the same set.

| Set | Before | After |
|---|---|---|
| Synthetic vault, 59 messages | 51/59 (86%) | 51/59 (86%) |
| Public Obsidian documentation, 174 notes, 79 messages | 51/79 (64%) | 51/79 (64%) |
| Personal vault, 620 notes, 76 messages (private) | 55/76 (72%), needed notes found 43/57 | **61/76 (80%), needed notes found 49/57**, held-out half 25/38 to 28/38 |
| New set of 13 messages about no-body notes (synthetic, in the repository, `NO_BODY_MESSAGES`) | 4/13 (30%), held-out 2/6 | **12/13 (92%), held-out 6/6** |

Messages that must attach nothing stayed clean on every set (14 of 15 on the personal vault, as before), including the ones written to tempt a title-only note ("I feel slow this morning" next to a quote titled "Slow is smooth and smooth is fast"). So stage 1 is kept.

**The one miss and its limit.** "Tell me about Annie", where Annie is only an alias, is not found in `auto`, `embeddings` or `hybrid` (0.56 by meaning; saying the aliases as "also called Annie" in the embedded text lifted it to 0.61, still under 0.72, and is kept because it lifts other alias messages over the bar). A message that names nothing but a nickname is a word match, and `auto` uses meaning alone for the user's notes (ADR 027); `keywords` finds it. This is a known gap, not tuned for.

**Read with the real chat model** (`gemma2:9b`, three runs each, scratch data): a quote-titled note was named 3 of 3; a properties-only card was described as a note that exists and is empty, with nothing invented about the person, 3 of 3; an empty date-titled note was described as empty 2 of 3 (the third said nothing was found). The first wording (`no text besides the title`) got the empty date note right once in three, and a second, louder wording got it right three times but had the model say "I've heard that name before" about a card, which is invented, so it was rejected. An outline whose headings were the answer was ignored by the model under every wording: the note was attached, and the model answered from general knowledge without inventing anything about the note. That is a limit of this model, recorded here and not tuned for. For a quote note the wording "this note is empty" is accurate but a little off when the title is the content: the model sometimes says "it's empty right now" of a note the user thinks of as the quote.

## Consequences

- A quarter of one real vault becomes findable; a note is found by an alias; a fact that lives only in properties can be answered from the note.
- The index grows by up to two passages per note. New passages are embedded in the background the first time; the vectors of existing body passages are kept, since their text does not change.
- A note with no body is counted as a note in the term statistics, which changes the scores a little everywhere: the existing sets are the check.
- The risk ADR 014 named is real: a passage with almost no words can outscore real text. A title passage starts with the same rules as any passage, and if the measurement shows it over-scoring, it is limited to the label match of ADR 024 (a message that names half of the title) instead of the general score.
- Properties are shown to a local model only at first, so a cloud model answers less than a local one about facts in properties until #79.
- The index gains one passage per note with no text under its headings. On the personal vault that is the 156 notes that were missing, embedded in a few seconds.

## Alternatives rejected

- **A title-match rescue after the search by meaning.** Measured: 1 of 76 messages, and looser rules added more wrong notes than they fixed. The notes were missing from the index, and a rescue cannot return what is not there.
- **Merging properties into the body paragraphs.** A value would read as prose the user wrote and would lengthen every paragraph of the note; a separate, labelled passage keeps them apart and lets the measurement switch them off without touching the body.
- **Title and headings only, without properties.** Simpler and more private, and it finds a card by name but cannot answer from it; the stated position is that every property is read, with what leaves the machine decided by #79.
- **Sending properties to every model from the start.** Rejected: what goes to a cloud service must be known and approved by the user (#79).

## Not built yet

Stage 2's properties passage as first written is replaced by the two layers of "Stage 2, as decided"; layer 2 is not built until layer 1 is measured. Later, and each with its own record: a message about a date ("yesterday") does not match a note titled by that date by meaning, so date-titled notes may need their own handling; links between notes as connections the persona can follow (#78); folder definitions (#23); reports on notes missing a title or properties (#77).
