"""Tests for sympose.engine.confirmations (docs/decisions/078): a request is stored and survives a reload, one card is
waiting at a time, accepting checks everything again and creates the persona, and the outcome is told to her once."""

import os

import pytest
from helpers import write_persona

from sympose import persona_create
from sympose.engine import confirmations as c

TOOLS = ("propose_note", "propose_persona")
SOUL = "You are Ada, a warm tutor.\n\nHow you talk:\n- Gently.\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    for folder in ("Work", "Recipes", "Journal"):
        (vault / folder).mkdir(parents=True)
    profiles = tmp_path / "profiles"
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    monkeypatch.setenv("VAULT_PATHS", str(vault))
    return profiles


def draft(name="Ada", folders=("Recipes", "Work")):
    return persona_create.Draft(name, "A tutor", SOUL, "graduation", "#3366cc", "#99bbee", tuple(folders), "manual")


def test_a_request_is_stored_waiting_and_read_back(world):
    request = c.propose_persona("samantha", "s1", draft())

    again = c.read("samantha", request["id"])

    assert again == request and again["state"] == c.WAITING and again["handle"] == "ada" and again["draft"]["folders"] == ["Recipes", "Work"]
    assert c.for_session("samantha", "s1") == [request] and c.for_session("samantha", "other") == []


def test_nothing_exists_while_the_request_waits(world):
    c.propose_persona("samantha", "s1", draft())

    assert not os.path.exists(world / "ada")


def test_a_new_request_replaces_the_one_that_was_waiting_in_that_conversation_only(world):
    first = c.propose_persona("samantha", "s1", draft("Ada"))
    elsewhere = c.propose_persona("samantha", "s2", draft("Bea"))
    second = c.propose_persona("samantha", "s1", draft("Ada", ("Work",)))

    states = {r["id"]: r["state"] for r in c.for_session("samantha", "s1") + c.for_session("samantha", "s2")}

    assert states == {first["id"]: c.REPLACED, second["id"]: c.WAITING, elsewhere["id"]: c.WAITING}


def test_a_replaced_request_cannot_be_answered(world):
    first = c.propose_persona("samantha", "s1", draft())
    c.propose_persona("samantha", "s1", draft())

    with pytest.raises(c.Refused, match="already been answered"):
        c.resolve("samantha", first["id"], True, None, TOOLS)
    assert not os.path.exists(world / "ada")


def test_accepting_creates_the_persona_with_the_pills_as_the_user_left_them(world):
    request = c.propose_persona("samantha", "s1", draft())

    done = c.resolve("samantha", request["id"], True, ["Journal"], TOOLS)

    assert done["state"] == c.ACCEPTED and done["draft"]["folders"] == ["Journal"]
    assert "Journal" in (world / "ada" / "persona.yaml").read_text() and "Work" not in (world / "ada" / "persona.yaml").read_text()
    assert c.read("samantha", request["id"])["state"] == c.ACCEPTED


def test_accepting_with_the_edit_mode_the_user_chose_makes_the_persona_with_it(world):
    request = c.propose_persona("samantha", "s1", draft())

    done = c.resolve("samantha", request["id"], True, None, TOOLS, edit_mode="accept")

    assert done["draft"]["edit_mode"] == "accept" and "edit_mode: accept" in (world / "ada" / "persona.yaml").read_text()


def test_an_edit_mode_that_is_not_one_is_refused_and_the_request_keeps_waiting(world):
    request = c.propose_persona("samantha", "s1", draft())

    with pytest.raises(c.Refused, match="edit_mode must be one of"):
        c.resolve("samantha", request["id"], True, None, TOOLS, edit_mode="wild")
    assert c.read("samantha", request["id"])["state"] == c.WAITING and not os.path.exists(world / "ada")


def test_accepting_without_an_edit_mode_given_keeps_hers(world):
    request = c.propose_persona("samantha", "s1", draft())

    c.resolve("samantha", request["id"], True, None, TOOLS)

    assert "edit_mode: manual" in (world / "ada" / "persona.yaml").read_text()


def test_accepting_without_pills_given_keeps_her_folders(world):
    request = c.propose_persona("samantha", "s1", draft())

    c.resolve("samantha", request["id"], True, None, TOOLS)

    assert "Recipes" in (world / "ada" / "persona.yaml").read_text()


