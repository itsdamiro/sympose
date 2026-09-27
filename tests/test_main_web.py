"""`python -m sympose.main` also serves the built web app, guarded the same way `sympose web` is
(docs/decisions/028). `sympose.main`'s dev server runs with `reload=True`; WatchFiles watches the
subprocess's `cwd` (the scratch `tmp_path` below, not the repo), so an ordinary run is not at risk
from other files changing. Seen flaky only once, twice in a row, immediately after heavy manual
port/process probing on this same machine (stray `sympose.main` processes, several full-suite runs
at once); clean in isolation and in a following full run once those were cleared. If this ever
flakes in a plain CI run, look for port or process contention first, not this fixture's logic."""

import http.client
import os
import signal
import socket
import subprocess
import sys
import time

import pytest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port: int, path: str, host: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path, headers={"Host": host})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("main_web")
    (tmp_path / "vault").mkdir()
    port = _free_port()
    env = dict(os.environ, VAULT_PATHS=str(tmp_path / "vault"), PORT=str(port))
    process = subprocess.Popen(
        [sys.executable, "-m", "sympose.main"],
        cwd=tmp_path, env=env, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                _get(port, "/health", "127.0.0.1")
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise AssertionError("sympose.main never started listening")
        yield port
    finally:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=10)


def test_the_built_web_app_is_served_here_too(server):
    status, body = _get(server, "/", "127.0.0.1")
    assert status == 200 and b"<!doctype html" in body.lower()


def test_a_foreign_host_header_is_refused_here_too(server):
    status, _ = _get(server, "/", "evil.example")
    assert status == 400


def test_the_api_still_answers_under_the_page(server):
    status, body = _get(server, "/health", "127.0.0.1")
    assert status == 200 and b"healthy" in body
