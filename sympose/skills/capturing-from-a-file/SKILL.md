---
name: capturing-from-a-file
description: Makes a note from a file the user attached, a PDF, an image, a recording or a video, the key points, the passages worth keeping and a few questions to test oneself, with the file's name as its source. Use when the user asks to save, note, capture or make study notes from an attached file.
tools: [propose_note, tool_calls]
---
This skill applies only when the message asks for a note. An attached file alone is not a request for one, and a request for a summary is not one either: answer in the chat and file nothing.

Steps:

1. Use only what is in the file the user attached, listed below. Never add what you know about the topic or the author from elsewhere.
2. Write the note as properties between `---` lines, then the sections. The properties: `source:` with the file's name exactly as given below (the file itself is not in the vault), `type:` as given below, and `tags:` left empty.
3. The sections, in this order: `## Summary` (two to four sentences), `## Key points`, `## Worth keeping`, `## Questions`.
4. Key points: three to seven short bullets, in the order the file makes them. For a PDF, end a point with the page it is on, as `(p. 4)`. For a recording or a video, begin it with the time, as `[3:10]`, only for a part you listened to or looked at.
5. Worth keeping: up to five passages, each in quotation marks and short, as the file words them, never reworded; for an image, the text written in it. Leave the section out if nothing is worth quoting.
6. Questions: three to five, each one the user could answer from the file to test themselves.
7. If the file could not be read, say so and propose nothing. If the user asked for a shorter note, or for one section, give that and keep the properties.
8. Call propose_note with the whole text, a title of three to five words (the file's own title when it has one), and one sentence in `say`. Say you have drafted it only after the call. The note exists only when the user accepts it in the app.

Go back to step 5 if a quoted passage is not in the file, word for word.
