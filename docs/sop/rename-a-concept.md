# SOP: name a concept, and rename one

For any assistant. A concept's name is the key shared by the decision records in each repo and the note in the vault's `Concepts/` folder (ADR 011). The sync copies the name from the record, so the two must change together.

## Naming a new concept

1. **Look first.** List `Concepts/`. If the idea has a note, use its name; a near-duplicate (`Pattern` beside `Patterns`) is the mistake the lint hints at.
2. **Name it** as `docs/VAULT_CONVENTIONS.md` says ("Concepts"). It must not share a name with a folder note (`Patterns`, `Tags`, `Concepts`, `Ideas`, `Inbox`), case aside.
3. **Write the note** in `Concepts/` (the owner's, not the sync's), then use the exact name in the `concepts:` line of the record.

## Renaming a concept

1. **Rename the note in Obsidian**, which updates links inside the vault.
2. **Add the old name to `aliases:`** in the concept note, so records that still use it keep resolving.
3. **Change the `concepts:` line** of each record that uses the old name. The lint's `old-concept-name` warnings list them.
4. **Commit the records** with the owner's go-ahead, then run the sync and the lint (the commands are in `docs/VAULT_CONVENTIONS.md`, "Running the sync and the lint").
5. **Done when** the lint shows no `old-concept-name` warning for it. The alias stays; it does no harm and keeps old links readable.

## Do not

- Rename in the vault and skip the alias: the records then fail the lint, and the next sync restores the old name in the cards.
- Let the lint or a script edit the records. It reports; a person or an assistant, on the owner's word, edits.
