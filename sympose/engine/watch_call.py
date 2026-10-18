"""The model call of a turn that has a video for the model to watch (docs/decisions/089): Google's own request, and the
video's captions when Google will not take it. The preview is not a promise, so a refusal of the request (not a key, a
quota or a stop) is not the end of the turn: the same messages go to the model the ordinary way with the captions where
the video would have been, and the rest of the turn (its tool rounds) stays on that route."""

from typing import Any, Callable

from sympose.engine import captions, gemini_direct, model as model_mod
from sympose.engine.model import EngineModelError, ModelReply
from sympose.engine.prompt_text import WATCHING


def _swap(messages: list[dict[str, Any]], words: str) -> list[dict[str, Any]]:
    """`messages` with the line saying a video is attached replaced by the captions."""
    return [
        {**m, "content": m["content"].replace(WATCHING, words)} if m.get("role") == "user" and isinstance(m.get("content"), str) else m
        for m in messages
    ]


def for_links(links: tuple[str, ...]) -> Callable[..., ModelReply]:
    """A function with `model.call_model`'s arguments that watches `links`, or reads their captions when it cannot."""
    fell_back: list[str] = []  # the captions text, once the watch has been refused

    def call(messages: list[dict[str, Any]], **kwargs: Any) -> ModelReply:
        if not fell_back:
            try:
                return gemini_direct.call(messages, links=links, **kwargs)
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
