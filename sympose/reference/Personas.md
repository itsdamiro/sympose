# Personas

A persona, also called an agent or a profile, is a character you chat with, each with its own voice, allowed folders and conversations. Samantha ships with Sympose and is the default. Any other persona is one you create yourself. Only Samantha has this Sympose reference, so a question about Sympose itself goes to her.

## Where does a persona live?

Each persona has its own folder, `profiles/<handle>/`, holding `persona.yaml` (its name, handle, title, allowed folders and optional model, icon and colours), `soul.md` (how it sounds), `sessions/` (its saved conversations) and `recaps/` (short recaps of them).

## How do I create a new persona?

In the web app, ask Samantha to create a new persona, which is also called an agent or a profile. Describe the one you want, such as a patient maths tutor or a calm gardening companion.

A card appears in the chat showing the persona as it would look: its icon and colour, its title, what it may do to your notes, the folders it may read and its soul.

Samantha chooses each of these to suit the character you described, but they are only suggestions. You decide: change the edit mode in the dropdown, switch folders on or off with the pills, and ask Samantha in the chat to change anything else, such as the icon or the soul. Asking again replaces the card with a fresh one.

A persona is created only when you click Accept; until then nothing is made, and Decline makes nothing. Accepting creates the persona with the folders and edit mode as you left them. The model is not part of it: the persona uses your default, and you change it on the Persona page.

Creating a persona works in the web app only, only through Samantha, and only with a model that can call tools, such as a cloud model or gemma4; with one that cannot, such as gemma2:9b, create it by hand. You can create one by hand with any model: a folder named with the handle, lowercase and one word, with a `persona.yaml` and a `soul.md` for its voice.

## What does a persona.yaml look like?

```
name: 'Editor'
handle: 'editor'
title: 'Proofreader'
vault_folders: ['Writing']
model: 'ollama_chat/gemma2:9b'
```

The `model` line is optional.

## How do I give a persona its own icon and colour?

Add `icon: 'leaf'` (a name from the app's icon set, such as brain, book, compass, leaf, star or pen) and `accent: '#c82828'` to its `persona.yaml`, plus `accent_dark` if the colour should differ on a dark theme. The icon and colour show wherever the persona appears. Choosing them in the app is planned.

## What goes in a soul file?

`soul.md` holds a persona's voice and temperament: how it talks and what it is like to be with. It holds no rules and no capabilities, and is best kept around 1.5 KB. A persona without a soul file uses a plain, generic companion voice.

## Can I edit a persona's soul and memory in the web app?

Yes. On the Persona page the FILES chip lists the soul and the three memory files; choosing one opens it in the editor. A saved soul becomes your own copy, `soul.local.md`; the shipped `soul.md` never changes, and Reset to default puts it back. Proposed changes to the profile or context are shown for Review first.

## Can I stop a persona from seeing some of my folders?

Yes. `vault_folders` in `persona.yaml` lists the top-level folders a persona may read, or `'*'` for all of them. It is a hard boundary: searching, note grounding, the web app and the graph all stay inside it. A folder listed there that is not in the vault is not created: the persona simply sees nothing in it, and `sympose doctor` names the entry so a misspelt folder is easy to find.

## Can a persona edit my notes?

A persona can propose changes, new notes and comments in the web app, and you accept or decline each one; it never writes to your vault by itself.

How much it does before your Accept is its `edit_mode`: `plan`, `manual` (the default), `accept` or `auto`. Set it for one persona in its own `persona.yaml` (or in `persona.local.yaml`, which is yours and untracked), or for all personas with the `edit_mode` setting; the Persona page also lets you choose.

`accept` and `auto` show a note about how well the persona's current model edits, so read each change before you accept it.

## How do I switch persona or make one the default?

`/persona` switches persona. `/default` makes the current persona the one Sympose starts with, and remembers it in `settings.json` as `default_persona`.

## What is not built for personas yet?

Memory that grows as you talk, and a separate expertise file, are not built yet.
