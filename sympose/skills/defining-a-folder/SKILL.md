---
name: defining-a-folder
description: Proposes the definition note of one folder, saying what the folder is for and what its notes carry. Use when the user asks to define, describe or explain a folder, or says what a folder is for, or agrees when you offer to.
tools: [propose_folder_definition, tool_calls]
---
Steps:

1. Pick the one top-level folder, from the user's words and the vault map. If two fit, ask which. A folder the vault map already shows with a purpose has a definition: say so, and send the user to Folder settings to change it.
2. Find what the folder is for. If the user said, use their words. Otherwise use the note titles and sub-folder names you were given or can look up, and write one or two plain sentences about what they show. If you know none, or they show nothing in common, leave the purpose empty: never guess one from the folder's name.
3. Never write the property lines yourself: Sympose counts them from the folder's real notes.
4. Call propose_folder_definition with the folder, the purpose sentence (empty if you have none) and one sentence in `say`. Say you have proposed it only after the call. If the purpose is empty, say so in one sentence: the user can type it into the draft before accepting. The note exists only when the user accepts it.

Go back to step 2 if the purpose sentence says something the titles do not show.

Example: for "what is my Movies folder for?" with titles like "Arrival (2016)" and "Heat" and a sub-folder "Watchlist", the purpose is "Films the user has watched or wants to watch, one note each." and the call is made with that, never with a list of properties.
