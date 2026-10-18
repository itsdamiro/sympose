---
name: capturing-from-a-page
description: Makes a note from a web page the user linked, the key points, the passages worth keeping and a few questions to test oneself, with the page's address as its source. Use when the user asks to save, note, capture or make study notes from a page, an article or a link.
tools: [propose_note, tool_calls]
---
This skill applies only when the message asks for a note. A link alone is not a request for one, and a request for a summary is not one either: answer in the chat and file nothing.

Steps:

1. Use only what the page says, from the page the user linked, below. Never add what you know about the topic or the author from elsewhere.
2. Write the note as properties between `---` lines, then the sections. The properties: `source:` with the page's address exactly as given below, `type: web note`, and `tags:` left empty.
3. The sections, in this order: `## Summary` (two to four sentences), `## Key points`, `## Worth keeping`, `## Questions`.
4. Key points: three to seven short bullets, in the order the page makes them. Worth keeping: up to five passages, each in quotation marks and short, as the page words them, never reworded; leave the section out if nothing is worth quoting.
5. Questions: three to five, each one the user could answer from the page to test themselves.
6. If the page could not be read, say so and propose nothing. If the user asked for a shorter note, or for one section, give that and keep the properties.
7. Call propose_note with the whole text, a title of three to five words (the page's own title when you know it), and one sentence in `say`. Say you have drafted it only after the call. The note exists only when the user accepts it in the app.

Go back to step 4 if a quoted passage is not on the page, word for word.
