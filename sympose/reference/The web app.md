# The web app

The web app, also called the dashboard, is Sympose's browser app for your vault. It works on the active vault and stays inside the folders the active persona may see. Start it with `sympose web`.

## What can I do in the web app?

Browse your notes and folders in a tree, edit notes in a markdown editor, create, rename, move and delete notes and folders, search the whole vault from the search bar, and switch or add vaults from the workspace switcher.

## Do pictures in my notes show in the web app?

Yes. A picture written `![[shot.png]]` or `![description](assets/shot.png)` is drawn in the editor, on a line of its own or inside a sentence, a list item, a quote or a heading. A size can follow a bar: `![[shot.png|300]]` is 300 pixels wide and `![[shot.png|300x200]]` is 300 by 200.

A picture in a table cell, one that is also a link, and one inside code stay as written while you edit. PNG, JPEG, WebP, GIF and SVG show, up to 20 MB each, from any folder the persona can read (Attachments too) except one starting with a dot, like .obsidian.

A name with no folder is looked for from the vault's root, then from the note's folder, then in every folder the persona may see, the shortest path first, in any case. A picture from a web address (http, https or data) is never loaded and stays as written, as does a reference to a missing file. Pictures are not listed in the tree, the graph or the search, and a persona does not see them.

## What happens to links when I rename a note?

The web app updates the wikilinks (the double-bracket kind) in every other note that points at it, and touches nothing else in those notes. Two limits: links written as Markdown links, like [text](Target.md), are not updated, and a wikilink you show as an example inside a code block or in inline code is changed too, which Obsidian would not do. Check such a note after a rename.

## How do I rename or move a folder?

Rename it from its ⋯ menu (or a right-click) in the tree. To move it, drag its row onto another folder, onto the heading of the folder you are in, onto a root folder in the main menu, or onto the vault name or the empty space below the root folders to move it to the top of the vault.

Sympose asks first when something needs your word: a folder with that name is already there (merge into it, or move it under another name), files are in both (the incoming ones are renamed, for example Recipe (2), and nothing is overwritten), or the move changes which notes a persona may read.

It then rewrites the wikilinks that name the folder, and updates the personas' folder lists, the hidden list, pending changes, pins and recent notes. Links written as Markdown links, like [text](Folder/Note.md), are not changed.

## How do I change a folder's icon, colour or description?

Right-click a top-level folder in the main menu and choose Folder settings. Type in the Icon field (film, travel, food) and pick from the matches, choose a colour for the Knowledge Nebula, and say what the folder is for and which properties its files start with.

Save puts them in the folder's definition, like People/People.md, and changes only what you changed. A new folder offers the same dialog when you make it, and Skip leaves everything as it was.

## How do I give a folder inside another folder its own icon or colour, to tell projects apart?

Right-click a folder that sits inside a top-level folder, like Projects/sympose, in the folder list and choose Folder look. Pick an icon, a swatch or a Light and a Dark colour, and Save. The folder is drawn with that icon in the list, and its notes in that colour in the Knowledge Nebula, where the legend lists it by its path, so one project is easy to tell from another.

The colour is kept in the top-level folder's own note, like Projects/Projects.md, in a subfolders property, so no extra note is made for it. A note takes the colour of the nearest coloured folder around it, at any depth, and keeps its top-level folder's colour when none of them has one. Renaming or moving the folder takes its look with it, and the cross in each field removes it.

## What are tracked changes and comments?

When a persona proposes a change to the note you have open, the editor shows it as a tracked change: the old text struck through and the new text beside it. A small tab above it holds Accept and Decline (and a paperclip). A block at the top says how many changes the persona suggested, with Accept all (which saves) and Decline all. A change you edited underneath is marked outdated, not merged.

To leave a comment, select text and choose Comment; the persona reads your open comments with your next message and can reply or propose a change. A comment can be resolved, and a persona's own comment can be accepted or declined (a reason is optional). Nothing reaches the file until you accept or save. This is web app only.

A comment's words are highlighted in the note. Click the highlight to open the thread, where you can reply, resolve it or delete it; a comment the persona leaves is opened the same way. Comments on exactly the same words share one highlight and one box, with a thread for each. There is no separate comments panel.

In a table, a persona can change the words of one cell. A model that can use tools can also add or remove a row or a column, by replacing the whole table.

You then see the table's source, the old rows struck and the new ones beside them, with one Accept and Decline for the whole table, and she says in her reply what she changed. She cannot remove the table or reshape it in other ways, so she says so and leaves a comment.

## Where do I click Accept or Decline on a change?

In the note, a small tab above the changed words holds Accept and Decline, and a paperclip. For a new note the persona proposed, the block above the draft has Accept and Decline. For the whole note, the block at the top has Accept all and Decline all.

## How do I point the persona at a part of my note?

Click the paperclip on a tracked change, in the box that opens on a comment, or above commented words when you point at them. The words appear as a chip floating above the message box, and the persona is sent that part of the note, so she knows which one you mean. Remove the chip with its own button. A message you sent with a chip shows a paperclip beside its time.

Without a chip she is sent the whole open note. With one, a model that can use tools gets the note's headings and the section the words are in, and can open the rest if it needs it.

## Can she bring a note up on screen for me?

Yes. Give her a note's name or path and the web app shows it in the editor panel, for reading. A model that can call tools does it as is. For one that cannot, such as gemma2:9b, turn on the `show_note_marker` setting (opening notes on a model without tools); it costs that model some edits. Nothing in your vault changes, and she says so when there is no such note.

## What is the Drafts section?

