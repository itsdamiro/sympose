"""Adding, reading and switching a persona's skills (docs/decisions/077, the amendment of 2026-10-14): a folder the user
points at is checked, only its `SKILL.md` is copied, and it arrives off; nothing is carried until it is switched on."""

import pytest
import yaml
from helpers import write_persona

from sympose import persona_skills, profile
from sympose.engine import skills

SKILL = "---\nname: {name}\ndescription: Plans a trip itinerary. Use when the user wants to plan a trip.\n---\n1. Ask the dates.\n"


@pytest.fixture
def home(tmp_path, monkeypatch):
    base = tmp_path / "profiles"
    folder = write_persona(base, "ada", "name: Ada\nvault_folders: '*'\nskills: ['poem-writing']\n")
    bundled = tmp_path / "bundled" / "poem-writing"
    bundled.mkdir(parents=True)
    (bundled / "SKILL.md").write_text(SKILL.format(name="poem-writing"), encoding="utf-8")
    monkeypatch.setattr(skills, "BUNDLED_DIR", str(tmp_path / "bundled"))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(base))
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return folder


def skill_folder(tmp_path, name="trip-planning", text=None, extra=()):
    folder = tmp_path / "elsewhere" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(SKILL.format(name=name) if text is None else text, encoding="utf-8")
    for other in extra:
        (folder / other).write_text("x", encoding="utf-8")
    return folder


def test_the_list_holds_every_skill_the_persona_could_carry_with_its_state(home, tmp_path):
    persona_skills.add("ada", str(skill_folder(tmp_path)))

    rows = {r["name"]: r for r in persona_skills.listing("ada")}

    assert list(rows) == ["poem-writing", "trip-planning"]
    assert rows["poem-writing"]["enabled"] is True and rows["poem-writing"]["own"] is False
    assert rows["trip-planning"]["enabled"] is False and rows["trip-planning"]["own"] is True
    assert rows["trip-planning"]["length"] == len("1. Ask the dates.") and rows["trip-planning"]["cap"] == skills.DEFAULT_CAP


def test_an_added_skill_is_copied_into_the_personas_folder_and_arrives_off(home, tmp_path):
    result = persona_skills.add("ada", str(skill_folder(tmp_path)))

    assert result["skill"]["name"] == "trip-planning" and result["skill"]["enabled"] is False
    assert (home / "skills" / "trip-planning" / "SKILL.md").read_text(encoding="utf-8") == SKILL.format(name="trip-planning")
    assert skills.carried(profile.get_profile("ada")) and [s.name for s in skills.carried(profile.get_profile("ada"))] == ["poem-writing"]


def test_only_skill_md_is_copied_and_the_rest_is_counted(home, tmp_path):
    result = persona_skills.add("ada", str(skill_folder(tmp_path, extra=("run.sh", "notes.txt"))))

    assert result["left_out"] == 2
    assert [p.name for p in (home / "skills" / "trip-planning").iterdir()] == ["SKILL.md"]


