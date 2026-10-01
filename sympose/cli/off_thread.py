"""Running a blocking engine call off the interface thread, and knowing the app was quit meanwhile.
`turns.py`, `meter_estimate.py` and `memory_command.py` each had their own copy of both."""

import asyncio
import concurrent.futures


def quitting(app) -> bool:
    """`/quit` fired while a call was in flight. `_exit` is a private Textual attribute, not part of
    its public API, but the only signal available; this is the one place that reads it, and a test
    (`tests/test_cli.py`'s quit-while-in-flight ones) catches a Textual upgrade that renames it
    rather than this silently becoming a no-op."""
    return bool(app._exit)


async def run(executor: concurrent.futures.Executor | None, fn, *args):
    """`fn(*args)` on `executor` (the loop's default pool when `None`), awaited."""
    return await asyncio.get_running_loop().run_in_executor(executor, fn, *args)
