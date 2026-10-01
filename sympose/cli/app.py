"""The Textual app shell: a persistent, always-live `Input` docked at the
bottom with a scrolling transcript above it — the one thing legacy's
blocking `rich.prompt.Prompt` loop couldn't do (see `docs/VISION.md`,
lines 46-50). Chat replies now come from the real engine
(`sympose/engine/`, docs/decisions/006); model/persona pickers use real
data (`options.py`). Event handling and the
actual command/streaming behavior live in `dispatch.py`/`runtime.py`/
`turns.py`/`picker.py`, split out to hold the 200-LOC-per-file cap."""

from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Input, OptionList, Static

from sympose import engine, persona_files
from sympose.cli import dispatch, memory_command, picker, settings_list, share, state, stop
from sympose.cli import transcript as transcript_mod
from sympose.cli.background_status import BackgroundStatus
from sympose.cli.composer import DEFAULT_PLACEHOLDER, ComposerInput
from sympose.cli.meter import ContextMeter
from sympose.cli.options import list_personas
from sympose.cli.stop import StopButton
from sympose.engine import memory_refresh
from sympose.profile import resolve_default_persona


class SymposeCLI(App):
    """Run with `python -m sympose.cli`."""

    @property
    def session_id(self) -> str | None:
        """The current conversation's session id: what its generation resolved to, `None` before the
        first reply and after a persona switch (which starts a new generation)."""
        return self.session_by_generation.get(self.session_generation)

    CSS = """
    Screen {
        background: $surface;
    }
    #banner {
        border: round $primary;
        height: auto;
        padding: 0 1;
        margin: 0 1 1 1;
    }
    #transcript {
        height: 1fr;
        margin: 0 1;
    }
    .turn-gap {
        margin-top: 1;
    }
    .system-line {
        color: $text-muted;
    }
    SelectionPanel {
        margin: 0 1;
    }
    #composer {
        border: round $primary;
        margin: 0 1 0 1;
    }
    #composer:focus {
        border: round $accent;
    }
    """

    BINDINGS = [Binding("escape", "close_panel", "Close picker", show=False)]

    def compose(self) -> ComposeResult:
        yield Static("", id="banner")
        yield VerticalScroll(id="transcript")
        yield BackgroundStatus("")
        yield ComposerInput(placeholder=DEFAULT_PLACEHOLDER, id="composer")
        yield StopButton(stop.LABEL)
        yield ContextMeter("")

    def on_mount(self) -> None:
        personas = list_personas()
        if not personas:
            # list_profiles() now deliberately returns [] once a
            # profiles/ dir exists but has no valid <handle>/persona.yaml in it
            # (docs/decisions/009) -- `personas[0]` below would be a
            # cryptic IndexError instead of an actionable message.
            raise RuntimeError(
                "No personas configured -- check SYMPOSE_PROFILES_DIR points "
                "at a directory containing at least one <handle>/persona.yaml."
            )
        # The configured default persona (factory default: Samantha, see
        # `CLAUDE.md`'s project rules) — picked explicitly rather than
        # whichever profile happens to sort first alphabetically.
        default_handle = resolve_default_persona()
        self.persona = next(
            (p for p in personas if p.handle == default_handle), personas[0]
        )
        state.init(self)
        picker.update_banner(self)
        engine.refresh_recaps(self.persona.handle)  # background, while the user types (ADR 023)
        engine.refresh_embeddings(self.persona.handle)  # background, only if the knob is on (ADR 027)
        if memory_refresh.auto_refresh_enabled():  # off by default: /memory refresh always stays manual (ADR 041)
            engine.refresh_memory(self.persona.handle)
        engine.refresh_status_phrases(self.persona.handle)  # background, a no-op once it has its own set
        transcript_mod.mount_line(self, "Talking to the real engine now — local by default.", "system")
        transcript_mod.mount_line(self, "Type a message, or / for commands.", "system")
        share.announce(self)  # a cloud model in use is said out loud (ADR 031)
        memory_command.announce_pending(self)  # a proposal an earlier refresh staged is said too (ADR 041)
        missed = persona_files.missed_notice()  # a persona folder the roster cannot find (ADR 029)
        if missed:
            transcript_mod.mount_line(self, Text(missed, style=Style(color=self.theme_color("error", "red"), bold=True)), "system")
        self.composer.focus()

    async def action_quit(self) -> None:
        # Always the normal exit, even with a model call still running: Textual's teardown is what
        # gives the terminal back (#65), and the call cannot be waited for or cancelled, so
        # `__main__.main` ends the process with `os._exit` once `run()` returns.
        self.exit()

    @property
    def transcript(self) -> VerticalScroll:
        return self.query_one("#transcript", VerticalScroll)

    @property
    def composer(self) -> Input:
        return self.query_one("#composer", Input)

    def theme_color(self, name: str, fallback: str) -> str:
        return self.get_css_variables().get(name, fallback)

    def action_close_panel(self) -> None:
        if self.pending_setting is not None:  # a number is being asked for (docs/decisions/036)
            settings_list.cancel(self)
            return
        if self.panel is not None:
            picker.close_panel(self)
            self.composer.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "composer":
            dispatch.on_input_changed(self, event.value)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "composer":
            await dispatch.on_input_submitted(self, event.value)

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        await dispatch.on_option_selected(self, event)


if __name__ == "__main__":
    SymposeCLI().run()
