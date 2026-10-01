"""Shared test helpers — one directory per persona (docs/decisions/011)."""

from pathlib import Path


def write_persona(profiles_dir: Path, handle: str, body: str) -> Path:
    """Creates `<profiles_dir>/<handle>/persona.yaml` with `body` and
    returns the persona directory."""
    directory = profiles_dir / handle
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "persona.yaml").write_text(body)
    return directory


def rename_note(profile: dict, old_name: str, new_name: str, **kwargs) -> str:
    """`vault_write_rename.rename_note_to_path`'s result message, for a test that does not care where
    the note went."""
    from sympose import vault_write_rename

    return vault_write_rename.rename_note_to_path(profile, old_name, new_name, **kwargs)[0]
