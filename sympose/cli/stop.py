"""Stopping a reply from the terminal chat (docs/decisions/054): the Stop line under the input, shown only
while a reply is being written or revealed, and what pressing it does. A reply still being written is thrown
away (the engine drops the turn; `turns._run_turn` says so and gives the message back); a reply already
written, whose words are still appearing, is shown whole at once. Messages that waited still go out."""

from textual.widgets import Static

from sympose import engine

LABEL = "■ Stop"
STOPPING = "■ Stopping…"


class StopButton(Static):
    """Hidden until `refresh_for` shows it; a click stops. Under the composer, above the context meter."""

    DEFAULT_CSS = """
    StopButton {
        display: none;
        height: 1;
        margin: 0 2 0 2;
        color: $text-muted;
    }
    StopButton.active {
        display: block;
    }
    StopButton:hover {
        color: $error;
    }
    """

    def on_click(self) -> None:
        stop(self.app)


def busy(app) -> bool:
    """A reply is being written, or one is still being revealed."""
    return bool(app.turn_runs) or bool(app.active_reply_timers)


def refresh_for(app) -> None:
    """Show the Stop line while something can be stopped, and hide it again once nothing can."""
    button = app.query_one(StopButton)
    button.set_class(busy(app), "active")
    if not app.stopping:
        button.update(LABEL)


def stop(app) -> None:
    """Stop what is running: every reply being written (the engine answers whether it could still be
    dropped; one already complete is left to arrive) and every reveal in progress."""
    accepted = [handle for handle in sorted(app.generating) if engine.cancel_turn(handle)]
    if accepted:
        app.stopping = True
        app.query_one(StopButton).update(STOPPING)
    for skip in list(app.reply_skips):
        skip()
