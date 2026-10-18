"""The model call of a turn that has a video for the model to watch (docs/decisions/089): Google's own request, and the
video's captions when Google will not take it. The preview is not a promise, so a refusal of the request (not a key, a
quota or a stop) is not the end of the turn: the same messages go to the model the ordinary way with the captions where
the video would have been, and the rest of the turn (its tool rounds) stays on that route."""

from dataclasses import replace
from typing import Any, Callable
from urllib.parse import urlsplit

from sympose.engine import captions, gemini_direct, memory_tools, model as model_mod
from sympose.engine.lookup_result import Result
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.prompt_text import READING_PAGES, READING_SEARCH, WATCHING


# Said under the reply when Google's reader could not open a page: the model may answer from what it already knew and
# write as though it had read the page (measured on a page the reader refuses), so the reply says that it did not.
PAGE_NOT_OPENED = "Google could not open {pages}, so none of this comes from {that}."
# The same, for a page the reader was never asked for: measured, a model asked to summarise a well-known page often
# answers from memory and Google reports no read at all, neither an opening nor a failure.
PAGE_NOT_READ = "Google did not read {pages}, so none of this comes from {that}."
# What `remember` answers on a turn in which Google read a page or searched (the model reads this, not the user).
WEB_NOT_REMEMBERED = (
    "Not saved. This turn read a page or searched the web, and nothing in such a turn is written to memory. "
    "Say so; the user can ask again in a message that needs no web."
)


def _swap(messages: list[dict[str, Any]], words: str) -> list[dict[str, Any]]:
    """`messages` with the line saying a video is attached replaced by the captions, and the lines about pages and
    search taken out: the ordinary call has neither."""
    def swapped(text: str) -> str:
        return text.replace(WATCHING, words).replace(f"{READING_PAGES}\n\n", "").replace(f"{READING_SEARCH}\n\n", "")

    return [{**m, "content": swapped(m["content"])} if m.get("role") == "user" and isinstance(m.get("content"), str) else m for m in messages]


def _key(address: str) -> str:
    """An address as Google may hand it back: same page when only the scheme, `www.`, a closing slash, the query or the fragment differ."""
    parts = urlsplit(address)
    return f"{parts.netloc.lower().removeprefix('www.')}{parts.path.rstrip('/')}"


def _not_read(asked: tuple[str, ...], opened: list[str], unopened: list[str]) -> list[str]:
    """The `asked` pages that Google reported neither opened nor unopened. An opened address that matches no asked page
    stands for one that was redirected, so it clears one of them."""
    reported = {_key(a) for a in (*opened, *unopened)}
    missing = [a for a in asked if _key(a) not in reported]
    asked_keys = {_key(a) for a in asked}
    spare = [o for o in opened if _key(o) not in asked_keys]
    return missing[len(spare):]


def _said(text: str, unopened: list[str], not_read: list[str]) -> str:
    for template, pages in ((PAGE_NOT_OPENED, unopened), (PAGE_NOT_READ, not_read)):
        if pages := list(dict.fromkeys(pages)):
            text += "\n\n" + template.format(pages=", ".join(pages), that="that page" if len(pages) == 1 else "those pages")
    return text


def without_memory_after_the_web(run_tool: Callable[..., Any], opened: list[str], searched: list[str]) -> Callable[..., Any]:
    """`run_tool` that refuses `remember` once Google has opened a page or searched in this turn: what came from outside
    must not be able to make a write to the persona's memory, and the lists are those `for_links` fills as the turn goes."""
    def run(persona: dict[str, Any], model: str, name: str, raw_arguments: Any) -> Any:
        if name == memory_tools.REMEMBER and (opened or searched):
            return Result(WEB_NOT_REMEMBERED, lookup={"tool": name, "saved": False})
        return run_tool(persona, model, name, raw_arguments)

    return run


def for_links(
    links: tuple[str, ...], server_tools: tuple[str, ...] = (), asked: tuple[str, ...] = (),
    opened: list[str] | None = None, searched: list[str] | None = None,
) -> Callable[..., ModelReply]:
    """A function with `model.call_model`'s arguments that watches `links` and carries Google's `server_tools`, or reads
    the videos' captions when Google will not take them. `asked` are the pages the user's message links to: the reply says
    so when Google did not read one. `opened` and `searched` are lists the caller may keep, to know what the turn read."""
    fell_back: list[str] = []  # the captions text, once the watch has been refused
    unopened: list[str] = []  # the pages Google's reader could not open, over all of the turn's calls
    opened = [] if opened is None else opened  # the pages it opened
    searched = [] if searched is None else searched  # the searches it ran

    def call(messages: list[dict[str, Any]], **kwargs: Any) -> ModelReply:
        if not fell_back:
            try:
                reply = gemini_direct.call(messages, links=links, server_tools=server_tools, unopened=unopened, opened=opened, searched=searched, **kwargs)
                if reply.text and not reply.tool_calls:  # the answer, not a round of tool calls
                    reply = replace(reply, text=_said(reply.text, unopened, _not_read(asked, opened, unopened)))
                return reply
            except gemini_direct.WatchUnavailable as refused:
                got, missing = captions.fetch(links, captions.MAX_TOKENS)
                words = captions.render(got, missing)
                if not got:
                    raise EngineModelError(
                        f"Gemini would not take the video, and its captions could not be got ({'; '.join(m.reason for m in missing)})."
                    ) from refused
                fell_back.append(words or "")
        return model_mod.call_model(_swap(messages, fell_back[0]), **kwargs)

    return call