def test_declining_makes_nothing(world):
    request = c.propose_persona("samantha", "s1", draft())

    assert c.resolve("samantha", request["id"], False, None, TOOLS)["state"] == c.DECLINED
    assert not os.path.exists(world / "ada")


def test_a_request_is_answered_once(world):
    request = c.propose_persona("samantha", "s1", draft())
    c.resolve("samantha", request["id"], True, None, TOOLS)

    with pytest.raises(c.Refused, match="already been answered"):
        c.resolve("samantha", request["id"], True, None, TOOLS)
    with pytest.raises(c.Refused, match="already been answered"):
        c.resolve("samantha", request["id"], False, None, TOOLS)


def test_a_proposal_with_no_folders_is_accepted_with_the_ones_the_user_turned_on(world):
    request = c.propose_persona("samantha", "s1", draft(folders=()))

    with pytest.raises(c.Refused, match="at least one folder"):
        c.resolve("samantha", request["id"], True, None, TOOLS)
    done = c.resolve("samantha", request["id"], True, ["Journal"], TOOLS)

    assert done["state"] == c.ACCEPTED and "Journal" in (world / "ada" / "persona.yaml").read_text()


def test_no_pill_on_is_refused_and_the_request_keeps_waiting(world):
    request = c.propose_persona("samantha", "s1", draft())

    with pytest.raises(c.Refused, match="at least one folder"):
        c.resolve("samantha", request["id"], True, [], TOOLS)
    assert c.read("samantha", request["id"])["state"] == c.WAITING and not os.path.exists(world / "ada")


def test_a_folder_she_cannot_read_is_refused_even_from_the_card(world):
    request = c.propose_persona("samantha", "s1", draft())

    with pytest.raises(c.Refused, match="Secrets"):
        c.resolve("samantha", request["id"], True, ["Secrets"], TOOLS)
    assert not os.path.exists(world / "ada")


def test_the_proposal_is_checked_again_when_accepted(world):
    request = c.propose_persona("samantha", "s1", draft())
    path = world / "samantha" / "confirmations" / f"{request['id']}.json"
    path.write_text(path.read_text().replace("graduation", "smiley"))  # a file edited by hand

    with pytest.raises(c.Refused, match="icon"):
        c.resolve("samantha", request["id"], True, None, TOOLS)
    assert not os.path.exists(world / "ada")


def test_a_handle_taken_in_the_meantime_makes_the_request_outdated(world):
    request = c.propose_persona("samantha", "s1", draft())
    write_persona(world, "ada", "name: Ada\n")

    done = c.resolve("samantha", request["id"], True, None, TOOLS)

    assert done["state"] == c.OUTDATED and "already exists" in done["reason"]
    assert (world / "ada" / "persona.yaml").read_text() == "name: Ada\n"


def test_unknown_and_unsafe_ids_are_refused(world):
    for bad in ("nope", "../x", ""):
        with pytest.raises(c.Refused, match="not there"):
            c.resolve("samantha", bad, True, None, TOOLS)


def test_she_is_told_each_decision_once(world):
    accepted = c.propose_persona("samantha", "s1", draft("Ada"))
    c.resolve("samantha", accepted["id"], True, None, TOOLS)
    declined = c.propose_persona("samantha", "s1", draft("Bea"))
    c.resolve("samantha", declined["id"], False, None, TOOLS)
    c.propose_persona("samantha", "s1", draft("Cy"))  # still waiting: not told

    told = c.outcomes("samantha", "s1")

    assert c.lines(told) == [
        "You proposed a persona called Ada: the user accepted it and the persona now exists.",
        "You proposed a persona called Bea: the user declined it, so nothing was made.",
    ]
    c.mark_told("samantha", told)
    assert c.outcomes("samantha", "s1") == []
    assert c.outcomes("samantha", "s2") == []


def test_a_replaced_request_is_not_told(world):
    first = c.propose_persona("samantha", "s1", draft("Ada"))
    c.propose_persona("samantha", "s1", draft("Ada"))

    assert first["id"] not in [r["id"] for r in c.outcomes("samantha", "s1")]
