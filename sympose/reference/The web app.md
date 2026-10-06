# The web app

The web app, also called the dashboard, is Sympose's browser app for your vault. It works on the active vault and stays inside the folders the active persona may see. Start it with `sympose web`.

## What can I do in the web app?

Browse your notes and folders in a tree, edit notes in a markdown editor, create, rename, move and delete notes and folders, search the whole vault from the search bar, and switch or add vaults from the workspace switcher.

## What happens to links when I rename a note?

The web app updates the wikilinks (the double-bracket kind) in every other note that points at it, and touches nothing else in those notes. Two limits: links written as Markdown links, like [text](Target.md), are not updated, and a wikilink you show as an example inside a code block or in inline code is changed too, which Obsidian would not do. Check such a note after a rename.

## How do I rename or move a folder?

Rename it from its ⋯ menu (or a right-click) in the tree. To move it, drag its row onto another folder, onto the heading of the folder you are in, onto a root folder in the main menu, or onto the vault name or the empty space below the root folders to move it to the top of the vault.

Sympose asks first when something needs your word: a folder with that name is already there (merge into it, or move it under another name), files are in both (the incoming ones are renamed, for example Recipe (2), and nothing is overwritten), or the move changes which notes a persona may read.

It then rewrites the wikilinks that name the folder, and updates the personas' folder lists, the hidden list, pending changes, pins and recent notes. Links written as Markdown links, like [text](Folder/Note.md), are not changed.

## What are tracked changes and comments?

When a persona proposes a change to the note you have open, the editor shows it as a tracked change: the old text struck through and the new text beside it, each with Accept and Decline. The toolbar has Accept all and save, and Decline all, for the whole note. A change you edited underneath is marked outdated, not merged.

To leave a comment, select text and choose Comment; the persona reads your open comments with your next message and can reply or propose a change. A comment can be resolved, and a persona's own comment can be accepted or declined (declining needs your reply first). Nothing reaches the file until you accept or save. This is web app only.

A comment's words are highlighted in the note. Click the highlight to open the thread, where you can reply, resolve it or delete it; a comment the persona leaves is opened the same way. Comments on exactly the same words share one highlight and one box, with a thread for each. There is no separate comments panel.

In a table, a persona can propose a change to the words of one cell. She cannot propose removing a table or a row, or reshaping it, so she says so and leaves a comment; you make that change yourself in the editor.

## How do I point the persona at a part of my note?

Click the paperclip on a tracked change, in the box that opens on a comment, or above commented words when you point at them. The words appear as a chip under your message, and the persona is sent that part of the note, so she knows which one you mean. Remove the chip with its own button. A message you sent with a chip shows a paperclip beside its time.

Without a chip she is sent the whole open note. With one, a model that can use tools gets the note's headings and the section the words are in, and can open the rest if it needs it.

## What is the Drafts section?

At the top of the notes list, the Drafts section lists the notes in the folder you are viewing that a persona has proposed changes to, the new notes she has proposed, and the notes with an open comment. Choose one to open it. Right-click a note in it for the same menu as in the notes list, such as rename or delete. A new note she proposed has no file yet: it is created when you accept it.

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

## What is the Knowledge Nebula?

The Knowledge Nebula is a graph of your notes, in 2D or 3D. Each note is a point and the links between notes are the lines. It shows only the folders the active persona may see.

## Can I chat in the web app?

Not yet. The web app has a chat panel, but it is only a design mock for now. Chatting works in the terminal.
