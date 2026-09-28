# The web app

The web app, also called the dashboard, is Sympose's browser app for your vault. It works on the active vault and stays inside the folders the active persona may see. Start it with `sympose web`.

## What can I do in the web app?

Browse your notes and folders in a tree, edit notes in a markdown editor, create, rename and delete notes and folders, search the whole vault from the search bar, and switch or add vaults from the workspace switcher.

## What happens to links when I rename a note?

The web app updates the wikilinks (the double-bracket kind) in every other note that points at it, and touches nothing else in those notes. Two limits: links written as Markdown links, like [text](Target.md), are not updated, and a wikilink you show as an example inside a code block or in inline code is changed too, which Obsidian would not do. Check such a note after a rename.

## How do I get back a note I deleted?

A deleted note or folder goes to the Bin, which is the vault's trash (the `.trash` folder), so it is not gone for good. Open the Bin to restore a note, or delete it permanently.

## How do I hide a note or folder from view?

Right-click it, or long-press on a touch screen, and choose "Hide from view". It leaves the tree, the recent and pinned lists and the Knowledge Nebula, and clicking a link to it does nothing. Hiding is for the view only: Samantha can still read a hidden note, and search still finds it, greyed out.

## How do I show a hidden note again?

Choose Unhide beside it in the search results, or in the "Hidden from view" part of Settings, which lists everything you hid. That part also decides whether the folder definition notes, left out of the tree by default, are listed.

## What is the Knowledge Nebula?

The Knowledge Nebula is a graph of your notes, in 2D or 3D. Each note is a point and the links between notes are the lines. It shows only the folders the active persona may see.

## Can I chat in the web app?

Not yet. The web app has a chat panel, but it is only a design mock for now. Chatting works in the terminal.
