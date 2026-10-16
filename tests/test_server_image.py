"""Tests for the vault image route (docs/decisions/085): which file a reference finds, what is refused, the headers."""

import pytest
from fastapi.testclient import TestClient
from helpers import write_persona

from sympose import vault_image
from sympose.server import create_app

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


@pytest.fixture
def vault(monkeypatch, tmp_path):
    root = tmp_path / "vault"
    for folder in ("assets", "Projects/x", "Attachments", ".obsidian", "Private", "deep/er", "hidden-by-owner"):
        (root / folder).mkdir(parents=True)
    (root / "Projects/x/note.md").write_text("note", encoding="utf-8")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    write_persona(profiles, "samantha", "name: Samantha\nvault_folders: '*'\n")
    write_persona(profiles, "narrow", "name: Narrow\nvault_folders: ['Projects']\n")
    monkeypatch.setenv("VAULT_PATHS", str(root))
    monkeypatch.setenv("SYMPOSE_PROFILES_DIR", str(profiles))
    return root


@pytest.fixture
def client(vault):
    return TestClient(create_app())


def get(client, path, frm="", persona="samantha", method="get"):
    return getattr(client, method)("/api/vault/image", params={"path": path, "from": frm, "persona": persona})


def test_a_path_from_the_root_is_served_with_its_type(vault, client):
    (vault / "assets/shot.png").write_bytes(PNG)
    r = get(client, "assets/shot.png")
    assert r.status_code == 200
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in r.headers


def test_a_path_from_the_notes_folder_is_found_after_the_root(vault, client):
    (vault / "Projects/x/logo.png").write_bytes(PNG)
    assert get(client, "logo.png", frm="Projects/x/note.md").content == PNG
    (vault / "Projects/x/rooted.png").write_bytes(b"from the folder")
    (vault / "rooted.png").write_bytes(b"from the root")
    assert get(client, "rooted.png", frm="Projects/x/note.md").content == b"from the root"


def test_a_bare_name_is_found_anywhere_shortest_path_first_then_alphabetical(vault, client):
    (vault / "deep/er/pic.png").write_bytes(b"deep")
    assert get(client, "pic.png").content == b"deep"
    (vault / "assets/pic.png").write_bytes(b"assets")
    assert get(client, "pic.png").content == b"assets"
    (vault / "Attachments/pic.png").write_bytes(b"attachments")  # longer than `assets/`
    assert get(client, "pic.png").content == b"assets"
    for folder in ("zz", "aa"):  # the same length: the alphabet decides
        (vault / folder).mkdir()
        (vault / folder / "tie.png").write_bytes(folder.encode())
    assert get(client, "tie.png").content == b"aa"


def test_a_name_with_a_folder_in_it_is_never_searched_for(vault, client):
    (vault / "deep/er/pic.png").write_bytes(PNG)
    assert get(client, "other/pic.png").status_code == 404
    assert get(client, "er/pic.png").status_code == 404


def test_attachments_and_a_hidden_folder_are_served(vault, client):
    from sympose import vault_hidden

    (vault / "Attachments/pasted.png").write_bytes(b"pasted")
    (vault / "hidden-by-owner/p.png").write_bytes(b"owned")
    assert vault_hidden.hide(str(vault), "hidden-by-owner")
    assert vault_hidden.is_hidden("hidden-by-owner/p.png", vault_hidden.hidden_paths(str(vault)))
    assert get(client, "Attachments/pasted.png").content == b"pasted"
    assert get(client, "pasted.png").content == b"pasted"
    assert get(client, "hidden-by-owner/p.png").content == b"owned"
    assert get(client, "p.png").content == b"owned"


@pytest.mark.parametrize("ref", ["../outside.png", "/etc/hosts.png", "assets/../../outside.png", ".obsidian/x.png", ""])
def test_a_path_out_of_the_vault_or_into_a_dot_folder_is_refused(vault, client, ref):
    (vault.parent / "outside.png").write_bytes(PNG)
    (vault / ".obsidian/x.png").write_bytes(PNG)
    assert get(client, ref).status_code == 404


def test_a_dot_folder_is_not_searched_for_a_bare_name(vault, client):
    (vault / ".obsidian/only.png").write_bytes(PNG)
    assert get(client, "only.png").status_code == 404


def test_the_notes_own_dot_folder_is_not_a_way_in(vault, client):
    (vault / ".obsidian/x.png").write_bytes(PNG)
    assert get(client, "x.png", frm=".obsidian/note.md").status_code == 404


