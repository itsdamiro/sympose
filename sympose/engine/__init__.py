"""The chat engine (docs/decisions/006, docs/decisions/007) — `run_turn` is
the one entrypoint every channel (CLI today; Slack/web later) calls."""

from sympose.engine.context_estimate import estimate as estimate_context
from sympose.engine.memory_refresh import refresh_in_background as refresh_memory
from sympose.engine.model import EngineModelError
from sympose.engine.recap_refresh import refresh_in_background as refresh_recaps
from sympose.engine.semantic_refresh import refresh_in_background as refresh_embeddings
from sympose.engine.status_phrases import generate_in_background as refresh_status_phrases
from sympose.engine.turn import PersonaNotFoundError, TurnResult, run_turn

__all__ = [
    "run_turn", "TurnResult", "EngineModelError", "PersonaNotFoundError", "refresh_recaps", "refresh_embeddings",
    "refresh_memory", "refresh_status_phrases", "estimate_context",
]
