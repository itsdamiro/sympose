---
name: drafting-a-note-in-a-folders-style
description: Drafts a new note in the style of a vault folder, following that folder's definition note and its template. Use when the user asks to add, write down, draft or create a new note, such as a recipe or a person, in a folder.
tools: [propose_note]
---
Steps:

1. Pick the folder the note belongs in, from the user's words and the vault map. If two folders fit, ask which.
2. Find the folder's definition note (the note named after the folder, such as `Recipes/Recipes.md`) and one or two notes already in the folder: use the notes you were given, or look them up with your tools if you have them.
3. Write the new note in the same shape: the properties of the definition's `## Template` block, then the same sections in the same order as the notes in the folder.
4. Fill only what the user gave. A property or section they gave nothing for stays empty. Never invent a rating, a date, an amount or a detail.
5. Propose the note the way your editing instructions for this turn say (the propose_note tool, or its marker), with the whole text, a title of three to five words, and one sentence in `say`. The note exists only when the user accepts it.

Go back to step 3 if the draft lacks a property or a section the folder's notes have.

Example: for "add a recipe: mushroom risotto, serves 3, 45 minutes" in a folder whose template has type, servings, time, rating, tags and sections Ingredients, Steps, Notes, the note holds `type: recipe`, `servings: 3`, `time: 45min`, an empty `rating:`, and the three sections, with only what was said under them.
