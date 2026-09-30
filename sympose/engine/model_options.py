"""The models both channels offer to choose from (docs/decisions/007, 044). Ids are the real
litellm-resolvable strings a per-call model passes straight through, with the local Ollama model listed
first, matching the engine's own local-first default. A persona's own `model` or the `chat_model` setting
can name anything litellm resolves; `model_option_for` gives such an id an entry too."""

from dataclasses import dataclass

from sympose.engine.model import DEFAULT_LOCAL_MODEL


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    # Short name for a reply's header: a dedicated field rather than parsing it back out of `label`,
    # which is free-form display text with no guaranteed structure.
    short: str


MODEL_OPTIONS: list[ModelOption] = [
    # `DEFAULT_LOCAL_MODEL`, not a re-typed literal: a stale duplicate would silently diverge from the
    # engine's canonical default.
    ModelOption(id=DEFAULT_LOCAL_MODEL, label="Gemma2:9b — local, default", short="Gemma2:9b"),
    # Real, litellm-resolvable provider-prefixed ids, not placeholders: a bare "claude-sonnet-5" would
    # break every later turn with a confusing error. They work if the provider's key (ANTHROPIC_API_KEY,
    # OPENAI_API_KEY) is set in `.env`; if not, litellm raises its own auth error, which `EngineModelError`
    # shows as a friendly line.
    ModelOption(id="anthropic/claude-sonnet-5", label="Claude Sonnet 5 — cloud", short="Claude Sonnet 5"),
    ModelOption(id="openai/gpt-4o-mini", label="GPT-4o mini — cloud", short="GPT-4o mini"),
    # The `-latest` aliases, not a dated name: Google retires named versions, an alias follows. Needs
    # `GEMINI_API_KEY` in `.env` (docs/decisions/007).
    ModelOption(id="gemini/gemini-flash-latest", label="Gemini Flash — cloud", short="Gemini Flash"),
    ModelOption(id="gemini/gemini-pro-latest", label="Gemini Pro — cloud", short="Gemini Pro"),
    # One `OPENROUTER_API_KEY` for models from other makers; any other OpenRouter model works by name in
    # `chat_model` (docs/decisions/007).
    ModelOption(id="openrouter/anthropic/claude-haiku-4.5", label="Claude Haiku 4.5 — OpenRouter", short="Claude Haiku 4.5"),
    ModelOption(id="openrouter/meta-llama/llama-3.3-70b-instruct", label="Llama 3.3 70B — OpenRouter", short="Llama 3.3 70B"),
    ModelOption(id="openrouter/meta-llama/llama-3.1-8b-instruct", label="Llama 3.1 8B — OpenRouter", short="Llama 3.1 8B"),
    ModelOption(id="openrouter/deepseek/deepseek-v4-flash", label="DeepSeek V4 Flash — OpenRouter", short="DeepSeek V4 Flash"),
]


def model_option_for(model_id: str) -> ModelOption:
    """The entry for `model_id`, or a synthesized one for an id the list doesn't hold (a persona's own
    `model`, or the `chat_model` setting, can name anything litellm resolves)."""
    known = next((m for m in MODEL_OPTIONS if m.id == model_id), None)
    return known or ModelOption(id=model_id, label=model_id, short=model_id.split("/")[-1])