def test_a_trailing_slash_and_a_home_relative_path_are_understood(home, tmp_path, monkeypatch):
    folder = skill_folder(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert persona_skills.add("ada", str(folder) + "/")["skill"]["name"] == "trip-planning"
    (home / "skills" / "trip-planning" / "SKILL.md").unlink()
    (home / "skills" / "trip-planning").rmdir()
    assert persona_skills.add("ada", "~/elsewhere/trip-planning")["skill"]["name"] == "trip-planning"


@pytest.mark.parametrize(
    "path, reason",
    [
        ("", "full path"),
        ("   ", "full path"),
        ("relative/folder", "full path"),
        ("{tmp}/nowhere", "no folder"),
        ("{tmp}/empty", "no SKILL.md"),
    ],
)
def test_a_path_that_is_not_a_skill_folder_is_refused_with_the_reason(home, tmp_path, path, reason):
    (tmp_path / "empty").mkdir()

    with pytest.raises(persona_skills.SkillRefused, match=reason):
        persona_skills.add("ada", path.format(tmp=tmp_path))
    assert not (home / "skills").exists()


def test_a_skill_that_breaks_a_rule_is_refused_with_that_rule(home, tmp_path):
    bad = skill_folder(tmp_path, "mismatch", text=SKILL.format(name="other"))

    with pytest.raises(persona_skills.SkillRefused, match="must be the folder's name, mismatch"):
        persona_skills.add("ada", str(bad))
    assert not (home / "skills").exists()


def test_a_file_of_exactly_the_size_limit_is_added_and_one_byte_more_is_not(home, tmp_path):
    head = SKILL.format(name="edge")
    fits = skill_folder(tmp_path, "edge", text=head + "x" * (skills.MAX_FILE - len(head)))
    over = skill_folder(tmp_path / "over", "edge", text=head + "x" * (skills.MAX_FILE - len(head) + 1))

    with pytest.raises(persona_skills.SkillRefused, match="more than Sympose reads"):
        persona_skills.add("ada", str(over))
    assert persona_skills.add("ada", str(fits))["skill"]["name"] == "edge"


def test_a_file_not_text_is_refused(home, tmp_path):
    binary = tmp_path / "elsewhere" / "bin"
    binary.mkdir(parents=True)
    (binary / "SKILL.md").write_bytes(b"\xff\xfe\x00\x80")

    with pytest.raises(persona_skills.SkillRefused, match="as text"):
        persona_skills.add("ada", str(binary))


def test_a_name_the_persona_already_has_is_refused_whether_bundled_or_her_own(home, tmp_path):
    persona_skills.add("ada", str(skill_folder(tmp_path)))

    with pytest.raises(persona_skills.SkillRefused, match="already has a skill called trip-planning"):
        persona_skills.add("ada", str(skill_folder(tmp_path / "again")))
    with pytest.raises(persona_skills.SkillRefused, match="already has a skill called poem-writing"):
        persona_skills.add("ada", str(skill_folder(tmp_path / "bundled-name", "poem-writing")))


def test_an_unknown_persona_is_refused(home, tmp_path):
    with pytest.raises(persona_skills.SkillRefused, match="no persona called nobody"):
        persona_skills.add("nobody", str(skill_folder(tmp_path)))
    with pytest.raises(persona_skills.SkillRefused, match="no persona called nobody"):
        persona_skills.listing("nobody")


def test_a_name_left_in_her_list_by_a_folder_deleted_by_hand_does_not_switch_the_new_one_on(home, tmp_path):
    persona_skills.add("ada", str(skill_folder(tmp_path)))
    persona_skills.set_enabled("ada", "trip-planning", True)
    (home / "skills" / "trip-planning" / "SKILL.md").unlink()
    (home / "skills" / "trip-planning").rmdir()

    row = persona_skills.add("ada", str(skill_folder(tmp_path / "again")))["skill"]

    assert row["enabled"] is False
    assert "trip-planning" not in profile.get_profile("ada")["skills"]
    assert "poem-writing" in profile.get_profile("ada")["skills"]


def test_switching_on_puts_the_skill_in_the_local_list_and_the_persona_carries_it(home, tmp_path):
    persona_skills.add("ada", str(skill_folder(tmp_path)))

    row = persona_skills.set_enabled("ada", "trip-planning", True)

    assert row["enabled"] is True
    assert yaml.safe_load((home / "persona.local.yaml").read_text(encoding="utf-8")) == {"skills_on": ["trip-planning"]}
    assert sorted(s.name for s in skills.carried(profile.get_profile("ada"))) == ["poem-writing", "trip-planning"]
    assert "trip-planning" not in (home / "persona.yaml").read_text(encoding="utf-8")  # the shipped file is untouched


def test_switching_off_takes_it_out_and_switching_on_twice_does_not_repeat_it(home, tmp_path):
    persona_skills.add("ada", str(skill_folder(tmp_path)))
    persona_skills.set_enabled("ada", "trip-planning", True)
    persona_skills.set_enabled("ada", "trip-planning", True)
    assert profile.get_profile("ada")["skills"] == ["poem-writing", "trip-planning"]

    assert persona_skills.set_enabled("ada", "poem-writing", False)["enabled"] is False
    assert profile.get_profile("ada")["skills"] == ["trip-planning"]


def test_a_skill_that_is_not_there_cannot_be_switched(home):
    with pytest.raises(persona_skills.SkillRefused, match="no skill called ghost"):
        persona_skills.set_enabled("ada", "ghost", True)
    assert not (home / "persona.local.yaml").exists()


def test_reading_gives_the_file_exactly_as_stored_for_an_own_and_a_bundled_skill(home, tmp_path):
    persona_skills.add("ada", str(skill_folder(tmp_path)))

    assert persona_skills.read("ada", "trip-planning")["text"] == SKILL.format(name="trip-planning")
    assert persona_skills.read("ada", "poem-writing")["text"] == SKILL.format(name="poem-writing")
    with pytest.raises(persona_skills.SkillRefused, match="no skill called ghost"):
        persona_skills.read("ada", "ghost")


def test_two_switches_at_once_both_keep_their_change(home, tmp_path, monkeypatch):
    import threading
    import time

    for name in ("one-skill", "two-skill"):
        persona_skills.add("ada", str(skill_folder(tmp_path / name, name)))
    real = persona_skills.persona_model.set_skills

    def slow(handle, names):  # the write lags, so a second switch reads her list before the first has landed
        time.sleep(0.1)
        return real(handle, names)

    monkeypatch.setattr(persona_skills.persona_model, "set_skills", slow)
    threads = [threading.Thread(target=persona_skills.set_enabled, args=("ada", n, True)) for n in ("one-skill", "two-skill")]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert sorted(profile.get_profile("ada")["skills"]) == ["one-skill", "poem-writing", "two-skill"]


def test_a_skills_value_that_is_not_a_list_of_names_names_none_as_the_engine_reads_it(home, tmp_path):
    (home / "persona.yaml").write_text("name: Ada\nvault_folders: '*'\nskills: poem-writing\n", encoding="utf-8")

    rows = {r["name"]: r["enabled"] for r in persona_skills.listing("ada")}

    assert rows == {"poem-writing": False}  # not the substring match of "poem-writing" in "poem-writing"
    assert skills.carried(profile.get_profile("ada")) == []
    assert persona_skills.set_enabled("ada", "poem-writing", True)["enabled"] is True


def test_hidden_files_in_the_folder_are_not_counted_as_left_out(home, tmp_path):
    result = persona_skills.add("ada", str(skill_folder(tmp_path, extra=(".DS_Store", "notes.txt"))))

    assert result["left_out"] == 1
