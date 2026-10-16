"""Reading and saving a folder's settings, the Folder settings dialog's two calls (docs/decisions/087).

`read` is what the dialog starts from: the definition note's own values when the folder has one, the generic template
when it has not. `save` takes everything the dialog holds: it creates the definition note when there is none, and
when there is one it changes only the fields that differ from the note (`folder_settings_text`), through the editor's
own save, so a note that changed meanwhile is refused. Called only from the user's click in the dialog."""

from dataclasses import dataclass, field
from typing import Any

from sympose import folder_definitions as defs
from sympose import folder_definitions_write as write_defs
from sympose import folder_looks, folder_settings_text, generic_template, look, vault_paths
from sympose.folder_looks_write import Changed, Failed, Missing, Refused, rewrite_note
from sympose.vault_snapshot import parse_frontmatter
from sympose.vault_write_resolve import resolve_existing_note
from sympose.vault_write_status import NOTE_DENIED, NOTE_EXISTS

_CREATED = "Created note:"  # what `create_note` starts its answer with when it made the file


@dataclass(frozen=True)
class Settings:
    """What the dialog holds: the user's words and the folder's look (`None` for a look key that is not set)."""

    purpose: str = ""
    template: list[str] = field(default_factory=list)
    icon: str | None = None
    accent: str | None = None
    accent_dark: str | None = None

    @property
    def look(self) -> dict[str, str | None]:
        return {"icon": self.icon, "accent": self.accent, "accent_dark": self.accent_dark}


def look_refusal(chosen: dict[str, str | None]) -> str | None:
    """Why a look cannot be written, or `None`: an icon the app's set does not have, or a colour that is not a
    six-digit hex (the value ends up in the page, and in a note that may travel)."""
    icon = chosen.get("icon")
    if icon is not None and icon not in look.ICON_NAMES:
        return f"`{icon}` is not an icon Sympose has."
    if any(value is not None and not folder_looks.HEX_COLOR.fullmatch(value) for key, value in chosen.items() if key != "icon"):
        return "A colour is six hexadecimal digits after a `#`, like `#be123c`."
    return None


def _reachable(profile: dict[str, Any], folder: str) -> tuple[str, list[str]] | None:
    """The vault and allowed folders of `profile` when `folder` can be given settings now: a top-level folder of the
    user's own content that exists and that the persona may write to. Anything else is answered like a folder that
    is not there, so the answer does not say which exist."""
    scope = vault_paths.resolve_sandbox(profile)
    if scope is None or not defs.can_have_definition(folder) or not write_defs.reachable(scope, folder):
        return None
    return scope


def read(profile: dict[str, Any], folder: str) -> dict[str, Any]:
    """What the dialog for `folder` starts from. `{"editable": False}` when the folder cannot be given settings
    (not one of the user's own top-level folders, not there for this persona, or a definition the persona cannot
    open); otherwise `editable`, `defined`, the `purpose`, the `template` lines, where they came from
    (`template_source`: `note`, or the generic template's `vault` or `settings`) and the look keys the note sets.
    Raises `Refused` when the definition cannot be read as text."""
    scope = _reachable(profile, folder)
    if scope is None:
        return {"editable": False}
    note = defs.definition_path(folder)
    if not write_defs.defined(scope[0], folder):
        lines, source = generic_template.lines_for(scope[0])
        return {"editable": True, "defined": False, "purpose": "", "template": lines, "template_source": source}
    path = resolve_existing_note(profile, note)
    if path is None:
        return {"editable": False}
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, ValueError) as reason:  # ValueError: not valid UTF-8
        raise Refused(f"`{note}` could not be read as text.") from reason
    return {
        "editable": True,
        "defined": True,
        "purpose": defs.read_purpose(text) or "",
        "template": write_defs.property_lines([defs.read_template(text) or ""]),
        "template_source": "note",
        **{key: None for key in folder_looks.KEYS},
        **folder_looks.of_note(parse_frontmatter(text)[0]),
    }


def _edited(text: str, folder: str, settings: Settings) -> str:
    """`text`, a definition note, with each field of `settings` that differs from it changed. A field the note
    already holds is not rewritten, and the limits (`write_defs.purpose_refusal`, `template_refusal`) apply only to
    what changes, so a note the user wrote by hand is not refused for what the dialog left alone."""
    note = defs.definition_path(folder)
    if defs.split_frontmatter(text) is None:  # its purpose and template cannot be told from the properties
        raise Refused(f"`{note}` opens a properties block it does not close, so nothing was changed.")
    meta = parse_frontmatter(text)[0]
    current = folder_looks.of_note(meta)
    # A key whose value was already unusable (not a name, not a hex) reads as none, so clearing it changes nothing.
    changes = {key: value for key, value in settings.look.items() if value != current.get(key)}
    if reason := look_refusal(changes):  # only what changes: a name the set lacks, left alone, is not refused
        raise Refused(reason)
    lines = write_defs.property_lines(settings.template)
    purpose_changed = settings.purpose.strip() != (defs.read_purpose(text) or "")
    template_changed = lines != write_defs.property_lines([defs.read_template(text) or ""])
    if purpose_changed and (reason := write_defs.purpose_refusal(settings.purpose)):
        raise Refused(reason)
    if template_changed and (reason := write_defs.template_refusal(lines)):
        raise Refused(reason)
    if changes:
        text = folder_settings_text.with_look(text, changes)  # `None` only for an unclosed block, refused above
    if purpose_changed:
        text = folder_settings_text.with_purpose(text, settings.purpose)
    if template_changed:
        text = folder_settings_text.with_template(text, lines)
    return text


def save(profile: dict[str, Any], folder: str, settings: Settings) -> bool:
    """Saves `settings` as `folder`'s definition note: created when the folder has none, otherwise changed in
    place. `True` when the note was created. Raises `Refused` with the reason a person can read when the text, the
    look or the folder is not allowed, `Missing` when the folder is not there for this persona, and `Changed` when
    the note was created or changed by someone else while the dialog was open."""
    if not defs.can_have_definition(folder):
        raise Refused(f"`{folder}` is not a folder that can have a definition.")
    scope = _reachable(profile, folder)
    if scope is None:
        raise Missing(f"Folder `{folder}` not found in the vault.")
    note = defs.definition_path(folder)
    if write_defs.defined(scope[0], folder):
        rewrite_note(profile, note, lambda text: _edited(text, folder, settings))
        return False
    if reason := look_refusal(settings.look) or write_defs.refusal(settings.purpose, settings.template, any(settings.look.values())):
        raise Refused(reason)
    lines = write_defs.property_lines(settings.template)
    chosen = [folder_looks.line(key, value) for key, value in settings.look.items() if value]
    made = write_defs.Draft(folder, note, defs.render(folder, lines, settings.purpose, chosen), lines, 0, False)
    result = write_defs.write(profile, made)
    if result == NOTE_EXISTS:
        raise Changed(f"`{folder}` got a description while this was open. Close the settings and open them again.")
    if result == NOTE_DENIED:
        raise Refused("That path is outside the folders this persona can use.")
    if not result.startswith(_CREATED):
        raise Failed(f"`{note}` could not be created. {result.removeprefix('Error: ')}")
    return True
