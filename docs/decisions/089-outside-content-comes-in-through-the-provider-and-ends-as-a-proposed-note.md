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

> **Summary.** Web search, reading a page and watching a video are tools the cloud provider runs inside the same request, switched by one knob (`off`, `asked`, `auto`) and one approval per category, and the thing the user wants most from them is capture: a link, a video or a PDF becomes a note when he asks for one, proposed and waiting for Accept. The first slice is built (a YouTube link watched by Gemini Flash); the spike (see "Spike results") and its numbers make the provider's agentic video mode the default for Gemini, with captions for every other model. It costs a new kind of untrusted text in the prompt and a new thing that leaves the machine.

> **Status: Proposed (2026-10-18).** Design talk with the user the same day; the spike has run and the Decision below is written from its results (the user chose the agentic default, 2026-10-18); the first slice is built (see "Slice 1, as built"). Builds on ADR 031 (what a cloud model may receive), ADR 040 and 072 (the persona's tools and the Accept gate), ADR 077 (skills) and ADR 033 (folder definitions).

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

**1. Outside content comes in through the provider, not through Sympose.** A model that has a built-in tool (Google Search, page reading and video for Gemini; the equivalents for the others) gets it attached to the request, and the provider runs it. Sympose does not browse, so it has no crawler, no page parser and no search key to look after. A per-model list says which tools a model has, the way `lookup.MEASURED` says which models take tools. A model without one says it cannot, and a local model has none. For Gemini the request is made directly to Google's REST endpoint (`httpx` is installed), not through LiteLLM, which cannot send a YouTube link, `mediaProcessing`, or Google's own tools beside a function declaration (Spike results, 3); the request sets `toolConfig.includeServerSideToolInvocations`. Only that route is Gemini-specific code, behind the same seam as `model.call_model`, and the history it keeps is text only (see 5).

**2. One knob, `web_access`: `off`, `asked` or `auto`.** The names avoid `ask`, which in `skill_lookup` and `vault_lookup` means "the model calls a tool". Default `asked`.

- `asked`: the tool is attached only on a clear signal, a link in the user's message. The trigger is deterministic, in the same spirit as ADR 077's refusal of phrase lists: wording such as "look this up" is not read for intent.
- `auto`: the tool is attached on every turn on a model that has one, and the model decides. The cost is the tool's description on every turn and a provider charge on each search.
- `off`: nothing is attached.

**3. Approval is per category, in `cloud_share`'s manner (ADR 031), off by default.** Two new categories are proposed: `web` (the search terms and the links a provider reads for the user) and `media` (a file the user attaches: a video, an image, a PDF, audio). Withheld, the prompt says so, and the persona tells the user how to allow it, as ADR 031 does for notes. The reply header names what was sent.

**4. Capture is the product, and it ends in a proposed note when the user asks for one.** A link alone is not a request for a note, and a request for a summary is not one either: "summarize this video" gets the summary in chat and files nothing, as ADR 072 says of `manual`, the default ("when asked, she proposes"). "Make study notes from this video" or "save that as a note" is a request for a note, and she writes it through `propose_note`, into the folder whose definition (ADR 033) fits, and the file changes only when the user clicks Accept (ADR 072, never relaxed). In `plan` she describes the note in chat and proposes nothing; in `auto` she may propose one unasked, as ADR 072 allows. Asking for the summary and then for the note does not read the video twice: the summary is already in the conversation, so the second step costs only the output tokens of the note, but a chat summary is usually shorter than a study note, so a user who wants the full note says so in the first message. A skill, `capturing-from-a-link` or the like (ADR 077: text only, no script), carries the shape of the note: for a video, an outline with timestamps that link back to the moment, the key ideas and a few questions to test oneself on; for a page, the key points, the passages worth keeping and the link as its source. The skill does not add the ability to watch or to read a page; the engine does. A note made from a link records the link in its properties.

**5. A video has two routes, and the model decides which.**

- *The watch route, the default for Gemini:* the link goes in as a file part with `mediaProcessing: AGENTIC` and `mimeType` `video/mp4`, and the model navigates the video itself. Measured: 4,700 to 7,800 tokens for a summary or full study notes on a 12 and a 19-minute video, 9,765 for a question about a 4.4-hour course that static mode refuses (nothing over about 2.8 hours fits there). It sees the screen. It is Gemini only and a preview, so the product treats a failed or changed request as "the watch route is unavailable" and falls back to the transcript route.
- *The transcript route, for every other model and the fallback:* Sympose fetches the captions of a public video and the model summarizes text. It costs little and works on any model including a local one, but cannot see a slide or a line of code on screen, and the caption source is not an official interface: it returned 7 of 7 videos and then blocked the spike's address after 17 fetches, so it needs a cache, a rate limit, IPv4 first (or a short connect timeout) and an honest "I could not get the captions" when it fails.
- *History keeps text only.* Replies from the watch route carry `toolCall` and `toolResponse` parts; sending them back is refused (400, "Tool type of tool_call part does not match with tool call context"), so history keeps the reply's text, the user's link and nothing else. A follow-up that needs the video re-reads it, about 5,000 to 6,000 tokens a turn. Spike results, 2, has the figures. A follow-up with the link left out gets an answer from the text alone and gives a different timestamp from the three that read the video, so the link stays in the history for as long as the conversation is about the video, and a reply that did not read it says so.

Whatever the route, the persona says which part of the video she covered. A static request (`fps`, start and end offset) is kept for a case the agentic mode cannot do, and not built first.

**6. What comes in from outside is data, and it is marked as outside.** A fetched page or a transcript can contain instructions aimed at the model; the prompt treats it as untrusted text, as ADR 077 treats a copied-in skill. A claim from the web is stated as from the web, never blended into "your notes say"; vault grounding stays zero-hallucination and covers the vault part of an answer only. A note made from a link records the link it came from.

## The spike (run 2026-10-18; results below)

One scratch run on a short, public video with the user's own Gemini key, no vault content, with his go-ahead (a cloud run needs it each time):

1. The token count Gemini reports for a YouTube link at the default and at a low media resolution, and whether the answer shows it read captions (a question only the captions answer: a word the speaker says that is not visible).
2. Whether the agentic mode exists in the API and what it does to the count.
3. Whether LiteLLM sends a YouTube link as a `file` part unchanged, and what a page read and a search return through Google's tools.
4. Whether captions can be fetched reliably from the machine, and for how many of a handful of public videos.

## Spike results (2026-10-18)

Run with the user's go-ahead, invented data only (no vault content), on the Gemini key in `.env`. `gemini-flash-latest` resolved to `gemini-3.8-flash`. Public videos: "Me at the zoo" (19 s), a 12-minute TED talk, a 19-minute 3Blue1Brown video, a 4.4-hour freeCodeCamp course. Tokens are what Gemini reported, not dollars: no price was looked up and no bill was checked. Most figures are one run each, so they are direction, not a distribution.

**1. Tokens, and whether it reads captions.**

- A YouTube link is read as frames and audio, not captions: the usage shows video and audio tokens (the 12-minute talk is 67,378 prompt tokens in `generateContent`, 76,308 in `countTokens`; its captions are 12,360 characters, about 3,000 tokens). The word-level "a word only the captions would give" question was not run; the token counts settle it.
- About 71 video and 32 audio tokens per second, so about 6,200 a minute and 370,000 an hour in `countTokens` (about 330,000 by `generateContent`). A video over about 2.8 hours does not fit: the 4.4-hour course counts 1,649,225 against a limit of 1,048,576, and a request is refused.
- The media resolution does nothing to the cost: default, `LOW` and `MEDIA_RESOLUTION_MEDIUM` give the same count to the token, on `gemini-3.8-flash`, `3.5-flash`, `pro-latest` and `flash-lite-latest`, set on the request or on the part. Only `HIGH` changes it, to nearly three times. ADR text above that says "a low media resolution as the default" has nothing to stand on.
- What does cut the cost in the static mode: `video_metadata.fps` (0.2 takes the talk from 76,308 to 34,276; the audio is a floor of 32 a second) and a start and end offset (a two-minute window is 12,363).

**2. The agentic mode exists.** `Part.mediaProcessing = AGENTIC` ("model-driven dynamic navigation, recommended for most use cases" in Google's own API schema, revision 20261017), with `STATIC` for the fixed-rate mode. It needs `mimeType` set on the file part in `generateContent` (`video/mp4` works for a YouTube link); `countTokens` reports only the 3 text tokens, because the video is not loaded up front.

- The same study-outline request on the 12-minute talk: static 68,533 tokens in all, agentic 5,395 (83 prompt, 154 tool use, 4,640 thinking, 518 reply). The video is never reported as input tokens, so what Google bills for it is not known from this run.
- The 4.4-hour course, a question about the two-hour mark: static refused; agentic answered in 35 s for 9,765 tokens in all (1,584 of them video), naming "If Statements & Comparisons" at 1:54:07 and "Building a Better Calculator" at 2:00:37, which are exactly the chapters in the video's description.
- Timestamps against the caption timings of the talk, five topics: static was off by 0 to 29 s, agentic by 0 to 15 s. Good enough for a link back to a moment if it points a little early.
- It works beside a function declaration (a call to a vault tool in the same request chose the right tool). Two samples of agentic on a long video; the latency was 16 and 35 s against 12 to 21 s static on the talk.

- **Full study notes, agentic mode (2026-10-18, one run each, user's go-ahead for these two calls).** The request asked for a title, a summary, a timestamped outline of the whole video, key ideas and five questions. The 12-minute talk: 6,062 tokens in all (105 prompt, 176 tool use, 4,348 thinking, 1,433 reply), 21 s, against 68,533 static for a shorter reply. The 19-minute 3Blue1Brown video: 7,815 tokens (153, 225, 6,188 thinking, 1,249), 24 s. Neither reports any video tokens (tool use is text only), so the cost stays near 5,000 to 8,000 and does not climb toward the static price; the thinking is most of it, and it grows with the length of the video. What Google bills for the frames it fetched is still not known. Both notes were complete (9 and 7 outline sections, timestamps in order, ending near the end of the video); their accuracy was not checked against the video or captions (the caption fetch is blocked on this address), so the content is unread by a human. The reply parts were `toolCall` and `toolResponse` with thought signatures, then the text.
- **A second turn about the same video (2026-10-18, one run each, the 12-minute talk, user's go-ahead).** Turn 1, a three-sentence summary: 4,699 and 4,953 tokens. Turn 2, a question about a timestamp and a figure, with the link kept in history and the reply's text only: 5,141 (and 5,983 with the reply's signature kept, 5,247 with a function declared and the server-tool flag), each time with a new `toolCall`, so **it reads the video again on every turn that asks about it, at about 5,000 to 6,000 tokens, not the 68,000 of the static mode**. The same history sent back in full, with `toolCall`, `toolResponse` and signatures: **refused, 400** ("Tool type of tool_call part does not match with tool call context"), with and without a function declared. Turn 2 with the link left out (text-only history): 964 tokens, no tool call, and a timestamp (2:40) that none of the three runs that read the video gave (2:10 to 2:25, in three phrasings); the figure (300) agreed. So a follow-up without the video is fast and cheap and not grounded. Not measured: a vault function call after the video turns in the same conversation (one request chose the right function beside the video; no second turn).

**3. LiteLLM 1.102 and the provider tools.**

- A YouTube link does not pass through LiteLLM's `gemini/` route. `llms/gemini/chat/transformation.py` converts every `http(s)` file URL to base64 (it downloads the page and sends the HTML as inline data; Google refuses it, 400). The shared conversion function called directly leaves the link as `file_data`, so the fault is in the Google AI Studio route's step before it, and setting `format` does not help.
- LiteLLM has no field for `mediaProcessing`. It does carry `video_metadata` (fps, offsets) and a per-part media resolution.
- Google Search and page reading work through LiteLLM when they are the only tools: a search for the newest stable Python returned 3.15.0 with its source and counted one search request; a page read cost 7,850 tool-use tokens for one page (8,151 in all) and returned the right version. The same question without the tool got "I do not have live access" and a guessed 3.13.2, the failure the provenance rule is for.
- LiteLLM drops the built-in tools whenever a function declaration is in the request: the body sent carried only `function_declarations`. The earlier mixed runs never searched. Over REST the combination works only with `toolConfig.includeServerSideToolInvocations: true` (the API refuses it otherwise); with it, three requests behaved right (a web question searched and read, a vault question called the vault function). The reply then carries `toolCall` and `toolResponse` parts and thought signatures; whether LiteLLM's message history keeps them across turns was not tested.
- So the watch route and the web tools in the same request as the vault tools mean a direct request to the Gemini REST endpoint (`httpx` is already installed), a patch to LiteLLM, or a newer LiteLLM, not an option on the call that exists today. This is the cost of Decision 1 that the ADR did not know.

**4. Captions from this machine.**

- Seven of seven public videos returned captions (a 19-second clip, a talk, a lecture, a music video, a film with almost no speech, a 3.4-hour and a 4.4-hour course), 1 to 2 s each, creator captions in every case (none were auto-generated). A made-up ID fails cleanly (`VideoUnavailable`). The library was `youtube-transcript-api` 1.2.4, in a scratch venv.
- Then YouTube blocked this machine's address for captions: after 17 fetches in a few minutes (the last 10 were the same video in a row), every fetch failed with `IpBlocked`, and it was still blocked when last checked, several minutes later. The watch page and the oEmbed endpoint still answered. Probably temporary, but not checked later. This is the fragility Decision 5 named, shown on a home connection with a modest burst, and a cloud address is blocked from the first request.
- Python on this machine stalls 15 to 30 s on a first request to YouTube because IPv6 connects take 23 s and fail while IPv4 takes 0.02 s; LiteLLM's calls to Gemini are not affected (2.1 s). A caption fetch from Sympose would need IPv4 first or a short connect timeout.

**What this changes (for the user to decide, nothing is edited above).**

- Decision 5's premise that the watch route "costs far more" holds only for the static mode. With the agentic mode the watch route is cheaper than the transcript route for a long video and sees the screen, but it is Gemini only, a preview, and needs the direct request. The transcript route survives as the route for a local model and for the day Google changes the preview; its fetch needs rate limits and a cache, and it will fail on some addresses.
- Decision 5's "low media resolution as the default" is replaced by the agentic mode as the default, and `fps` and offsets for the static fallback.
- Decision 1 needs one more line: the provider's tools are reached by a direct request, because LiteLLM cannot send them (the link, `mediaProcessing`, the tools beside a function).
- Open question "which route is the default": the numbers say agentic, for Gemini; the transcript route for everything else.
- Not measured: the dollar cost of agentic mode and of a search, the free-tier limit, a video without captions in the watch route, a private or age-restricted video, Gemini Pro, other providers' equivalents.

## Slice 1, as built (2026-10-18)

A YouTube link in a message is watched by Gemini Flash and the conversation goes on from there; issue #130 holds the rest.

- **What exists.** `engine/web_access.py` (the knob and the link rule), `engine/gemini_direct.py` (the direct request), the `web` category in `sharing` (so the Cloud models switches, `/share` and the reply header have it without more code), a `web_access` row in the settings registry (group Links), two prompt lines (`WATCHING`, `WITHHELD_WEB`), and `turn._run` handing `lookup.converse` the direct call when a video is to be watched. `network.ipv4_transport()` gives the direct request the same IPv4 rule as LiteLLM's.
- **Settled while building.**
  - *Only `web`, not `media`.* A video link is a link read for the user, so it is `web`; `media` is for files the user attaches and waits for that. *`auto` is not offered:* with nothing but videos to watch it would do what `asked` does, so the knob has `asked` and `off` until search arrives.
  - *The latest link stays.* A message with a link watches it; a later message with none watches the latest link of the conversation (up to 3 links a message), so a question about the video is answered from the video. Measured on the 12-minute talk: a question that needs the video costs about 5,000 to 6,000 tokens, and an unrelated question with the video attached took 3 s and no video look. A carried link is watched only when allowed and is never reported as withheld, so a conversation begun before the user allowed it does not nag.
  - *Only Flash.* `WATCHERS` holds `gemini/gemini-flash-latest`, the one model the agentic mode was measured on; a model joins by measurement, as in `lookup.MEASURED`.
  - *The persona's tools work.* The direct call has `model.call_model`'s arguments and `ModelReply`, so `lookup.converse` takes it as its `call`: `propose_note`, `remember` and the vault tools run on a video turn, and an answer after a tool round does not look at the video again (712 and 489 tokens in the spike, against about 5,000 for a new look).
  - *Streamed.* The request streams (`streamGenerateContent`, SSE), so a stop is heard and the time to the first text is measured; the agentic mode works streamed (the first text came at 11.5 s in the test).
  - *Signatures.* A function call sent back needs a thought signature (a request without one: 400). Sympose keeps the history OpenAI-shaped and does not keep the real one, so it sends Google's documented placeholder, and the answer after the tool round was right with it (a real run filed a note). Not measured: whether the placeholder costs quality over many rounds.
  - *Outside content cannot steer a write.* A turn that watches a video is run without `remember` (the tool and the marker), because what is said or shown in a video could otherwise make a write to the persona's memory, the one write that has no Accept. Proposing a note is unchanged: it waits for Accept. The cost is that "remember this" in the same message as a link is not done; the persona is not told how to, and the user can say it in the next message.
  - *Both channels.* The turn is the engine's, so the terminal watches a video the same way; only the proposal needs the web app.
- **Checked.** 32 tests for the link rule and the request (23 of 23 mutants caught, run by hand with backups), 6 for the turn, 1 for the transport. A real run on a scratch vault with the public TED talk and Flash (the user's go-ahead): the link with `web` not allowed was not opened and the persona said how to allow it (nothing was sent); allowed, a three-sentence summary in 13 s with the header naming `web`; "where does he talk about the passport?" gave timed answers in 12 s; "what is 12 times 12?" with the video still attached took 3 s; "make a short study note and save it" called `propose_note` and left a draft (the vault had no new file until Accept). `/code-review` at `high` gave 6 findings: 3 fixed (a stream error after the reply began was reported as a cut-off, the reply-ending checks were a second copy of `call_model`'s and are now `model.end_reply`, and `remember` above) and 3 left (below). Retrieval eval unchanged after two reference entries (`auto` 62 of 68).
- **Left on purpose.** The latest link is re-sent to Google on every later turn of the conversation, even an unrelated one (about 3 s and no video look when unrelated, but the link leaves the machine each time): the user's call whether to bound it, for example to the next few turns. A new HTTP client for each round of a tool loop. The placeholder signature over many rounds.
- **Seen, not fixed.** The draft has no timestamps and no source link: the capture skill (ADR 077) that carries the note's shape is not written, so a note made from a video is whatever the model writes. The persona's closing line said "accept it in Obsidian" (the reply is from the model, the web app is where Accept is). Not measured: dollars, the free-tier limit, a vault tool beside the video over many rounds, a video that has no captions, a private or age-restricted video, and a second turn on the placeholder signature for a long conversation.

## Consequences

- A cloud model becomes useful for studying: a link goes in, a note in the vault's folder comes out, after Accept.
- The cost of the knob is visible: `asked` costs nothing until a link appears, `auto` costs a tool description every turn.
- Two more things can leave the machine, and both are approved by the user and off by default.
- The persona's answers can now carry web claims, which makes provenance a rule in the prompt, not a habit. A model that blends the two is a bug to fix, the same as a vault claim with nothing behind it.
- The watch route is tied to one provider's preview feature and its prices. If those change, the transcript route is the one that stays.
- A local model gets the transcript route and nothing else.
- A follow-up about a video costs about 5,000 to 6,000 tokens each time it needs the video, and the direct request to Google is the first piece of provider-specific code in the engine.

## Open questions

- Skills are chosen by matching the message to a skill's description (ADR 077), and a message that is only a link gives that match almost nothing. Probably the engine loads the capture skill when a link triggers the tool, the same signal as `asked`, and no new surface; to be settled when it is built.
- Whether a link in a message should make her offer a note in her reply (one line, no draft) or say nothing about it until asked.
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
