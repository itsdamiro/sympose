"""Tests must not depend on whether an embedding model is running on the machine (docs/decisions/027).
The shipped default of `grounding_search` is `auto`, which would call one, so every test starts with the
default set to `keywords` and with a settings file of its own (the maintainer's real `settings.json` is
never read). A test of meaning-based search sets its mode itself; a test of the shipped default is marked
`@pytest.mark.shipped_defaults`."""

import pytest

from sympose.engine import embeddings


def pytest_configure(config):
    config.addinivalue_line("markers", "shipped_defaults: run with the settings defaults the product ships")


@pytest.fixture(autouse=True)
def _keyword_search_by_default(request, tmp_path_factory, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path_factory.mktemp("settings") / "settings.json"))
    if request.node.get_closest_marker("shipped_defaults") is None:
        monkeypatch.setattr(embeddings, "DEFAULT_MODE", embeddings.KEYWORDS)


@pytest.fixture(autouse=True)
def _profiles_of_their_own(tmp_path_factory, monkeypatch):
    """Saving a persona's model writes its `persona.yaml` (docs/decisions/044), so a test never reaches the
    real `./profiles/`: it starts with an empty folder of its own. A test that needs personas sets
    `SYMPOSE_PROFILES_DIR` itself, which takes over from this."""
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(tmp_path_factory.mktemp("profiles")))


@pytest.fixture(autouse=True)
def _no_ollama_capability_lookup(monkeypatch):
    """Which local models take tools (docs/decisions/040) is asked of a running Ollama; a test must not
    depend on which models this machine has pulled, so the question is refused unless a test answers it."""
    from sympose.engine import tool_support

    def refused(*args, **kwargs):
        raise OSError("no Ollama in tests")

    monkeypatch.setattr(tool_support, "urlopen", refused)
    for state in ("_OLLAMA_TOOLS", "_OLLAMA_SILENT_UNTIL", "_STRIKES"):
        monkeypatch.setattr(tool_support, state, {})
    monkeypatch.setattr(tool_support, "_UNABLE", set())
