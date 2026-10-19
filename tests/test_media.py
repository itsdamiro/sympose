"""Files attached to a message (docs/decisions/089, `media`): which are taken, how many and how large, what is held for
the next few messages and what is not. Nothing here reaches a model."""

import pytest

from sympose import settings_store
from sympose.engine import media, sharing

CLOUD = "gemini/gemini-flash-latest"
OTHER_CLOUD = "anthropic/claude-sonnet-5-5"
LOCAL = "ollama_chat/gemma2:9b"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("SYMPOSE_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(media, "_held", {})


def pdf(name="paper.pdf", size=10):
    return media.make(name, b"%PDF" + b"x" * size)


def test_a_file_is_known_by_the_ending_of_its_name_and_nothing_the_browser_says():
    kinds = {name: media.make(name, b"x").kind for name in ("a.PDF", "b.png", "c.JPEG", "d.mp3", "e.m4a", "f.mp4", "g.mov", "h.heic")}
    assert kinds == {"a.PDF": media.PDF, "b.png": media.IMAGE, "c.JPEG": media.IMAGE, "d.mp3": media.AUDIO, "e.m4a": media.AUDIO, "f.mp4": media.VIDEO, "g.mov": media.VIDEO, "h.heic": media.IMAGE}
    assert media.make("a.pdf", b"x").mime == "application/pdf"


@pytest.mark.parametrize("name", ["notes.txt", "archive.zip", "script.py", "noending", "", "   "])
def test_a_file_google_cannot_read_is_refused_in_words(name):
    with pytest.raises(media.MediaRefused, match="PDFs, images, sounds and videos"):
        media.make(name, b"x")


def test_an_empty_file_is_refused():
    with pytest.raises(media.MediaRefused, match="empty"):
        media.make("a.pdf", b"")


def test_a_name_is_the_last_part_of_a_path_without_control_characters():
    assert media.file_name("/Users/me/Documents/a\x00b.pdf") == "ab.pdf"
    assert media.file_name("C:\\Users\\me\\report.pdf") == "report.pdf"
    assert len(media.file_name("x" * 500 + ".pdf")) == 120


def test_at_most_three_files_and_a_limit_on_their_size_together():
    media.check([pdf(f"{i}.pdf") for i in range(media.MAX_FILES)])
    with pytest.raises(media.MediaRefused, match="At most 3"):
        media.check([pdf(f"{i}.pdf") for i in range(media.MAX_FILES + 1)])
    big = media.File("big.pdf", "application/pdf", media.PDF, b"x" * (media.MAX_BYTES // 2 + 1))
    with pytest.raises(media.MediaRefused, match="too large"):
        media.check([big, big])


def test_a_name_used_twice_is_numbered_so_the_first_file_is_not_ambiguous():
    first, second = media.check([pdf("a.pdf"), pdf("a.pdf")])
    assert (first.name, second.name) == ("a.pdf", "a (2).pdf")


def test_files_go_to_a_model_that_reads_them_when_the_user_has_allowed_media():
    sharing.set_approved(sharing.MEDIA, True)
    found = media.plan(CLOUD, "samantha", "s1", (pdf(),))
    assert found.names == ("paper.pdf",) and found.fresh and not found.withheld and not found.unsupported


def test_files_the_user_has_not_allowed_are_withheld_by_name_and_not_sent():
    found = media.plan(CLOUD, "samantha", "s1", (pdf(),))
    assert found.files == () and found.withheld == ("paper.pdf",)


def test_a_local_model_and_a_cloud_model_that_cannot_read_files_are_told_so_not_asked_for_approval():
    sharing.set_approved(sharing.MEDIA, True)
    for model in (LOCAL, OTHER_CLOUD):
        found = media.plan(model, "samantha", "s1", (pdf(),))
        assert found.files == () and found.unsupported == ("paper.pdf",) and not found.withheld


def test_a_message_with_no_files_and_nothing_held_has_nothing():
    assert media.plan(CLOUD, "samantha", "s1", ()) == media.Plan()


def test_files_are_held_for_the_next_five_messages_then_let_go():
    sharing.set_approved(sharing.MEDIA, True)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf(),)))
    for _ in range(media.CARRY_TURNS):
        carried = media.plan(CLOUD, "samantha", "s1", ())
        assert carried.names == ("paper.pdf",) and not carried.fresh
        media.settle("samantha", "s1", carried)
    assert media.plan(CLOUD, "samantha", "s1", ()) == media.Plan()


def test_held_files_belong_to_one_conversation_of_one_persona():
    sharing.set_approved(sharing.MEDIA, True)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf(),)))
    assert media.plan(CLOUD, "samantha", "s2", ()) == media.Plan() and media.plan(CLOUD, "other", "s1", ()) == media.Plan()


def test_held_files_are_bounded_in_bytes_and_the_oldest_conversation_goes_first():
    sharing.set_approved(sharing.MEDIA, True)
    half = media.File("v.mp4", "video/mp4", media.VIDEO, b"x" * (media.HELD_BYTES // 2 + 1))
    for n in range(3):
        media.settle("samantha", f"s{n}", media.Plan((half,), fresh=True))
    assert sorted(sid for _, sid in media._held) == ["s2"]
    media.settle("samantha", "s3", media.Plan((pdf(),), fresh=True))
    assert sorted(sid for _, sid in media._held) == ["s2", "s3"]


def test_a_new_message_with_files_replaces_the_held_ones():
    sharing.set_approved(sharing.MEDIA, True)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf("old.pdf"),)))
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf("new.pdf"),)))
    assert media.plan(CLOUD, "samantha", "s1", ()).names == ("new.pdf",)


