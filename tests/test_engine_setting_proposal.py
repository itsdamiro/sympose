"""Tests for sympose.engine.setting_proposal and the setting kind of confirmations (docs/decisions/080): what she may name, that a
call files a card and changes nothing, that accepting saves through the owning module (and a refusal leaves the setting as it
was), that a second proposal for the same setting replaces the waiting one, and what she is told. The model is a fake."""

import json

import pytest
from helpers import write_persona

from sympose import persona_model, settings_store
from sympose.engine import confirmations as c, followup, persona_proposal, setting_proposal, setting_targets, sharing, tool_support, turn
from sympose.engine.model import ModelReply
from sympose.engine.model_tools import ToolCall

LOCAL = "ollama_chat/gemma2:9b"
CLOUD = "gemini/gemini-flash-latest"
SAM = {"handle": "samantha", "vault_folders": "*"}


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\nsympose_reference: true\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(turn.budget, "_native_max", lambda model: None)
    monkeypatch.setattr(tool_support.litellm, "supports_function_calling", lambda model: model == CLOUD)


def call(setting, value, session="s1"):
    return setting_proposal.run("samantha", session, SAM, "propose_setting", json.dumps({"setting": setting, "value": value}))


def only_request(session="s1"):
    (request,) = c.for_session("samantha", session)
    return request


def test_the_tool_names_every_setting_she_may_change():
    text = json.dumps(setting_proposal.tool())

    assert all(name in text for name in ("history_tokens", "model", "cloud_share:notes", "cloud_share:memory", "model_timeout"))
    assert "chat_model" not in text and "active_vault" not in text


def test_a_call_files_a_card_and_changes_nothing():
    result = call("history_tokens", 3000)

    assert result.lookup["saved"] is True and "nothing changes until they accept" in result.text
    assert only_request()["draft"] == {"setting": "history_tokens", "value": 3000}
    assert settings_store.get("history_tokens") is None


@pytest.mark.parametrize("setting, value, says", [
    ("chat_model", "gemini/x", "no setting called"),
    ("memory_remember", "yes", "true or false"),
    ("vault_lookup", "sometimes", "takes one of"),
    ("history_tokens", "lots", "is not a whole number"),
    ("cloud_share:notes", "yes", "true or false"),
    ("cloud_share:secrets", True, "no setting called"),
    ("model", "nonsense/model", "must be one of"),
])
def test_a_call_that_fails_a_check_is_told_why_and_files_nothing(setting, value, says):
    result = call(setting, value)

    assert says in result.text and result.lookup["saved"] is False
    assert c.for_session("samantha", "s1") == []


@pytest.mark.parametrize("raw", ["not json", "{}", json.dumps({"setting": 3, "value": 1}), json.dumps({"setting": "model_timeout"})])
def test_arguments_that_cannot_be_read_are_said_so(raw):
    result = setting_proposal.run("samantha", "s1", SAM, "propose_setting", raw)

    assert "could not be read" in result.text and not result.lookup["saved"]


def test_another_tools_name_is_not_ours():
    assert setting_proposal.run("samantha", "s1", SAM, "propose_persona", "{}") is None


def test_accepting_saves_through_the_owning_module():
    call("history_tokens", 3000)
    request = only_request()

    done = c.resolve("samantha", request["id"], True, None, ())

    assert done["state"] == c.ACCEPTED and done["draft"]["was"]
    assert settings_store.get("history_tokens") == 3000


@pytest.mark.parametrize("setting, value, says", [("memory_remember", "yes", "true or false"), ("chat_model", "x", "not a setting any more")])
def test_accepting_checks_the_stored_request_again_whatever_filed_it(setting, value, says):
    request = c.propose_setting("samantha", "s1", setting, value)

    with pytest.raises(c.Refused, match=says):
        c.resolve("samantha", request["id"], True, None, ())

    assert c.read("samantha", request["id"])["state"] == c.WAITING and settings_store.get("memory_remember") is None


def test_declining_changes_nothing():
    call("history_tokens", 3000)

    done = c.resolve("samantha", only_request()["id"], False, None, ())

    assert done["state"] == c.DECLINED and settings_store.get("history_tokens") is None


def test_a_number_the_owner_refuses_is_refused_with_its_reason_and_the_card_keeps_waiting():
    call("history_tokens", 10)  # below the module's minimum: only trying knows
    request = only_request()

    with pytest.raises(c.Refused, match="not valid"):
        c.resolve("samantha", request["id"], True, None, ())

    assert c.read("samantha", request["id"])["state"] == c.WAITING and settings_store.get("history_tokens") is None


def test_a_toggle_and_a_choice_are_saved():
    call("grounding_followups", "off")
    call("memory_remember", True)
    for request in c.for_session("samantha", "s1"):
        c.resolve("samantha", request["id"], True, None, ())

    assert settings_store.get(followup.SETTING) == "off" and settings_store.get("memory_remember") is True


