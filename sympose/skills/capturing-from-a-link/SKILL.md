---
name: capturing-from-a-link
description: Makes a note from a video the user linked, an outline with timestamps that link back to the moment, the key ideas and questions to test oneself, with the link as its source. Use when the user asks to save, note, capture or make study notes from a video or link.
tools: [propose_note, tool_calls]
---
This skill applies only when the message asks for a note. A link alone is not a request for one, and a request for a summary is not one either: answer in the chat and file nothing.

Steps:

1. Use only what you saw and heard in the video the user linked, below. Never add what you know about the topic or the speaker from elsewhere.
2. Write the note as properties between `---` lines, then the sections. The properties: `source:` with the video's address exactly as given below, `type: video note`, and `tags:` left empty.
3. The sections, in this order: `## Summary` (two to four sentences), `## Outline`, `## Key ideas`, `## Questions`.
4. In the outline, one line per part of the video, in order, to its end: the time in square brackets and nothing else around it, then a short title and one sentence. Write the time as `[3:10]` or `[1:02:15]`, never as a link; Sympose turns it into one. Give a time only for a part you looked at.
5. Key ideas: three to seven short bullets. Questions: three to five, each one the user could answer from the video to test themselves.
6. If the user asked for a shorter note, or for one section, give that and keep the properties.
7. Call propose_note with the whole text, a title of three to five words (the video's own title when you know it), and one sentence in `say`. Say you have drafted it only after the call. The note exists only when the user accepts it in the app.

Go back to step 4 if the outline has a time you did not look at or stops before the end of the video.

Example outline lines: `- [0:00] Why the problem matters: he sets up the question the talk answers.` and `- [12:40] The first result: ...`.
