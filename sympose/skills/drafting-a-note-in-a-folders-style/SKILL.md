---
name: drafting-a-note-in-a-folders-style
description: Drafts a new note in the style of a vault folder, following that folder's definition note and its template. Use when the user asks to add, write down, draft or create a new note, such as a recipe or a person, in a folder.
tools: [propose_note, tool_calls]
context: folder
---
Steps:

1. Pick the folder the note belongs in, from the user's words and the vault map. If two folders fit, ask which.
2. Below these steps are the folder's definition and one note already in it, exactly as stored. If they are not there, use the notes you were given, or look them up with your tools.
3. Write the new note in that shape, character for character: the property lines between `---` lines, with the same property names, then the same `##` sections in the same order.
4. Fill only what the user gave. A property or section they gave nothing for stays empty (`tags:` with nothing after it). Never invent a tag, rating, date, amount or detail, and leave no placeholder text.
5. Call propose_note with the whole text, a title of three to five words, and one sentence in `say`. Say you have drafted it only after the call. The note exists only when the user accepts it.

Go back to step 3 if the draft lacks a property or a section the folder's notes have.

Example: for "add a recipe: mushroom risotto, serves 3, 45 minutes" in a folder whose template has type, servings, time, rating, tags and sections Ingredients, Steps, Notes, the note holds `type: recipe`, `servings: 3`, `time: 45min`, an empty `rating:` and an empty `tags:` between `---` lines, then the three sections, with only what was said under them.
