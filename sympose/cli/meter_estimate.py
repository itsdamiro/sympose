"""The meter's figure right after a model switch (docs/decisions/018, "Update"): instead of going
blank it shows an estimate for the new model, counted off the interface thread and dropped if a
reset (another switch, a persona switch) has made it stale meanwhile."""

import asyncio
import concurrent.futures
import logging

from sympose import engine
from sympose.cli import meter

log = logging.getLogger(__name__)

# Its own pool, not the one chat turns use (`turns.py`): those threads can all be waiting on a model,
# and the meter's figure must not queue behind them. Two workers so a slow count for one switch does
# not hold up the next switch's.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sympose-meter")


def start(app, model_id: str) -> None:
    """Call right after `meter.clear`, so the epoch captured here is the one the estimate belongs to.
    Does nothing before the conversation's first reply (nothing to count)."""
    session_id = app.session_id
    if session_id is None:
        return
    app.run_worker(_show(app, app.persona.handle, session_id, model_id, meter.epoch(app)))


async def _show(app, handle: str, session_id: str, model_id: str, since: int) -> None:
    try:
        figures = await asyncio.get_running_loop().run_in_executor(
            _EXECUTOR, engine.estimate_context, handle, session_id, model_id
        )
    except Exception as e:  # an estimate is a courtesy: never worth an error in the chat
        log.warning("Could not estimate the context for %s: %s", model_id, e)
        return
    if figures is not None and not app._exit:
        meter.show(app, figures[0], figures[1], since, estimated=True)
