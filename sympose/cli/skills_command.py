"""`/skills` (docs/decisions/077, the amendment of 2026-10-20): the persona's skills in the terminal, as Settings shows them
in the web app. `/skills` opens a list where choosing a row switches that skill on or off; `/skills add <path>` copies a
skill's folder in (off) and shows what it says; `/skills read <name>` shows a skill's text; `/skills remove <name>` deletes
one of the user's own, after a yes. Every rule is `persona_skills`'; this only asks and shows."""

from rich.text import Text

from sympose import persona_skills
from sympose.cli import attach_command, picker, transcript as transcript_mod
from sympose.cli.selection import SelectionOption

PICKER_KIND = "skills"
CONFIRM_KIND = "skills_confirm"
KEEP = "keep"
_REMOVE = "remove:"
_SHOWN_DESCRIPTION = 70
USAGE = (
    "Usage: /skills lists the skills, and choosing one switches it on or off. /skills add <path to a skill's folder>, "
    "read <name> and remove <name> (yours only)."
)


def _say(app, line) -> None:
    transcript_mod.mount_line(app, line, "system")


def _short(description: str) -> str:
    return description if len(description) <= _SHOWN_DESCRIPTION else description[: _SHOWN_DESCRIPTION - 1].rstrip() + "…"


def options(handle: str) -> list[SelectionOption]:
    """One row per skill the persona could carry, with whether it is on now; choosing a row flips it."""
    return [
        SelectionOption(f"{row['name']} — {'on' if row['enabled'] else 'off'}{', yours' if row['own'] else ''}: {_short(row['description'])}", row["name"])
        for row in persona_skills.listing(handle)
    ]


async def open_picker(app, highlight: str | None = None) -> None:
    rows = options(app.persona.handle)
    names = [row.value for row in rows]
    row = names.index(highlight) if highlight in names else -1
    await picker.open_picker(app, PICKER_KIND, f"Skills of @{app.persona.handle} (Esc when done)", rows, highlight=row)


def toggle(app, name: str) -> None:
    """Flip the skill `name` and say what it is now."""
    try:
        was = {r["name"]: r["enabled"] for r in persona_skills.listing(app.persona.handle)}
        if name not in was:
            raise persona_skills.SkillRefused(f"There is no skill called {name}.")
        row = persona_skills.set_enabled(app.persona.handle, name, not was[name])
    except persona_skills.SkillRefused as e:
        _say(app, str(e))
        return
    _say(app, f"{name} is now {'on' if row['enabled'] else 'off'}.")


def _show(app, name: str) -> bool:
    """Print the skill's facts and its text exactly as stored; `False` (after saying why) when it can't be read."""
    try:
        skill = persona_skills.read(app.persona.handle, name)
    except persona_skills.SkillRefused as e:
        _say(app, str(e))
        return False
    cut = f"; only the first {skill['cap']} are sent with a message" if skill["length"] > skill["cap"] else ""
    owner = "Yours: it is sent only to a model on your computer, never to a cloud model." if skill["own"] else "Ships with Sympose."
    _say(app, f"{name} — {'on' if skill['enabled'] else 'off'}. {skill['length']} characters{cut}. {owner}")
    _say(app, Text(skill["text"]))
    return True


def _add(app, args: str) -> None:
    if not args.strip():
        _say(app, USAGE)
        return
    try:
        added = persona_skills.add(app.persona.handle, " ".join(attach_command.path_words(args)))
    except persona_skills.SkillRefused as e:
        _say(app, str(e))
        return
    name = added["skill"]["name"]
    _say(app, f"Added {name}. It is off: read it below, then turn it on with /skills.")
    if added["left_out"]:
        _say(app, "Only SKILL.md was copied. Nothing else in that folder is used.")
    _show(app, name)


async def _remove(app, name: str) -> None:
    rows = {r["name"]: r for r in persona_skills.listing(app.persona.handle)}
    if name not in rows:
        _say(app, f"There is no skill called {name}.")
    elif not rows[name]["own"]:
        _say(app, f"{name} ships with Sympose, so it can't be removed. Turn it off with /skills instead.")
    else:
        await picker.open_picker(
            app, CONFIRM_KIND, f"Remove {name} for good?", [SelectionOption("Remove it", _REMOVE + name, danger=True), SelectionOption("Keep it", KEEP)]
        )


def apply_removal(app, value: str | None) -> None:
    """A row of the remove confirm picker was chosen."""
    if value is None or not value.startswith(_REMOVE):
        return
    name = value[len(_REMOVE):]
    try:
        persona_skills.remove(app.persona.handle, name)
    except persona_skills.SkillRefused as e:
        _say(app, str(e))
        return
    _say(app, f"Removed {name}.")


async def run(app, args: str) -> None:
    verb, _, rest = args.strip().partition(" ")
    verb = verb.lower()
    if not verb:
        await open_picker(app)
    elif verb == "add":
        _add(app, rest)
    elif verb == "read" and rest.strip():
        _show(app, rest.strip())
    elif verb == "remove" and rest.strip():
        await _remove(app, rest.strip())
    else:
        _say(app, USAGE)
