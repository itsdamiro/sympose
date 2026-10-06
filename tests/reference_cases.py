"""The reference-library eval: questions a user might ask about Sympose itself,
with what must reach the model, and ordinary chat that must not attach any of
the library. Written before the library's notes, so the notes are not shaped to
fit the questions. Deterministic, no model.

The library (sympose/reference/) is searched by the same retriever as a
vault (docs/decisions/014); this only measures it against its own notes. The
questions are worded the way a person asks, not the way a note is titled."""

import os
from dataclasses import dataclass
from typing import Any

from grounding_cases import CASES

from sympose.engine.grounding import retrieve
from sympose.engine.grounding_index import build_index
from sympose.vault_snapshot import get_vault_snapshot

REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "sympose", "reference")


@dataclass(frozen=True)
class RefCase:
    id: str
    message: str
    # Every substring must appear in the text the model would receive.
    find: tuple[str, ...] = ()
    # The top hit must be this note (file name), when set.
    first: str | None = None
    # Nothing at all should be grounded from the library.
    none: bool = False
    known_gap: str | None = None


REF_CASES: list[RefCase] = [
    # What it is, who made it, where it came from
    RefCase("what-is-it", "what is Sympose?", find=("Obsidian",), first="What is Sympose.md"),
    RefCase(
        "why-cheap",
        "how does Sympose keep the cost of talking to my notes down?",
        find=("model",),
        first="What is Sympose.md",
    ),
    RefCase("author", "who made Sympose?", find=("damiro",), first="What is Sympose.md"),
    RefCase(
        "when-started",
        "when was Sympose started?",
        find=("22 September 2026",),
        first="History and author.md",
    ),
    RefCase(
        "earlier-version",
        "was there an earlier version before this one?",
        find=("24 August 2026",),
        first="History and author.md",
    ),
    # Obsidian
    RefCase(
        "works-with-obsidian",
        "does Sympose work with Obsidian?",
        find=("plain markdown files",),
        first="Obsidian.md",
    ),
    RefCase(
        "obsidian-open",
        "do I have to keep Obsidian running to use it?",
        find=("does not need Obsidian",),
        first="Obsidian.md",
    ),
    RefCase(
        "skipped-folders",
        "does it read my attachments folder?",
        find=("Attachments",),
        first="Obsidian.md",
    ),
    # Setting up
    RefCase(
        "start-chatting",
        "how do I start chatting with it in the terminal?",
        find=("sympose cli",),
        first="Getting started.md",
    ),
    RefCase(
        "needs-ollama",
        "it says it can't connect to the model, what do I do?",
        find=("Ollama",),
        first="Troubleshooting.md",
    ),
    RefCase(
        "first-reply-slow",
        "why is the first reply so slow?",
        find=("loads",),
        first="Troubleshooting.md",
    ),
    RefCase(
        "add-second-vault",
        "how do I add a second vault?",
        find=("VAULT_PATHS",),
        first="Add or switch vaults.md",
    ),
    RefCase(
        "switch-vault-in-terminal",
        "can I change vault from the terminal?",
        find=("web app",),
        first="Add or switch vaults.md",
    ),
    # Personas
    RefCase(
        "create-persona",
        "how do I create a new persona?",
        find=("persona.yaml",),
        first="Personas.md",
    ),
    RefCase(
        "create-agent",
        "im thinking or creating a new agent. a coder in nature.",
        find=("persona.yaml",),
        first="Personas.md",
    ),
    RefCase(
        "create-profile-with-a-typo",
        "can you help me create a ne profile for sympose or not? your drifting..",
        find=("persona.yaml",),
    ),
    RefCase(
        "make-agent-in-the-web-app",
        "can I make a new agent from the web app?",
        find=("the web app cannot either",),
        first="Personas.md",
    ),
    # the old name still finds its way (docs/decisions/028)
    RefCase(
        "make-agent-in-the-dashboard",
        "can I make a new agent from the dashboard?",
        find=("the web app cannot either",),
        first="Personas.md",
    ),
    RefCase(
        "soul-file",
        "what goes in a soul file?",
        find=("voice",),
        first="Personas.md",
    ),
    RefCase(
        "default-persona",
        "how do I make a different persona the default?",
        find=("/default",),
        first="Personas.md",
        known_gap="The right passage is returned, but a model note ranks first: 'different' "
        "and 'default' both appear under 'How do I switch to a different model?'. A ranking "
        "weakness of shared ordinary words, not a missing answer.",
    ),
    RefCase(
        "persona-folders",
        "can I stop a persona from seeing some of my folders?",
        find=("vault_folders",),
        first="Personas.md",
    ),
    # Models
    RefCase(
        "default-model",
        "which model does it use out of the box?",
        find=("gemma2:9b",),
        first="Choosing a model.md",
    ),
    RefCase(
        "change-model",
        "how do I switch to a different model?",
        find=("/model",),
        first="Choosing a model.md",
    ),
    # Commands and settings
    RefCase(
        "list-commands",
        "what commands can I type in the chat?",
        find=("/quit",),
        first="Chat commands.md",
    ),
    RefCase(
        "hide-a-folder",
        "how do I hide a folder in the web app?",
        find=("Hide from view",),
        first="The web app.md",
    ),
    RefCase(
        "unhide-a-note",
        "how do I show a hidden note again?",
        find=("Unhide",),
        first="The web app.md",
    ),
    RefCase(
        "settings-in-chat",
        "how do I change a setting without editing the file?",
        find=("/settings",),
        # No `first`: the Settings passage and one of "Add or switch vaults" ("editing `.env`") score alike
        # and trade places whenever a note is added to the library; the model is given both.
    ),
    RefCase(
        "slash-settings",
        "what does /settings do?",
        find=("/settings",),
        first="Chat commands.md",
        known_gap="A question that names only a slash command finds the wrong Settings passages by keywords "
        "(the same for /grounded); the wording that names what it does, above, finds the right one.",
    ),
    RefCase(
        "settings-file",
        "where are my settings stored?",
        find=("settings.json",),
        first="Settings.md",
    ),
    RefCase(
        "turn-off-followups",
        "how do I turn off the extra search she does for follow-up questions?",
        find=("grounding_followups",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "context-window-setting",
        "what does the context_window setting do?",
        find=("context_window",),
        first="Settings.md",
    ),
    # How it uses notes, the header, the meter
    RefCase(
        "header-from",
        "what does the from part in the reply header mean?",
        find=("grounded",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "hide-notes-line",
        "how do I hide which notes she used?",
        find=("/grounding",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "meter",
        "what does the percentage under the chat box mean?",
        find=("older turns",),
        first="The context meter.md",
    ),
    RefCase(
        "older-turns-out",
        "what does 'older turns out of context' mean?",
        find=("older turns",),
        first="The context meter.md",
    ),
    # Privacy, storage
    RefCase(
        "where-conversations",
        "where are my conversations stored?",
        find=("sessions",),
        first="Privacy and data.md",
    ),
    RefCase(
        "leaves-computer",
        "does anything I write leave my computer?",
        find=("Ollama",),
        first="Privacy and data.md",
    ),
    RefCase(
        "cloud-receives",
        "what does a cloud model receive from my vault?",
        find=("/share",),  # the privacy answer and the setting's own section both say it
    ),
    RefCase(
        "share-command",
        "how do I let a cloud model use my notes?",
        find=("/share",),
    ),
    # The web app (once called the dashboard, docs/decisions/028)
    RefCase(
        "nebula",
        "what is the Knowledge Nebula?",
        find=("graph",),
        first="The web app.md",
    ),
    RefCase(
        "rename-links",
        "what happens to the links in my other notes when I rename a note in the web app?",
        find=("Markdown links",),
        first="The web app.md",
    ),
    RefCase(
        "what-is-the-dashboard",
        "what is the dashboard?",
        find=("web app",),
        first="The web app.md",
        known_gap="The old name is a single word, and the library's strict search needs two of the message's "
        "words in a note's own text (ADR 019), so 'dashboard' alone finds nothing. A two-word question with "
        "it does (below), and searching by meaning (ADR 027) covers this one too.",
    ),
    RefCase(
        "start-the-web-app",
        "how do I start the web app?",
        find=("sympose web",),
        first="Getting started.md",  # its heading is the question itself (it was The web app.md before that note grew)
    ),
    RefCase(
        "start-the-dashboard",
        "how do I start the dashboard?",
        find=("sympose web",),
        first="The web app.md",
    ),
    RefCase(
        "deleted-note",
        "how do I get back a note I deleted?",
        find=("trash",),
        first="The web app.md",
    ),
    # What it cannot do: an honest "not yet" is part of the library
    RefCase(
        "slack",
        "does Sympose work in Slack?",
        find=("Slack",),
        first="Not built yet.md",
    ),
    RefCase(
        "session-logs-review",
        "arent you supposed to review our session logs?",
        find=("never reads them",),
        first="Not built yet.md",
    ),
    RefCase(
        "history-and-logs-pressed",
        "theres history and session logs for you to know what we talked last time. arent you aware of that?",
        find=("never reads them",),
        first="Not built yet.md",
    ),
    RefCase(
        "remembers-last-conversation",
        "does Samantha remember our last conversation?",
        find=("recaps",),
        first="Not built yet.md",
    ),
    RefCase(
        "where-recaps-live",
        "where are the recaps of my conversations kept?",
        find=("profiles/<handle>/recaps/",),
        first="Privacy and data.md",
    ),
    RefCase(
        "turn-off-recaps",
        "how do I turn off the recaps?",
        find=("session_recaps",),  # the setting's own section and the privacy answer both say it
    ),
    RefCase(
        "new-note-where",
        "where does the note you propose get saved when I accept it?",
        find=("takes the note's title",),
        first="Creating notes.md",
    ),
    RefCase(
        "new-note-folder",
        "can you make the new note in a subfolder I choose?",
        find=("Projects/Sympose",),
        first="Creating notes.md",
    ),
    RefCase(
        "new-note-not-listed",
        "I asked you to create a note but I cannot see it anywhere",
        find=("Drafts group",),
        first="Creating notes.md",
    ),
    RefCase(
        "writes-notes",
        "can Samantha write or edit my notes for me in the chat?",
        find=("Accept",),
        first="Not built yet.md",
    ),
    # Checking the notes (ADR 034)
    RefCase("check-notes", "how do I check my notes for problems?", find=("sympose vault --health",), first="Checking your notes.md"),
    RefCase("empty-notes", "how do I find empty notes in my vault?", find=("sympose vault --health",), first="Checking your notes.md"),
    RefCase("broken-links", "how can I find broken links in my vault?", find=("links to no note",), first="Checking your notes.md"),
    RefCase("clutter-files", "does the health report mention files that are not notes?", find=("clutter",), first="Checking your notes.md"),
    RefCase("folder-definition", "what is a folder definition?", find=("what the folder is for",), first="Checking your notes.md"),
    RefCase("draft-definition", "how do I draft a definition for a folder?", find=("sympose vault --draft",), first="Checking your notes.md"),
    RefCase("draft-cloud", "does drafting a folder definition send my notes to a cloud model?", find=("titles",), first="Checking your notes.md"),
    RefCase("health-fix", "can Sympose fix the problems it finds in my notes?", find=("never in bulk",), first="Not built yet.md"),
    RefCase("reads-properties", "does she read the properties of my notes?", find=("properties",), first="How Samantha uses your notes.md"),
    RefCase("reads-md-only", "does Sympose read my txt files as notes?", find=("not notes",), first="Obsidian.md"),
    # Search by meaning, in plain words
    RefCase(
        "what-is-search-by-meaning",
        "what does searching by meaning mean?",
        find=("lists of numbers",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "install-for-better-search",
        "do I need to install anything to make the search smarter?",
        find=("nomic-embed-text",),
    ),
    RefCase(
        "search-sent-to-cloud",
        "is my vault sent anywhere when she searches my notes by meaning?",
        find=("Ollama",),
    ),
    RefCase(
        "indexing-notice",
        "what does the indexing notice at the right of the chat box mean?",
        find=("cache",),  # the Settings section on the first index and the note on grounding both answer it
    ),
    RefCase(
        "missed-or-unrelated-notes",
        "why does she bring notes that have nothing to do with my question?",
        find=("embedding_min_similarity",),
        first="How Samantha uses your notes.md",
    ),
    RefCase(
        "back-to-keywords",
        "how do I make her search by words only again?",
        find=('"keywords"',),
    ),
    # Ordinary chat must attach nothing from the library
    RefCase("small-talk", "hey, how are you today?", none=True),
    RefCase("rough-day", "hey. rough day, my brain is completely fried", none=True),
    RefCase("thanks", "thanks, that helps!", none=True),
    RefCase("about-a-word-in-both", "which flights did I book for Lisbon?", none=True),
    RefCase("topic-change", "ok let's talk about something else", none=True),
    # Two words of a note's title in ordinary chat are one signal, not two.
    RefCase("title-words-in-chat", "I'm getting started on my taxes", none=True),
    # What a local model cannot do, and the long-chat settings (docs/decisions/040, 055)
    RefCase("local-model-no-tools", "why can't my local model open my notes by itself?", find=("call tools",), first="Choosing a model.md"),
    RefCase("fifth-note-in-folder", "why can't she open the 5th note in my movies folder?", find=("5th note",)),
    RefCase("compact-command", "how do I shorten a long conversation?", find=("/compact",)),
    RefCase("auto-compact-setting", "what does the auto_compact setting do?", find=("condenses a long conversation",), first="Settings.md"),
    RefCase("deleted-conversation-bin", "how do I get back a conversation I deleted?", find=("Conversations part",), first="The web app.md"),
    RefCase("switch-while-replying", "can I open another conversation while she is still writing a reply?", find=("lands in the conversation it was sent from",)),
    RefCase("parallel-replies-setting", "what does the parallel_replies setting do?", find=("different conversations of one persona",), first="Settings.md"),
    RefCase("sessions-bin-command", "how do I restore a deleted conversation in the terminal?", find=("/sessions restore",)),
    RefCase("past-chats-setting", "can she read my earlier conversations word for word? what is past_chats?", find=("`past_chats` setting",)),
    RefCase("recap-count-setting", "how many earlier conversations does she remember? what is recap_count?", find=("`recap_count` setting",)),
    RefCase("no-answer-from-model", "it says there was no answer from the model, what do I do?", find=("model_timeout",)),
    RefCase("connections-by-meaning-setting", "what does the connections_by_meaning setting do?", find=("`connections_by_meaning` setting",), first="Settings.md"),
    RefCase("connections-relevance-setting", "how do I get fewer notes in the related notes list? connections_relevance", find=("`connections_relevance` setting",), first="Settings.md"),
    RefCase("history-tokens-setting", "can I limit how much of the earlier conversation is sent each time? history_tokens", find=("`history_tokens` setting",)),
]

# Every message the vault eval already uses must attach nothing from the
# library, except the one that really is about Sympose.
_ABOUT_SYMPOSE = {"a-request-matching-only-ordinary-words-grounds-nothing"}
VAULT_QUESTIONS_MUST_NOT_ATTACH: list[RefCase] = [
    RefCase(f"vault-{c.id}", c.message, none=True)
    for c in CASES
    if c.id not in _ABOUT_SYMPOSE
]


def ground_reference(message: str) -> list[dict[str, Any]]:
    root = os.path.abspath(REFERENCE_DIR)
    return retrieve(build_index(get_vault_snapshot(root, [root])), message, strict=True)


def run_ref_case(case: RefCase) -> str | None:
    """`None` when the case passes, else a one-line reason."""
    hits = ground_reference(case.message)
    names = [os.path.basename(h["rel_path"]) for h in hits]
    if case.none:
        return None if not hits else f"expected nothing, got {names}"
    blob = "\n".join(h["text"] for h in hits)
    for needle in case.find:
        if needle not in blob:
            return f"missing {needle!r} in what the model would see ({names})"
    if case.first and (not names or names[0] != case.first):
        return f"top hit was {names[:1]}, wanted {case.first!r}"
    return None
