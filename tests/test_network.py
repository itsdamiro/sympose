"""Model and embedding calls go over IPv4 (engine/network.py): a dead IPv6 route cost a reply two minutes."""

import litellm
import pytest

from sympose.engine import embeddings, model, network  # noqa: F401  (importing them is what sets the flag)


@pytest.fixture(autouse=True)
def restore():
    before = litellm.force_ipv4
    yield
    litellm.force_ipv4 = before


def test_importing_the_model_and_embedding_modules_leaves_calls_on_ipv4(monkeypatch):
    monkeypatch.delenv(network.ALLOW_IPV6, raising=False)
    litellm.force_ipv4 = False

    network.prefer_ipv4()

    assert litellm.force_ipv4 is True


@pytest.mark.parametrize("value", ["1", "true", "YES", " on "])
def test_a_network_with_only_ipv6_can_allow_it(monkeypatch, value):
    monkeypatch.setenv(network.ALLOW_IPV6, value)
    network.prefer_ipv4()
    assert litellm.force_ipv4 is False


@pytest.mark.parametrize("value", ["", "0", "no", "false"])
def test_anything_else_keeps_ipv4(monkeypatch, value):
    monkeypatch.setenv(network.ALLOW_IPV6, value)
    network.prefer_ipv4()
    assert litellm.force_ipv4 is True


def test_the_modules_that_call_models_set_it_when_they_are_imported():
    import importlib

    for module in (model, embeddings):
        litellm.force_ipv4 = False
        importlib.reload(module)
        assert litellm.force_ipv4 is True, module.__name__
