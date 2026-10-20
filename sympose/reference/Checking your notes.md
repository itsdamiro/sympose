# Checking your notes

## How do I check my notes for problems?

Run `sympose vault --health`, or choose Notes check in the web app's Settings. It reads your notes and reports what it finds, grouped by folder: empty notes, links to no note, titles that are not the file name, and files that are not notes. It only reads: it never changes a note and never calls a model. `sympose vault --fix` is the command that repairs some of what it finds.

`--persona` followed by a handle reads what that persona can read. Without it, the default persona is used.

## What do the notes check's notices about moved folders mean?

They are observations, not faults. "Folder notes inside sub-folders" lists a note named after its folder (like `Projects/Garden/Garden.md`) in a folder that is not at the top: only a top-level folder's note is read as its description, so it may be a description that stopped applying after a move.

"Possible duplicate notes" lists a note like a note called Recipe (2) beside one called Recipe, which is what a folder merge makes of two notes with one name. Combine them by hand if they are duplicates.

## What counts as an empty note?

A note with no text and no properties, so nothing but its file name. A note that is only a title, or only properties, is not empty.

## What is a link to no note?

A wikilink, like [[Some note]], that names a note that does not exist, often left behind by a rename or a move. Links written as Markdown links, like [text](Note.md), are not checked, and an example link inside a code block is read like any other.

## What does a folder that no longer matches mean?

A wikilink written with a folder, like [[Archive/Idea]], where no note is at that path any more because the note moved, though one note still has that name. Obsidian reads the folder as a path and does not find it. `sympose vault --fix` can point it at the folder the note is in now. If several notes have the name, nothing is offered.

## What is a title that is not the file name?

A note whose `title` or `name` property says something other than its file name, ignoring case and spacing. Sympose treats the two as one thing, and the title as the right one.

A note with no title property, or a blank one, uses its file name as its title, so it is not reported. A title a file name cannot hold, such as one with a colon, is reported as one that cannot match.

## Does the report mention files that are not notes?

Yes, as clutter: files in your vault that Sympose does not read as notes, like .txt or .markdown files, and files with no extension. Images, audio, video, PDF, Obsidian's own canvas and base files, hidden files and the folders Sympose skips are not clutter.

Clutter is listed after the problems and is not one. It only tells you the files are there.

## Does the health check fix anything?

No. `sympose vault --health` only reports and does not change your notes.

## How do I fix what the check finds?

Run `sympose vault --fix` in a terminal. It offers each repair one at a time, shows what would change, and makes it only when you answer yes. `q` stops, and anything else leaves the note as it is. It never changes anything in bulk.

## Which repairs does the fix make?

Three: renaming a note to its title (the links to it are updated), pointing a link at the folder its note moved to, and adding a folder's icon to its definition. The vault is read again after every answer.

## When does the fix leave a title alone?

When another note is already called by the title, when another note shares the note's own file name, or when the title holds a character a file name or a link cannot. A plain link to a name several notes share could reach a different note after a rename, so those stay in the report. Empty notes are never deleted.

## What is a folder definition?

A note named after a top-level folder, like People/People.md, that says what the folder is for and holds a template of the properties its notes carry. Sympose can draft one for a folder that has enough notes and no definition yet, with `sympose vault --draft People`. In the web app, right-click the folder and choose Folder settings to make or change one yourself.

## Can the persona define a folder for me while we talk?

Yes, with a model that can call tools. Ask it to define a folder and it proposes the definition note as a draft; nothing is saved until you accept. It writes the purpose from the note titles, and the property list is counted from the folder's real notes, never written by the model.

## Which folders does the report offer a definition for?

Top-level folders with five or more notes and no definition. `folder_definition_min_notes` changes the five. They are listed under Folders due a definition, as an offer and not as a problem.

## How does a draft work?

`sympose vault --draft People` shows the note it would create and writes it only if you answer yes. A note that already exists is never replaced.

The template is counted from the folder's real notes: a property is in it when at least half of them carry it (`folder_template_share`). Nothing in it is invented.

## Who writes the purpose in a draft?

The model does, from the titles of the folder's notes and the names of its sub-folders, never from a note's text or properties. If the titles do not show what the folder is for, the purpose is left empty for you to write.

## Does a draft send my notes to a cloud model?

With a local model nothing leaves your computer. With a cloud model, only the folder's note titles and sub-folder names would be sent, and only if notes are allowed for cloud models (`cloud_share`, and /share). Otherwise nothing is sent and the purpose is left empty.
