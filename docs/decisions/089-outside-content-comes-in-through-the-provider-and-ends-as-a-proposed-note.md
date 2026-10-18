---
type: decision
status: proposed
date: 2026-10-18
projects: [sympose]
concepts: [Cloud privacy, Vault tools]
amends: []
supersedes: []
tags: [type/decision, status/proposed, project/sympose, topic/consent, topic/cost, topic/privacy]
---

# 089 — Outside content comes in through the provider and ends as a proposed note

> **Summary.** Web search, reading a page and watching a video are tools the cloud provider runs inside the same request, switched by one knob (`off`, `asked`, `auto`) and one approval per category, and the thing the user wants most from them is capture: a link, a video or a PDF becomes a note when he asks for one, proposed and waiting for Accept. Nothing is built; the numbers that decide the video route are not measured yet. It costs a new kind of untrusted text in the prompt and a new thing that leaves the machine.

> **Status: Proposed (2026-10-18).** Design talk with the user the same day; the open questions below are settled by the spike before any code. Builds on ADR 031 (what a cloud model may receive), ADR 040 and 072 (the persona's tools and the Accept gate), ADR 077 (skills) and ADR 033 (folder definitions).

## Context

Asked to summarize a YouTube video, the persona said she could not, because she has no access to the internet. She was right, and the cause is wider than the internet:

- Every model call sends text. In `sympose/engine/model.py` the call is `litellm.completion(model, messages, ...)` and every message's `content` is a string. Nothing sends a video, an image, a PDF or audio as media.
- Her tools reach the vault and herself and nothing else: `search_notes`, `open_note`, `list_notes`, `find_notes`, `remember`, the propose and comment tools, `show_note`. Nothing fetches a URL or searches the web. A link in a message arrives as the characters of the link.
- MCP, the planned way to add tools, is not built (VISION, "Actions").

Gemini Flash, one of the cloud models offered in `model_options.py`, can read a video and use Google Search, but only when the request asks for it. The other cloud providers have the same kind of tool (search, page reading, code execution) that they run on their side. LiteLLM 1.102, the installed version, has code that turns a `file` content part into Gemini's `file_uri` and `file_data`; whether a YouTube link passes through it untouched is not tested.

What the user wants from this is not a better chatbot: he studies mostly through YouTube and free web resources, and the feature he expects to use most is turning a link into a note in his vault. So capture ranks first and live web questions second.

What video costs, from Google's video-understanding page (read 2026-10-18; the sources disagree in places, so these are leads, not figures):

- About 100 tokens per second at low media resolution and about 300 at the default, with frames sampled once a second plus audio. That is roughly 360,000 tokens for an hour at low resolution and 1,000,000 at the default. A third document gives 263 per second for video and 32 for audio.
- The page does not say whether a YouTube link is read through its captions or by frames and audio. A transcript costs a small fraction of the tokens (an hour of speech is in the low tens of thousands), so if Gemini used the captions the video route would be cheap; nothing says it does.
- The YouTube link feature was described as a preview, free of charge, with a daily free-tier limit and a warning that prices will change. A start and end offset exist in static mode.
- A release note and a secondary blog mention an "agentic" mode on newer Flash models that loads only the transcript, frames and audio it needs. Not confirmed on Google's own pages.

## Decision

**1. Outside content comes in through the provider, not through Sympose.** A model that has a built-in tool (Google Search, page reading and video for Gemini; the equivalents for the others) gets it attached to the request, and the provider runs it. Sympose does not browse, so it has no crawler, no page parser and no search key to look after. A per-model list says which tools a model has, the way `lookup.MEASURED` says which models take tools. A model without one says it cannot, and a local model has none.

**2. One knob, `web_access`: `off`, `asked` or `auto`.** The names avoid `ask`, which in `skill_lookup` and `vault_lookup` means "the model calls a tool". Default `asked`.

- `asked`: the tool is attached only on a clear signal, a link in the user's message. The trigger is deterministic, in the same spirit as ADR 077's refusal of phrase lists: wording such as "look this up" is not read for intent.
- `auto`: the tool is attached on every turn on a model that has one, and the model decides. The cost is the tool's description on every turn and a provider charge on each search.
- `off`: nothing is attached.

**3. Approval is per category, in `cloud_share`'s manner (ADR 031), off by default.** Two new categories are proposed: `web` (the search terms and the links a provider reads for the user) and `media` (a file the user attaches: a video, an image, a PDF, audio). Withheld, the prompt says so, and the persona tells the user how to allow it, as ADR 031 does for notes. The reply header names what was sent.

**4. Capture is the product, and it ends in a proposed note when the user asks for one.** A link alone is not a request for a note, and a request for a summary is not one either: "summarize this video" gets the summary in chat and files nothing, as ADR 072 says of `manual`, the default ("when asked, she proposes"). "Make study notes from this video" or "save that as a note" is a request for a note, and she writes it through `propose_note`, into the folder whose definition (ADR 033) fits, and the file changes only when the user clicks Accept (ADR 072, never relaxed). In `plan` she describes the note in chat and proposes nothing; in `auto` she may propose one unasked, as ADR 072 allows. Asking for the summary and then for the note does not read the video twice: the summary is already in the conversation, so the second step costs only the output tokens of the note, but a chat summary is usually shorter than a study note, so a user who wants the full note says so in the first message. A skill, `capturing-from-a-link` or the like (ADR 077: text only, no script), carries the shape of the note: for a video, an outline with timestamps that link back to the moment, the key ideas and a few questions to test oneself on; for a page, the key points, the passages worth keeping and the link as its source. The skill does not add the ability to watch or to read a page; the engine does. A note made from a link records the link in its properties.

**5. A video has two routes, chosen on cost and on what the video is.**

- *The transcript route:* Sympose fetches the captions of a public video and the model summarizes text. It costs little, works on any model including a local one, and cannot see a slide or a line of code on screen. It depends on a captions source that is not an official interface and can break.
- *The watch route:* Gemini reads the video, with a low media resolution as the default and a start and end offset for a long one, so the persona can take the first twenty minutes and then the next. It sees the screen and costs far more, and it is Gemini only.

Which one is the default waits on the spike (below). Whatever the route, a length cap applies to one turn, and the persona says which part of the video she covered.

**6. What comes in from outside is data, and it is marked as outside.** A fetched page or a transcript can contain instructions aimed at the model; the prompt treats it as untrusted text, as ADR 077 treats a copied-in skill. A claim from the web is stated as from the web, never blended into "your notes say"; vault grounding stays zero-hallucination and covers the vault part of an answer only. A note made from a link records the link it came from.

## The spike that settles it, before any code

One scratch run on a short, public video with the user's own Gemini key, no vault content, with his go-ahead (a cloud run needs it each time):

1. The token count Gemini reports for a YouTube link at the default and at a low media resolution, and whether the answer shows it read captions (a question only the captions answer: a word the speaker says that is not visible).
2. Whether the agentic mode exists in the API and what it does to the count.
3. Whether LiteLLM sends a YouTube link as a `file` part unchanged, and what a page read and a search return through Google's tools.
4. Whether captions can be fetched reliably from the machine, and for how many of a handful of public videos.

## Consequences

- A cloud model becomes useful for studying: a link goes in, a note in the vault's folder comes out, after Accept.
- The cost of the knob is visible: `asked` costs nothing until a link appears, `auto` costs a tool description every turn.
- Two more things can leave the machine, and both are approved by the user and off by default.
- The persona's answers can now carry web claims, which makes provenance a rule in the prompt, not a habit. A model that blends the two is a bug to fix, the same as a vault claim with nothing behind it.
- The watch route is tied to one provider's preview feature and its prices. If those change, the transcript route is the one that stays.
- A local model gets the transcript route and nothing else.

## Open questions

- Skills are chosen by matching the message to a skill's description (ADR 077), and a message that is only a link gives that match almost nothing. Probably the engine loads the capture skill when a link triggers the tool, the same signal as `asked`, and no new surface; to be settled with the spike.
- Whether a link in a message should make her offer a note in her reply (one line, no draft) or say nothing about it until asked.
- Which route is the default for a video, once the spike has numbers.
- The names `web` and `media`, and whether a link a provider reads belongs under `web` or its own category.
- Whether fetching a transcript on the user's machine needs an approval of its own (the request goes from his machine to the video site).
- Where the length cap lives (a setting beside `skill_cap`, or fixed).
- Whether the web app needs a visible way to attach a link or file beyond pasting it (the user rejects new surfaces; the composer already shows what travels with the next message, ADR 075).
- Prompt caching and a cheaper model for the chores (recaps, the query rewrite, compaction) are separate ways to cut a cloud model's cost; neither is decided here, and whether the prompt order already suits caching has not been checked.

## Alternatives rejected

- **Sympose's own `web_search` and `fetch_page` tools.** Rejected for now: a crawler and a parser to maintain, a search key, and the same untrusted text. It becomes right if a model with no built-in tool must have the web, or if the provider tools prove unreliable.
- **A `/video` command or a skill that does the watching.** Rejected: a skill is text and cannot change what a request carries (ADR 077); a link in the message is the natural trigger and adds no surface.
- **Deciding from the wording of a message whether to search.** Rejected: phrase lists break on the first unexpected wording (ADR 077); `auto` lets the model decide and `asked` uses a link.
- **MCP first.** Rejected: its tool descriptions are sent every turn, and it is the largest piece; a provider tool needs none of it. It becomes right when the user needs an outside system the providers do not offer, such as a calendar.
- **Local video files first.** Rejected: capture from a link covers what he studies from, and a file needs an upload path and a size policy. Reconsider when he has lectures that are not online.