def test_a_carried_file_is_not_sent_once_the_user_takes_the_approval_back_and_is_not_reported():
    sharing.set_approved(sharing.MEDIA, True)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf(),)))
    sharing.set_approved(sharing.MEDIA, False)
    found = media.plan(CLOUD, "samantha", "s1", ())
    assert found.files == () and found.withheld == () and media.note(found) is None


def test_files_that_were_attached_and_not_sent_let_go_of_older_held_ones():
    sharing.set_approved(sharing.MEDIA, True)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf("old.pdf"),)))
    sharing.set_approved(sharing.MEDIA, False)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf("new.pdf"),)))
    sharing.set_approved(sharing.MEDIA, True)
    assert media.plan(CLOUD, "samantha", "s1", ()) == media.Plan()


def test_only_a_few_conversations_are_held_and_the_oldest_goes_first():
    sharing.set_approved(sharing.MEDIA, True)
    for n in range(media.HELD_CONVERSATIONS + 1):
        media.settle("samantha", f"s{n}", media.plan(CLOUD, "samantha", f"s{n}", (pdf(),)))
    assert media.plan(CLOUD, "samantha", "s0", ()) == media.Plan()
    assert media.plan(CLOUD, "samantha", f"s{media.HELD_CONVERSATIONS}", ()).names == ("paper.pdf",)


def test_forget_lets_go_of_a_conversations_files():
    sharing.set_approved(sharing.MEDIA, True)
    media.settle("samantha", "s1", media.plan(CLOUD, "samantha", "s1", (pdf(),)))
    media.forget("samantha", "s1")
    assert media.plan(CLOUD, "samantha", "s1", ()) == media.Plan()


def test_the_prompt_line_names_the_files_and_says_what_happened_to_each_kind():
    sent = media.Plan((pdf(),), fresh=True)
    assert "paper.pdf" in media.note(sent) and "outside content" in media.note(sent)
    assert "cannot read files" in media.note(media.Plan(unsupported=("a.pdf",)))
    assert '"media"' in media.note(media.Plan(withheld=("a.pdf",)))
    assert media.note(media.Plan()) is None


def test_media_is_a_category_the_user_can_approve_and_is_off_until_they_do():
    assert sharing.MEDIA in sharing.CATEGORIES and sharing.MEDIA not in sharing.approved()
    assert sharing.categories_of([], [], media=True) == [sharing.MEDIA]
    assert settings_store.get(sharing.SETTING) is None


def test_the_web_app_lists_the_same_endings_and_limits_as_the_server():
    import re
    from pathlib import Path

    source = (Path(__file__).parent.parent / "ui" / "src" / "lib" / "file-attachments.ts").read_text(encoding="utf-8")
    listed = re.search(r"FILE_EXTENSIONS = \[(.*?)\] as const", source, re.S).group(1)
    assert tuple(re.findall(r'"(\.[a-z0-9]+)"', listed)) == media.EXTENSIONS
    assert int(re.search(r"MAX_FILES = (\d+)", source).group(1)) == media.MAX_FILES
    assert int(re.search(r"MAX_BYTES = (\d+) \* 1024 \* 1024", source).group(1)) * 1024 * 1024 == media.MAX_BYTES


def test_files_named_earlier_in_the_conversation_and_not_attached_now_are_said_and_the_ones_attached_are_not():
    history = [
        {"role": "user", "content": "read [attached: old.pdf] and [attached: paper.pdf]"}, {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "again [attached: old.pdf]"},
    ]
    both = media.note(media.Plan((pdf("paper.pdf"),), fresh=False), history)
    assert "old.pdf" in both.split("\n\n")[-1] and "no longer attached" in both
    assert "paper.pdf" in both.split("\n\n")[0] and "paper.pdf" not in both.split("\n\n")[-1]
    assert media.gone(history, media.Plan((pdf("paper.pdf"), pdf("old.pdf")))) == ()
    assert media.note(media.Plan(), []) is None and media.note(media.Plan(), [{"role": "user", "content": "hi"}]) is None


def test_the_line_about_files_that_are_gone_reads_in_the_singular_and_the_plural():
    one = media.note(media.Plan(), [{"role": "user", "content": "[attached: a.pdf]"}])
    two = media.note(media.Plan(), [{"role": "user", "content": "[attached: a.pdf] [attached: b.pdf]"}])
    assert "It is no longer attached" in one and "read it now" in one
    assert "a.pdf, b.pdf" in two and "They are no longer attached" in two and "read them now" in two


def test_only_the_users_own_messages_name_a_file_not_what_the_persona_wrote():
    history = [{"role": "assistant", "content": "I read [attached: invented.pdf] for you"}, {"role": "user", "content": "thanks"}]
    assert media.gone(history, media.Plan()) == ()