At the top of the notes list, the Drafts section lists the notes in the folder you are viewing that a persona has proposed changes to, the new notes she has proposed, and the notes with an open comment. Choose one to open it. Right-click a note in it for the same menu as in the notes list, such as rename or delete.

A new note she proposed has no file yet: it is listed here only in the folder it will be made in (the Inbox folder unless another was named), and it is created there when you accept it.

## How do I get back a note I deleted?

A deleted note or folder goes to the Bin, which is the vault's trash (the `.trash` folder), so it is not gone for good. Open the Bin and choose Notes to restore a note, or delete it permanently.

## How do I get back a conversation I deleted?

A deleted conversation goes to the Bin too, in its own Conversations part, apart from the notes. Choose Conversations there and restore it: it returns to the persona's list, pinned as it was. Deleting it from that part is for good, and it asks first.

## How do I hide a note or folder from view?

Right-click it, or long-press on a touch screen, and choose "Hide from view". It leaves the tree, the recent and pinned lists and the Knowledge Nebula, and clicking a link to it does nothing. Hiding is for the view only: Samantha can still read a hidden note, and search still finds it, greyed out.

## How do I show a hidden note again?

Choose Unhide beside it in the search results, or in the "Hidden from view" part of Settings, which lists everything you hid. That part also decides whether the folder definition notes, left out of the tree by default, are listed.

## Can I go back to an older conversation while a persona is replying?

Yes. The persona's profile, opened from its name at the bottom of the menu, lists its conversations with the pinned ones first. Click one to open it, whatever the persona is doing. A reply always lands in the conversation it was sent from, which shows replying until it arrives and a dot after it, until you read it.

The row's ⋯ menu, or a right-click, pins, renames or deletes a conversation, and New starts a fresh one.

## Can I archive a conversation?

Yes: Archive to note, on a conversation's ⋯ menu. It needs at least two messages and no reply being written. The persona's model sums up what you said in a title, what it was about, what was decided and what was left open.

The summary does not exist as a file yet. It waits in Drafts, filed for a folder called Sessions inside the persona's first folder (the top of the vault when the persona sees all of it). Open it, change what you like, and keep it or drop it. With a cloud model your messages go to it, so recaps must be allowed in /share.

## Can a persona do something by itself on a schedule?

Yes, as a job. A job is a small file in the persona's own folder, never in your vault. In Settings, under Jobs, Add a job makes one that starts off. Open it from the ⋯ menu on its row, write when it runs (such as `weekly sun 18:00` or `daily 07:30`) and what to do, then switch it On.

Whatever a job produces waits in Drafts for you to accept, so a job never touches your vault by itself. A job can propose notes to add but not alterations to one you already have. A job that uses a cloud model runs once a day unless its file says otherwise.

## Where can I read what my job said?

In the job's one conversation. Every run of a job is added to it, so it is a single row in your list of conversations, marked with a clock; open it to read and reply. The next run sees the last few turns of it.

## How do I rename or delete a job?

In Settings, under Jobs, open the ⋯ menu on the job's row. Rename turns what you type into a file name (`Weekly review` becomes `weekly-review`) and keeps its last run. Delete asks first and keeps a copy of the file beside the others, with .bak added to its name. A job that is running right now has to finish first.

## How do I give a job another model?

In Settings, under Jobs, click the model on the job's row and pick another. The choice is written in the job's file as `model`, so it is the same as editing the file. "Use the default" takes it off, and the job follows the persona's model again. A job that uses no model, such as the notes check, has no picker. A cloud model still receives only what you allow in Settings.

## What goes in a job's file?

Which schedules can you write for a job? The schedule of a job is one of `daily 07:30`, `weekdays 07:30`, `weekly sun 18:00`, `monthly 1 09:00` (a day from 1 to 28) and `every 6 hours` (1 to 168), on your own clock. No other schedule is understood, such as twice a day or every other week.

A job's file has a few lines of properties, then what to write for the job to do. `schedule` is one of those, `kind` is `ask` (a turn with the persona's model, the usual), `health` or `refresh`, and `enabled` is true or false.

`health` (the notes check) and `refresh` (rebuilds the search index) use no model and need no text below. Optional: `model`, for another model than the persona's, and `max_runs_per_day`, a whole number. A persona can write this file for you to paste in, and you switch the job on yourself.

## Do jobs run when Sympose is closed?

While the web app is open, yes, and a time missed while it was closed runs when you next open it. On a Mac, switch on Run while Sympose is closed under Jobs in Settings, or run `sympose schedule install`, and the computer checks every 5 minutes with the app closed.

`sympose schedule remove` takes that away. `sympose run --due` runs what is due now and `sympose run persona/job` runs one job now.

## Why does a job stop making drafts?

A job that already has 5 of its drafts waiting skips its later runs, so nothing piles up while you are away, and a skipped run costs nothing. Its row in Settings shows a draft icon with the number waiting, in red once it is full. Accept or decline some in Drafts and the next run goes ahead. The 5 is the `waiting_drafts` setting.

## Why did a job stop running?

A job that fails 3 times in a row switches itself off, and its row in Settings says so. Fix the cause, then switch it On to start it again. A job whose file cannot be understood, such as a schedule it cannot read, shows what is wrong in its row and does not run.

## What is the Knowledge Nebula?

The Knowledge Nebula is a graph of your notes, in 2D or 3D. Each note is a point and the links between notes are the lines. It shows only the folders the active persona may see.

## Can I chat in the web app?

Yes. The web app has the same chat as the terminal, in a panel beside your notes. Pick a model, attach a file, stop a reply while it is written, and use the Condense button to shorten a long conversation. A change a persona proposes to a note waits for your Accept in the editor.