def test_a_cloud_share_category_is_switched_on_and_off_one_at_a_time():
    call("cloud_share:notes", True)
    c.resolve("samantha", only_request()["id"], True, None, ())

    assert sharing.NOTES in sharing.approved()

    call("cloud_share:notes", False, session="s2")
    c.resolve("samantha", only_request("s2")["id"], True, None, ())

    assert sharing.NOTES not in sharing.approved()


def test_the_persona_model_is_saved_for_the_persona_that_asked():
    call("model", CLOUD)

    c.resolve("samantha", only_request()["id"], True, None, ())

    assert persona_model._read(persona_model.persona_dir("samantha") + "/persona.local.yaml") == {"model": CLOUD}


PRO = "gemini/gemini-pro-latest"


@pytest.mark.parametrize("said, id", [("Gemini Pro", PRO), ("gemini-pro", PRO), ("GEMINI PRO", PRO)])
def test_a_model_named_in_words_is_filed_as_the_one_id_it_fits(said, id):
    result = call("model", said)

    assert result.lookup["saved"] is True
    assert only_request()["draft"]["value"] == id


def test_a_model_name_that_fits_several_ids_is_refused_with_just_those():
    result = call("model", "gemini")

    assert result.lookup["saved"] is False
    assert "gemini-flash-latest" in result.text and "gemini-pro-latest" in result.text and "gpt-4o-mini" not in result.text


def test_a_second_proposal_replaces_the_waiting_one_for_the_same_setting_only():
    call("history_tokens", 3000)
    call("model_timeout", 300)
    call("history_tokens", 4000)

    states = {(r["draft"]["setting"], r["draft"]["value"]): r["state"] for r in c.for_session("samantha", "s1")}

    assert states == {("history_tokens", 3000): c.REPLACED, ("model_timeout", 300): c.WAITING, ("history_tokens", 4000): c.WAITING}


def test_a_persona_request_is_not_replaced_by_a_setting_one():
    from sympose import persona_create

    draft = persona_create.Draft("Ada", "A tutor", "You are Ada.", "graduation", "#3366cc", "#99bbee", (), "manual")
    persona = c.propose_persona("samantha", "s1", draft)

    call("history_tokens", 3000)

    assert c.read("samantha", persona["id"])["state"] == c.WAITING


def test_she_is_told_what_the_user_decided():
    call("history_tokens", 3000)
    call("cloud_share:notes", True)
    first, second = c.for_session("samantha", "s1")
    c.resolve("samantha", first["id"], True, None, ())
    c.resolve("samantha", second["id"], False, None, ())

    said = c.lines(c.outcomes("samantha", "s1"))

    assert said[0].startswith("You proposed changing ") and "the user accepted it and it is changed" in said[0]
    assert "the user declined it, so nothing changed" in said[1] and "notes" in said[1]


def test_every_real_tool_name_is_one_a_soul_may_not_mention():
    assert "propose_setting" in persona_proposal.tool_names()


def test_the_card_warns_where_the_consequence_is_not_in_the_change():
    cloud = setting_targets.find("model")
    share = setting_targets.find("cloud_share:notes")

    assert "cloud model" in setting_targets.consequence(cloud, CLOUD) and setting_targets.consequence(cloud, LOCAL) is None
    assert "may then receive" in setting_targets.consequence(share, True) and setting_targets.consequence(share, False) is None


def model_that(monkeypatch, *replies):
    seen, queue = [], list(replies)

    def call_model(messages, model=None, **kwargs):
        seen.append({"messages": [dict(m) for m in messages], "model": model, **kwargs})
        return queue.pop(0)

    monkeypatch.setattr(turn.model_mod, "call_model", call_model)
    return seen


def test_a_model_with_tools_is_given_the_tool_and_a_call_makes_a_card(monkeypatch):
    tool_call = ToolCall("c1", "propose_setting", json.dumps({"setting": "history_tokens", "value": 3000}))
    seen = model_that(monkeypatch, ModelReply("", None, tool_calls=(tool_call,)), ModelReply("Proposed.", 5))

    result = turn.run_turn("samantha", "replies are slow", model=CLOUD, edits=True)

    assert "propose_setting" in [t["function"]["name"] for t in seen[0]["tools"]]
    assert [r["draft"]["setting"] for r in c.for_session("samantha", result.session_id)] == ["history_tokens"]
    assert settings_store.get("history_tokens") is None


@pytest.mark.parametrize("model, kwargs", [(LOCAL, {"edits": True}), (CLOUD, {})])
def test_she_is_not_given_it_without_a_tool_model_or_without_the_web_app(monkeypatch, model, kwargs):
    seen = model_that(monkeypatch, ModelReply("Hello.", 5))

    turn.run_turn("samantha", "hello", model=model, **kwargs)

    assert "propose_setting" not in [t["function"]["name"] for t in seen[0].get("tools", [])]
