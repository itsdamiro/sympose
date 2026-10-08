---
type: decision
status: accepted
date: 2026-09-26
projects: [sympose]
concepts: [Vault upkeep]
amends: [11]
supersedes: []
tags: [type/decision, status/accepted, project/sympose]
---

# 029 — `sympose doctor`: a health check for an installation, that fixes only what belongs to Sympose

> **Summary.** `sympose doctor` is a health check that only looks unless run with `--fix`, and it fixes only what belongs to Sympose (its `profiles/` and `settings.json`). Installs failed silently, for example a persona folder named `Grace` that works on macOS and vanishes on Linux. It exits 1 when a problem remains.

> **Status: Accepted.** Not built yet; this record comes first, as the standards ask. Amends ADR 011's note that directory names are "expected to be lowercase handles" by giving that expectation a check and a fix.

## Context

Several things in an installation go wrong without saying so. A persona folder named `Grace` is listed on a machine whose filesystem ignores case (the macOS default) and is missing from the roster on one that does not (Linux), so the same folder works on one machine and vanishes on another, with no message (issue #72). A `persona.yaml` that does not parse drops its persona from the roster with no message either. A hand-edited settings file can hold a `chat_model` or `default_persona` that is null, blank or not text, and a `default_persona` can name a persona that does not exist, which fails every request that names no persona. Each of these was found by reading code or by a review, not by anything the person running Sympose could see. What is missing is one place that looks at the installation, says plainly what is wrong, and can put right the part that is Sympose's own.

## Decision

**The command.** `sympose doctor` is a third subcommand of the `sympose` command (ADR 028). Run alone it only looks: it prints each problem in plain words, says what `--fix` would do about it or that it needs the person, and exits 0 when nothing is wrong and 1 when something is. `sympose doctor --fix` applies the fixes that are safe and says what it did; it exits 1 only if a problem is left that it cannot fix. It reads and changes only the folder Sympose runs in (the same `profiles/` and `settings.json` the rest of Sympose uses, including the `SYMPOSE_PROFILES_DIR` and `SYMPOSE_SETTINGS_PATH` overrides).

**What it may change: Sympose's own files, never the notes.** Persona folders, `settings.json` and other files Sympose creates are Sympose's to keep to a standard. The notes and folders of the vault are the person's own content, and the doctor never renames, rewrites or deletes them, so a vault with mixed-case note names is not a finding. Renaming notes would also rewrite every link that points at them, which is the most fragile part of the write layer (issues #42, #43 and #46), and a mixed-case name is not a failure today. If a real failure with a particular kind of note name is ever found, it is fixed at that point, not by a bulk rename.

**The first checks.**

- **A persona folder whose name is not lower case.** Handles are lower case everywhere in the code, so the folder must be. Fix: rename it to lower case. On a filesystem that ignores case the persona works either way, and it is still reported, since the folder will fail the day it is copied to a machine that does not. If a folder of the lower-case name already exists as a different folder (possible only on a filesystem that keeps case), nothing is renamed and the report names both. Any code that later creates a persona lower-cases its handle first.
- **A `persona.yaml` that cannot be read or is not a mapping.** The persona is missing from the roster. No fix: the file is the person's writing, so the message names the file and the parse error.
- **A settings file that cannot be read** (not JSON, or not an object). It is read as empty today, so every setting is quietly the default. No fix; the doctor names the file and does not overwrite it.
- **A `chat_model` or `default_persona` that is null, blank or not text,** and **a `default_persona` that names no persona in the roster.** Fix: remove the key, so the shipped default applies again (never write the default in as a literal, which would turn it into a setting the person seems to have chosen).

Each check is one function returning a list of findings (what is wrong, what `--fix` would do, and the action itself, or none), so a later check is one more function and the command needs no other change.

**Nothing changes without `--fix`**, and every fix touches one named file or folder and prints what it did.

## Consequences

- A person who copies a folder to another machine, or edits a settings file by hand, has one command to run and a plain answer, where before the answer was a persona that quietly did not appear.
- The persona-folder case problem (#72) gets its fix. The roster itself is unchanged and still lists only lower-case folders on a filesystem that keeps case; a start-up notice for that case is a separate step (below), so #72 stays open until it exists.
- The list of checks grows with real findings only. A check earns its place the way the standards' rules do: because something went wrong without saying so.
- A rename or a removed key is not undoable by the command. Both are small, named and printed, and the only file rewritten (`settings.json`) goes through the atomic writer (ADR 003's file, `atomic_write`).

## Alternatives rejected

- **Lower-casing vault folders and notes too.** Rejected for the reasons above: they are the person's content, mixed-case titles are normal in Obsidian, and a rename means rewriting links.
- **Fixing by looking the persona folder up under its real name** (so `Grace` is found on any filesystem) **instead of renaming.** Rejected as the answer to the roster: it keeps two spellings of one handle alive in the code and the session paths, and the handle everywhere else is lower case. Kept as a fallback only if the rename proves unwelcome.
- **Checking on every start-up instead of on request.** Rejected for the first version: it adds work and output to every launch for problems most installations do not have. A one-line notice at start-up, only when a persona is actually being missed, is the proposed follow-up.
- **`--fix` as the default, or asking a question for each fix.** Rejected: a command that changes files should say what it will do first, and a prompt per fix does not work in a script.
- **A separate file per check or a plugin mechanism.** Rejected: a list of functions in one module is all that four checks need.

## Not built yet

Everything above. Later, and each needing its own reason: the start-up notice for a persona folder the roster misses, a check that Ollama is running and has the configured embedding and chat models (the most common reason search quietly falls back to keywords), notes with a `.txt` or `.markdown` extension (#52), a byte-order mark hiding frontmatter (#50), and a damaged session file or embedding cache.

## Update: which models are in use, and what may reach them (issue #79)

**Context.** ADR 031 lets the user approve, per category, what a cloud model may receive, and `/share` and the model picker show it inside the chat. Nothing shows it from outside the chat, so someone who wants to know "where do my notes go?" has to start the chat and open a menu. The settings that decide it are spread over `chat_model`, a persona's own `model`, `embedding_model` and `cloud_share`.

**Decision.** `sympose doctor` prints a short section, "Models and what leaves this computer", before the findings, every time (it is a report, not a problem, so it changes neither the findings nor the exit code):

- The chat model a message runs on when nobody chooses one (the `chat_model` setting, else the shipped default), and each persona that names a model of its own in `persona.yaml`.
- The embedding model that search by meaning uses.
- For each: `local: nothing leaves this computer`, or `cloud: it receives your messages and this conversation` and then which categories of the vault it may receive (the approved ones in `cloud_share`), and which are held back. For a cloud embedding model, what it would receive is every passage of the notes and every message, so it says that, and whether `notes` is approved.

**One finding.** A cloud embedding model with `notes` not approved is a finding (it needs the person, so `--fix` does nothing): search by meaning is then off and notes are searched by keyword, quietly, with only a line in the log. The doctor says so and says how to allow it (`/share` in the chat, or `cloud_share` in the settings file).

**Not a finding.** A cloud chat model with nothing approved is the default (ADR 031) and is not reported as a problem; the section says what it receives.

**Why in its own module.** `doctor.py` is at the file-size cap; the report is one function that reads settings and calls `sharing`, so it goes in `doctor_models.py`, and `doctor.py` only calls it.

**Alternatives rejected.** Printing the section only when a cloud model is chosen: the same command should answer "everything stays here" as plainly as "this is sent", and a person cannot tell a silent report from a broken one. Listing every persona: only the ones that name a model differ from the default. Having `--fix` remove a cloud embedding model or approve `notes`: it is the person's decision what leaves the machine.

## Update: the start-up notice for a persona folder the roster misses (issue #72, decided 2026-09-27)

**Decision (the user's).** Option A of #72 stands: persona folder names must be lower case, `sympose doctor --fix` renames them (built), and the roster is unchanged. What this update adds is the notice that ADR 029 left for later, so a persona is never dropped without a word.

**The notice.** When `sympose cli` or `sympose web` starts, it looks in the profiles folder for a persona folder (one holding a `persona.yaml`) whose name is not lower case and which the roster cannot find under its lower-case name. On a file system that ignores case (the macOS default) every such folder is found, so nothing is said and nothing is missing; on one that keeps case (Linux) each of them is a persona the person cannot choose. The message names the folders and says how to fix it: "Persona folder 'Grace' is missing from the roster: its name is not lower case, and this file system keeps case. `sympose doctor --fix` renames it." The CLI shows it as a red line under the banner, and `sympose web` prints it before the address. It is said once per start, only when something is actually missed, and it changes nothing on disk. The two folders that would clash (`Grace` and `grace` both present) are not "missed": the roster shows `grace`, and the doctor already reports the clash.

**One place.** `persona_files.missed_notice()` builds the message from `missed_folders()`, and both starts call it; the doctor's own check keeps reporting the mixed-case folder on any file system, since it fails the day the folder is copied to one that keeps case.

**Consequences.** #72 is closed by this: the check and the fix (ADR 029), and the notice. A person on a case-keeping file system who never runs the doctor still learns why a persona is missing, at the moment it matters.

**Alternatives rejected.** Looking the folder up under its real name (option B): decided against by the user, for the reasons in "Alternatives rejected" above. Warning on every roster lookup: the roster is read by every request, so it would repeat. Refusing to start: the other personas work.

## Update: looking at a persona's folders creates nothing; a folder that is not in the vault is reported (issue #51, decided 2026-09-27)

**Context.** `vault_paths.get_allowed_dirs` made every folder in a persona's `vault_folders` exist, and the vault root too, on every lookup, and every read route and the engine resolve the persona's sandbox through it. A typo in `persona.yaml` (`Note` for `Notes`) therefore added an empty `Note` folder to the person's vault on a read-only request, and a wrong `VAULT_PATHS` created the folder it named. Nothing needs the folder to exist beforehand: `create_note` and `create_folder` already make the missing folders on the way when something is written.

**Decision (the user's).** A typo is an error the person sees, not a new folder. (1) Resolving a persona's allowed folders creates nothing, neither its folders nor the vault root. A folder that is not there stays in the persona's list: the persona sees nothing in it, exactly as before (it used to be created empty and then seen empty), and it is not widened to the whole vault, which would be a larger grant than the persona file asked for. A note written to it creates the folder at that moment, as any note written into a missing folder does. (2) `sympose doctor` reports, for each persona, a `vault_folders` entry that is in none of the configured vaults, naming the persona, the entry and the vaults: "the persona 'grace' lists the folder 'Note', which is not in any of your vaults". It has no fix, because the file is the person's writing and either the entry or the vault is wrong. It checks every configured vault, not only the active one, since a folder can belong to the other vault the persona is used with.

**Consequences.** Looking at the vault, in the web app or the terminal, never changes it. A persona whose folder does not exist shows an empty tree and finds nothing, and the doctor says why. A person who relied on the folder appearing by itself creates it in their notes app, or writes the first note through Sympose.

**Alternatives rejected.** Creating the folder on the persona's first write only, in `get_allowed_dirs`: the write path already does it. Dropping a missing folder from the list, which falls back to the whole vault when it was the only entry: it widens what the persona can see because of a typo. Warning at start-up as well: the doctor is the place for a check that reads persona files, and a persona pointed at nothing is not lost the way a dropped persona is.