def test_another_personas_folder_is_refused(vault, client):
    (vault / "Private/secret.png").write_bytes(PNG)
    (vault / "Projects/x/ok.png").write_bytes(PNG)
    assert get(client, "Private/secret.png", persona="narrow").status_code == 404
    assert get(client, "secret.png", persona="narrow").status_code == 404
    assert get(client, "Projects/x/ok.png", persona="narrow").status_code == 200


def test_an_unknown_persona_is_404(vault, client):
    assert get(client, "a.png", persona="nobody").status_code == 404


def test_a_symlink_out_of_the_vault_is_refused(vault, client):
    (vault.parent / "elsewhere.png").write_bytes(PNG)
    (vault / "assets/link.png").symlink_to(vault.parent / "elsewhere.png")
    assert get(client, "assets/link.png").status_code == 404


@pytest.mark.parametrize("name", ["notes.md", "movie.mp4", "doc.pdf", "data.txt", "noext"])
def test_a_file_that_is_not_one_of_the_image_types_is_refused(vault, client, name):
    (vault / "assets" / name).write_bytes(b"x")
    assert get(client, f"assets/{name}").status_code == 404


def test_the_extension_is_compared_in_lower_case(vault, client):
    (vault / "assets/Shot.PNG").write_bytes(PNG)
    r = get(client, "assets/Shot.PNG")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_every_listed_type_has_its_media_type(vault, client):
    for ext, media in vault_image.IMAGE_TYPES.items():
        (vault / "assets" / f"p{ext}").write_bytes(b"x")
        assert get(client, f"assets/p{ext}").headers["content-type"].split(";")[0] == media


def test_an_svg_is_sandboxed(vault, client):
    (vault / "assets/d.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    r = get(client, "assets/d.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_a_file_over_the_limit_is_413(vault, client, monkeypatch):
    monkeypatch.setattr(vault_image, "MAX_IMAGE_BYTES", 10)
    (vault / "assets/big.png").write_bytes(b"x" * 11)
    (vault / "assets/small.png").write_bytes(b"x" * 10)
    assert get(client, "assets/big.png").status_code == 413
    assert get(client, "assets/small.png").status_code == 200


def test_the_limit_is_twenty_megabytes():
    assert vault_image.MAX_IMAGE_BYTES == 20 * 1024 * 1024


def test_a_missing_file_is_404(vault, client):
    assert get(client, "assets/nope.png").status_code == 404


def test_head_gives_the_same_status_without_a_body(vault, client):
    (vault / "assets/shot.png").write_bytes(PNG)
    ok = get(client, "assets/shot.png", method="head")
    assert ok.status_code == 200 and ok.content == b""
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert get(client, "assets/nope.png", method="head").status_code == 404


def test_images_do_not_enter_the_tree_or_the_graph(vault, client):
    before_tree = client.get("/api/vault/tree", params={"persona": "samantha"}).json()
    before_graph = client.get("/api/vault/graph", params={"persona": "samantha"}).json()
    (vault / "assets/shot.png").write_bytes(PNG)
    (vault / "Projects/x/logo.svg").write_text("<svg/>")
    after_tree = client.get("/api/vault/tree", params={"persona": "samantha"}).json()
    after_graph = client.get("/api/vault/graph", params={"persona": "samantha"}).json()
    assert after_tree == before_tree
    assert after_graph == before_graph


def test_an_absolute_path_is_refused_even_into_the_vault(vault, client):
    (vault / "assets/shot.png").write_bytes(PNG)
    assert get(client, str(vault / "assets/shot.png")).status_code == 404


def test_a_path_with_a_folder_is_tried_from_the_notes_folder(vault, client):
    (vault / "Projects/x/img").mkdir()
    (vault / "Projects/x/img/pic.png").write_bytes(b"from the folder")
    assert get(client, "img/pic.png", frm="Projects/x/note.md").content == b"from the folder"
    assert get(client, "img/pic.png").status_code == 404  # from the root there is no `img/`


def test_a_windows_path_is_read_with_forward_slashes(vault, client):
    (vault / "Projects/x/img").mkdir()
    (vault / "Projects/x/img/pic.png").write_bytes(b"win")
    assert get(client, "assets\\..\\Projects\\x\\img\\pic.png").content == b"win"
    assert get(client, "img\\pic.png", frm="Projects\\x\\note.md").content == b"win"


def test_a_file_that_goes_away_between_finding_and_sizing_is_404(vault, client, monkeypatch):
    (vault / "assets/shot.png").write_bytes(PNG)

    def gone(path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(vault_image.os.path, "getsize", gone)
    assert get(client, "assets/shot.png").status_code == 404
