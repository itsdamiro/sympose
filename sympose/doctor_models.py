"""The models section of `sympose doctor` (docs/decisions/029, "which models are in use"): which chat and
embedding models are in use and what a cloud one may receive (docs/decisions/031). A report, not a check:
the one finding, a cloud embedding model whose notes are not approved, is `embedding_finding`.

Imported by `doctor` only when it runs: `sharing` brings in litellm, which takes a few seconds."""

from sympose import profile, settings_store
from sympose.engine import embeddings, sharing
from sympose.engine.model import DEFAULT_LOCAL_MODEL

_LOCAL = "local, nothing leaves this computer"


def _vault_part() -> str:
    approved = [name for name in sharing.CATEGORIES if name in sharing.approved()]
    held = [name for name in sharing.CATEGORIES if name not in approved]
    return f"from your vault it may receive: {', '.join(approved) or 'nothing'}" + (
        f"; held back: {', '.join(held)}" if held else ""
    )


def _chat(model: str) -> str:
    if sharing.is_local(model):
        return _LOCAL
    return f"cloud, it receives your messages and this conversation; {_vault_part()}"


def _embedding(model: str) -> str:
    if sharing.is_local(model):
        return _LOCAL
    said = "cloud, it would receive every passage of your notes and every message"
    return said if sharing.embeds_notes(model) else f"{said}, but notes are not approved, so notes are searched by keyword"


def embedding_finding() -> str | None:
    """What is wrong when the embedding model is a cloud one that may not receive the notes, else `None`."""
    model = embeddings.model()
    if sharing.embeds_notes(model):
        return None
    return (
        f"the embedding model {model!r} is a cloud model and notes are not approved for cloud models, so notes "
        "are searched by keyword and search by meaning is off (approve with /share in the chat, "
        "or add \"notes\" to cloud_share in the settings file)"
    )


def report() -> list[str]:
    chat = settings_store.text("chat_model", DEFAULT_LOCAL_MODEL)
    lines = ["Models and what leaves this computer:", f"- chat model: {chat}: {_chat(chat)}"]
    for persona in profile.list_profiles():
        own = persona.get("model")
        if isinstance(own, str) and own.strip():
            lines.append(f"- persona {persona['handle']}: {own.strip()}: {_chat(own.strip())}")
    embedding = embeddings.model()
    lines.append(f"- embedding model: {embedding}: {_embedding(embedding)}")
    return lines
