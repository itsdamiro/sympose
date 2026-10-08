# Vault conventions: names, fields, tags and links

How this project's decision records are named and written so that the owner's vault can read them. The vault is a folder of Markdown notes (Obsidian); a script in the workflow repository turns each committed record into a read-only card there. Nothing flows back into this repository. The full reasoning is in the workflow repository's ADRs 003, 004, 009, 010 and 011; this page is the short version for working here.

## Records

- **File name.** `docs/decisions/NNN-short-slug.md`: three digits, then lowercase words joined by hyphens. The card in the vault is named from the slug, so keep it short and free of punctuation. The number matches the heading (`# NNN — Title`).
- **Frontmatter on every record**, from `docs/decisions/TEMPLATE.md`: `type: decision`, `status` (`proposed`, `accepted`, `superseded` or `removed`), `date` (`YYYY-MM-DD`), `projects`, `concepts`, `amends`, `supersedes`, `tags`.
- **Summary and sections.** The template shows them: a `> **Summary.**` line, then Context, Decision, Consequences, Alternatives rejected and dated amendments. The card shows the summary, and the vault collects the alternatives in a "Rejected ideas" note.
- **Index.** One row per record in `docs/decisions/README.md`.

## Concepts

- A concept is an idea you would write about; the vault has one note for it in `Concepts/`. A record's `concepts:` line names at least one.
- **Names are sentence case, singular noun phrases:** `Session length`, `Pattern scan`. No ADR numbers, and none of `[ ] | # / : \`. Case does not matter when names are compared; spelling does.
- Write the name exactly as the note is named. If the idea has no note yet, ask the owner to create it: concept notes are the owner's.
- Renaming one: `docs/sop/rename-a-concept.md`. The old name goes under `aliases:` in the concept note, so records that still use it keep working.

## Tags

- Lowercase, kebab-case, namespaced: `type/`, `status/`, `project/`, `topic/`, `lang/`, `source/`. The sync adds `type/`, `status/` and `project/` from the fields; `topic/<word>` is added by hand.
- If you would write about a thing, it is a concept; if you would only filter or count by it, it is a tag.

## Links

- A link to another note is `[[Note name]]`, or `[[Note name|shown text]]`. Links inside a record's frontmatter are quoted (`"[[Note name]]"`). Links in code blocks and inline code are not links.
- A decision card is named `NNN - Sentence from the slug`; link to it as `[[040 - The persona looks up notes itself|ADR 040]]`. In the repository, link records by relative path as usual.
- Every note should link to at least one other and be linked from one. The lint warns; it does not fail.

## Running the sync and the lint

Both live in the workflow repository and take paths as arguments. Nothing is installed in this project.

```
python3 <workflow>/scripts/vault_sync.py <this-project> <vault> --name <ProjectName> --dry-run
python3 <workflow>/scripts/vault_sync.py <this-project> <vault> --name <ProjectName>
python3 <workflow>/scripts/vault_lint.py <vault>
```

The sync reads the committed records only, so commit first. It overwrites only notes marked `generated: true`. A lint error is reported and never fixed by the script; a concept with no note is for the owner to settle.

## Do not

- Copy anything from the vault into this repository, or put a private name or an absolute home path in a record. The repository may be public.
- Write a claim into a vault card by hand: the next sync overwrites it. Edit the record instead.
