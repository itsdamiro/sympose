"""`/compact` (docs/decisions/055): condense the earlier part of this conversation into notes now, with
the model in use. A real model call (`compaction.compact_now`), so it runs off the interface thread, on a
pool of its own: not the one chat turns use (`turns.py`), so it never queues behind a reply, and not the
loop's default pool, which `/quit` waits on."""

import concurrent.futures

from sympose.cli import meter, meter_estimate, off_thread, transcript as transcript_mod
from sympose.cli.options import active_model
from sympose.engine import compaction, session, session_compaction

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sympose-compact")

_SAID = {
    compaction.NOTHING: f"Nothing to condense yet: the newest {compaction.KEEP_TURNS} turns always stay as they are.",
    compaction.TOO_SMALL: "Nothing to gain yet: notes would be no shorter than the turns they replace.",
    compaction.FAILED: "The notes could not be written: the model could not be reached or gave nothing (see the log).",
    compaction.BUSY: "Already condensing this conversation: try again in a moment.",
}


async def run(app) -> None:
    session_id = app.session_id
    if session_id is None:
        transcript_mod.mount_line(app, "Nothing to condense: this conversation has not started yet.", "system")
        return
    handle, model = app.persona.handle, active_model(app.persona, app.model_override).id
    transcript_mod.mount_line(app, "Condensing the earlier turns...", "system")
    outcome = await off_thread.run(_EXECUTOR, compaction.compact_now, handle, session_id, model)
    if off_thread.quitting(app):
        return
    if outcome.status == compaction.DONE:
        transcript_mod.mount_line(
            app, f"Condensed the first {outcome.covered} turns into notes ({outcome.before} to {outcome.after} tokens):", "system"
        )
        transcript_mod.mount_line(app, outcome.text, "system")
        meter.clear(app)  # the figure was of the longer conversation
        meter_estimate.start(app, model)
    else:
        transcript_mod.mount_line(app, _SAID[outcome.status], "system")
        notes = session_compaction.notes(session.load_session(handle, session_id))
        if outcome.status == compaction.NOTHING and notes:
            transcript_mod.mount_line(app, f"The notes now: {notes}", "system")
    app.transcript.scroll_end(animate=False)
