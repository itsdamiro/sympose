"""The model call of a turn that has a video for the model to watch (docs/decisions/089): Google's own request, and the
video's captions when Google will not take it. The preview is not a promise, so a refusal of the request (not a key, a
quota or a stop) is not the end of the turn: the same messages go to the model the ordinary way with the captions where
the video would have been, and the rest of the turn (its tool rounds) stays on that route."""

from dataclasses import replace
from typing import Any, Callable

from sympose.engine import captions, gemini_direct, model as model_mod
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.prompt_text import READING_PAGES, READING_SEARCH, WATCHING


# Said under the reply when Google's reader could not open a page: the model may answer from what it already knew and
# write as though it had read the page (measured on a page the reader refuses), so the reply says that it did not.
PAGE_NOT_OPENED = "Google could not open {pages}, so none of this comes from {that}."


def _swap(messages: list[dict[str, Any]], words: str) -> list[dict[str, Any]]:
    """`messages` with the line saying a video is attached replaced by the captions, and the lines about pages and
    search taken out: the ordinary call has neither."""
    def swapped(text: str) -> str:
        return text.replace(WATCHING, words).replace(f"{READING_PAGES}\n\n", "").replace(f"{READING_SEARCH}\n\n", "")

    return [{**m, "content": swapped(m["content"])} if m.get("role") == "user" and isinstance(m.get("content"), str) else m for m in messages]


def for_links(links: tuple[str, ...], server_tools: tuple[str, ...] = ()) -> Callable[..., ModelReply]:
    """A function with `model.call_model`'s arguments that watches `links` and carries Google's `server_tools`, or reads
    the videos' captions when Google will not take them."""
    fell_back: list[str] = []  # the captions text, once the watch has been refused
    unopened: list[str] = []  # the pages Google's reader could not open, over all of the turn's calls

    def call(messages: list[dict[str, Any]], **kwargs: Any) -> ModelReply:
        if not fell_back:
            try:
                reply = gemini_direct.call(messages, links=links, server_tools=server_tools, unopened=unopened, **kwargs)
                if unopened and reply.text and not reply.tool_calls:  # the answer, not a round of tool calls
                    pages = list(dict.fromkeys(unopened))
                    that = "that page" if len(pages) == 1 else "those pages"
                    reply = replace(reply, text=f"{reply.text}\n\n{PAGE_NOT_OPENED.format(pages=', '.join(pages), that=that)}")
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
