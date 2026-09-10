"""The self-update path: what it downloads, from where, and what it refuses to run.

This is the highest-consequence code in the app. It fetches a file over the network and
launches it as the user. Three things used to stand between a request and that: nothing.
The endpoint took a ``download_url`` from the caller, ``urllib.request.urlopen`` honours
``file:`` and ``ftp:`` as happily as https, and the checksum was skipped whenever the release
did not happen to list the filename.

Nothing here touches the network. The seams are the release lookup and ``urlopen``.
"""

from __future__ import annotations

import hashlib
import tempfile
import threading
from pathlib import Path

import pytest

from omnivert import app_updates
from omnivert import installer_update
from omnivert.build_info import DEFAULT_APP_REPO

GITHUB_ASSET = (
    f"https://github.com/{DEFAULT_APP_REPO}/releases/download/v9.9.9/Omnivert-Setup-9.9.9.exe"
)
FORK_ASSET = (
    "https://github.com/attacker/Omnivert/releases/download/v9.9.9/Omnivert-Setup-9.9.9.exe"
)


@pytest.fixture(autouse=True)
def reset_update_state():
    """``_state`` is module-level and a left-behind "running" would gate the next test."""
    yield
    with app_updates._lock:
        app_updates._state.update(
            {"state": "idle", "message": None, "output": None, "restart_required": False}
        )


# --- where an asset may come from --------------------------------------------------------

@pytest.mark.parametrize(
    "url, allowed, why",
    [
        (GITHUB_ASSET, True, "the browser_download_url this build's own release publishes"),
        (FORK_ASSET, False, "a different account's release, still served by github.com"),
        ("https://evil.example/Omnivert-Setup.exe", False, "not GitHub at all"),
        (GITHUB_ASSET.replace("https://", "http://"), False, "plain http, tamperable"),
        ("file:///C:/Windows/System32/calc.exe", False, "urlopen speaks file: too"),
        ("ftp://github.com/Setup.exe", False, "and ftp:"),
        ("https://github.com.evil.example/Setup.exe", False, "prefix, not the host"),
        (
            f"https://evil.example/https://github.com/{DEFAULT_APP_REPO}/releases/download/x.exe",
            False,
            "the prefix has to be a prefix, not appear somewhere in the URL",
        ),
        ("", False, "nothing at all"),
    ],
)
def test_only_this_builds_own_releases_are_installable(url, allowed, why):
    """A host check is not a provenance check.

    ``app_repo`` is a free-text Settings field, so a host-level "must be github.com" test
    says nothing about WHOSE release is being installed: every account serves assets from
    github.com, and the SHA256SUMS that verifies the download is written by whoever published
    that release, so an attacker's checksum matches an attacker's binary by construction.
    Pointing Settings at a fork can still check for updates; installing is pinned to the repo
    this build was made from.
    """
    assert app_updates.release_asset_allowed(url) is allowed, why


def test_the_pin_follows_the_repo_the_build_was_made_from():
    """``release.yml`` rewrites DEFAULT_APP_REPO to the repo it builds from, so a fork that
    ships its own releases updates from its own rather than being pinned to this one."""
    assert app_updates.release_asset_prefix() == (
        f"https://github.com/{DEFAULT_APP_REPO}/releases/download/"
    )


def test_both_modules_pin_the_same_repo():
    """installer_update re-derives the prefix so it does not trust its caller. Two copies
    that disagreed would mean one of them is wrong."""
    assert installer_update._RELEASE_DOWNLOAD_PREFIX == app_updates.release_asset_prefix()


# --- the client no longer chooses what runs ----------------------------------------------

def test_the_asset_url_is_resolved_server_side(monkeypatch):
    """The URL comes from the configured repo, never from the request.

    ``POST /api/app/updates/apply`` used to carry a ``download_url`` that the server
    downloaded and ``Popen``'d, which made an unauthenticated local endpoint into arbitrary
    code execution for anything that could reach it.
    """
    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(
        app_updates,
        "check_for_app_update",
        lambda: {"configured": True, "error": None, "update_available": True,
                 "download_url": GITHUB_ASSET},
    )
    seen: dict = {}
    done = threading.Event()

    def record(url):
        seen["url"] = url
        done.set()

    monkeypatch.setattr(app_updates, "_run_installer_update", record)

    app_updates.start_app_update()

    assert done.wait(10), "the update thread never ran"
    assert seen["url"] == GITHUB_ASSET


def test_start_app_update_takes_no_url_at_all():
    """A parameter the caller can fill is a parameter the caller can abuse. There is no
    "trusted" caller here: the only client is a browser context anything can POST to."""
    import inspect

    assert list(inspect.signature(app_updates.start_app_update).parameters) == []


@pytest.mark.parametrize(
    "url", ["https://evil.example/Omnivert-Setup.exe", FORK_ASSET], ids=["off-github", "fork"]
)
def test_an_asset_outside_this_builds_repo_is_refused(monkeypatch, url):
    """Covers the whole path from a repointed ``app_repo`` to the launcher.

    Setting ``app_repo`` to a repo the attacker owns makes ``check_for_app_update`` return
    their asset, on github.com, with their own SHA256SUMS backing it. The repo pin is the
    only thing in the chain that notices.
    """
    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(
        app_updates,
        "check_for_app_update",
        lambda: {"configured": True, "error": None, "update_available": True,
                 "download_url": url},
    )
    monkeypatch.setattr(
        app_updates,
        "_run_installer_update",
        lambda u: pytest.fail(f"downloaded {u} anyway"),
    )

    status = app_updates.start_app_update()

    assert status["state"] == "error"
    assert DEFAULT_APP_REPO in str(status["message"])


def test_an_exception_while_resolving_frees_the_slot(monkeypatch):
    """The slot is claimed before the network call, so anything that escapes would wedge the
    updater on "running" for the life of the process, with every later apply returning the
    "one is already running" answer and starting nothing."""
    def boom():
        raise RuntimeError("malformed release payload")

    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(app_updates, "check_for_app_update", boom)

    status = app_updates.start_app_update()

    assert status["state"] == "error", "the slot was left claimed"
    assert app_updates.get_status()["state"] != "running"


def test_a_second_apply_during_the_first_check_starts_nothing(monkeypatch):
    """Resolving the asset server-side put a GitHub round trip inside a window that used to
    be microseconds wide: between "is one already running" and "mark one running".

    Held open here deliberately. The first apply is parked inside ``check_for_app_update``
    while the second is issued, which is exactly the interleaving two clicks on a slow
    connection produce. If the slot is not claimed before the network call, both get through
    and two installers launch.
    """
    calls: list[int] = []
    started: list[str] = []
    inside_check = threading.Event()
    release_check = threading.Event()

    def check():
        calls.append(1)
        inside_check.set()
        release_check.wait(10)
        return {"configured": True, "error": None, "update_available": True,
                "download_url": GITHUB_ASSET}

    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(app_updates, "check_for_app_update", check)
    monkeypatch.setattr(app_updates, "_run_installer_update", started.append)

    first = threading.Thread(target=app_updates.start_app_update, daemon=True)
    first.start()
    assert inside_check.wait(10), "the first apply never reached the release lookup"

    app_updates.start_app_update()  # the second click, while the first is still resolving
    release_check.set()
    first.join(timeout=10)

    assert calls == [1], "the second apply went to GitHub instead of returning early"
    assert started == [GITHUB_ASSET], f"expected one installer, got {started}"


def test_a_failed_check_stops_the_update(monkeypatch):
    """Resolving the asset server-side means a check that failed leaves nothing to install."""
    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(
        app_updates,
        "check_for_app_update",
        lambda: {"configured": True, "error": "Couldn't reach GitHub: timed out",
                 "download_url": None},
    )
    monkeypatch.setattr(
        app_updates, "_run_installer_update", lambda url: pytest.fail("ran anyway")
    )

    assert app_updates.start_app_update()["state"] == "error"


# --- the checksum is a gate, not a courtesy ----------------------------------------------

SUMS = (
    "aaaa1111  Omnivert-Setup-9.9.9.exe\n"
    "bbbb2222  omnivert-9.9.9-py3-none-any.whl\n"
)


def test_a_listed_filename_yields_its_hash():
    assert app_updates._sha256_from_sums(SUMS, "Omnivert-Setup-9.9.9.exe") == "aaaa1111"


def test_a_binary_marked_line_still_matches():
    """coreutils writes ``*name`` for a binary-mode digest; the release may or may not."""
    assert app_updates._sha256_from_sums("cccc3333 *Setup.exe\n", "Setup.exe") == "cccc3333"


def test_an_unlisted_filename_is_fatal(monkeypatch):
    """This was the whole bypass: an absent filename returned None and the update proceeded,
    so anything not named in SHA256SUMS was installed without being checked."""
    with pytest.raises(RuntimeError) as excinfo:
        app_updates._sha256_from_sums(SUMS, "Something-Else.exe")

    assert "cannot be verified" in str(excinfo.value)


def test_a_release_without_checksums_is_fatal(monkeypatch, isolated_settings):
    from omnivert import settings as settings_module

    settings_module.save({"app_repo": "BrandonDry/Omnivert"})
    monkeypatch.setattr(app_updates.gh, "get_json", lambda url: {"assets": []})

    with pytest.raises(RuntimeError) as excinfo:
        app_updates._expected_sha256("Omnivert-Setup-9.9.9.exe")

    assert "SHA256SUMS" in str(excinfo.value)


def test_a_checksums_file_from_another_repo_is_fatal(monkeypatch, isolated_settings):
    """The checksums decide whether the installer runs, so they are pinned like the installer.

    Without this, a release could pass the installer's repo pin and still be verified against
    a SHA256SUMS fetched from somewhere else, which would simply list the hash of whatever the
    attacker wanted run.
    """
    from omnivert import settings as settings_module

    settings_module.save({"app_repo": "BrandonDry/Omnivert"})
    monkeypatch.setattr(
        app_updates.gh,
        "get_json",
        lambda url: {
            "assets": [
                {
                    "name": "SHA256SUMS",
                    "browser_download_url": (
                        "https://github.com/attacker/Omnivert/releases/download/v9/SHA256SUMS"
                    ),
                }
            ]
        },
    )

    with pytest.raises(RuntimeError) as excinfo:
        app_updates._expected_sha256("Omnivert-Setup-9.9.9.exe")

    assert DEFAULT_APP_REPO in str(excinfo.value)


def test_an_unreachable_checksums_file_is_fatal(monkeypatch, isolated_settings):
    """Failing open on a network error would let anyone who can drop packets skip the check."""
    from omnivert import settings as settings_module

    settings_module.save({"app_repo": "BrandonDry/Omnivert"})

    def boom(url):
        raise OSError("connection reset")

    monkeypatch.setattr(app_updates.gh, "get_json", boom)

    with pytest.raises(RuntimeError):
        app_updates._expected_sha256("Omnivert-Setup-9.9.9.exe")


# --- the download itself -----------------------------------------------------------------

class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Served:
    """Bytes for ``download_installer`` to receive, plus a record of what it asked for.

    ``fetched`` is the assertion that matters for every refusal below. Checking only that a
    ValueError came back proves nothing: a download that goes ahead and then fails its
    checksum raises ValueError too, so a test written that way passes whether the URL was
    refused before the request or after it. Two of these were written that way first, and
    both survived having the gate they were meant to cover deleted.
    """

    def __init__(self, directory: Path):
        self.directory = directory
        self.fetched: list[str] = []


@pytest.fixture
def served(monkeypatch, tmp_path):
    def serve(payload: bytes) -> _Served:
        record = _Served(tmp_path)

        def fake_urlopen(url, timeout=None):
            record.fetched.append(url)
            return _FakeResponse(payload)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr(tempfile, "mkdtemp", lambda prefix=None: str(tmp_path))
        return record

    return serve


def test_a_good_download_is_returned(served):
    payload = b"MZ pretend installer"
    record = served(payload)

    path = installer_update.download_installer(
        GITHUB_ASSET, hashlib.sha256(payload).hexdigest()
    )

    assert path.read_bytes() == payload
    assert path.parent == record.directory
    assert record.fetched == [GITHUB_ASSET]


def test_a_checksum_mismatch_leaves_nothing_to_launch(served):
    """The one refusal that happens after the fetch: the bytes have to arrive to be hashed."""
    record = served(b"not the installer you published")

    with pytest.raises(ValueError) as excinfo:
        installer_update.download_installer(GITHUB_ASSET, "0" * 64)

    assert "checksum" in str(excinfo.value).lower()
    assert record.fetched == [GITHUB_ASSET]
    assert list(record.directory.glob("*.exe")) == [], "the rejected download stayed on disk"


def test_no_checksum_means_no_download(served):
    """The argument is required now. It used to default to None, and None meant "skip"."""
    record = served(b"anything")

    with pytest.raises(ValueError):
        installer_update.download_installer(GITHUB_ASSET, "")

    assert record.fetched == [], "downloaded a file it had no way to verify"


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Windows/System32/calc.exe",
        "ftp://github.com/Omnivert-Setup.exe",
        GITHUB_ASSET.replace("https://", "http://"),
        "https://evil.example/Omnivert-Setup.exe",
        FORK_ASSET,
    ],
)
def test_the_download_refuses_anything_but_this_builds_own_releases(served, url):
    """Checked here as well as in the caller on purpose: this function writes a file and its
    caller then launches it, so it does not assume anyone upstream checked."""
    record = served(b"payload")

    with pytest.raises(ValueError):
        installer_update.download_installer(url, "0" * 64)

    assert record.fetched == [], f"opened {url}"


def test_a_non_exe_asset_is_refused(served):
    record = served(b"payload")

    with pytest.raises(ValueError):
        installer_update.download_installer(
            f"https://github.com/{DEFAULT_APP_REPO}/releases/download/v9/notes.txt", "0" * 64
        )

    assert record.fetched == []


def test_an_up_to_date_build_refuses_to_install_anything(monkeypatch):
    """``update_available`` is a security gate, not just a UI hint.

    The frontend already hides the button, but the frontend is not the boundary: a
    same-origin POST straight to the route would otherwise re-download and launch the
    CURRENT release's installer on a machine already running it. Repo-pinned and
    checksum-verified, so not code execution, but an unauthenticated local trigger for an
    installer launch is not something to leave open.
    """
    started = []
    monkeypatch.setattr(app_updates, "is_frozen", lambda: True)
    monkeypatch.setattr(app_updates, "_run_installer_update", lambda url: started.append(url))
    monkeypatch.setattr(
        app_updates,
        "check_for_app_update",
        lambda: {
            "configured": True,
            "error": None,
            "update_available": False,
            "download_url": GITHUB_ASSET,
        },
    )

    result = app_updates.start_app_update()

    assert result["state"] == "error"
    assert "up to date" in str(result["message"]).lower()
    assert started == [], f"an up-to-date build still launched an installer: {started}"


def test_a_traversing_asset_url_is_refused():
    """A bare prefix test accepted a URL that climbed back out of the pinned repository. Not
    reachable through a real GitHub asset URL, but this is the gate that decides which
    executable gets launched, so it should not read as stronger than it is."""
    assert not app_updates.release_asset_allowed(
        f"https://github.com/{DEFAULT_APP_REPO}/releases/download/../../../attacker/evil/x.exe"
    )


@pytest.mark.parametrize(
    "repo,accepted",
    [
        ("BrandonDry/Omnivert", True),
        ("owner/repo", False),          # the placeholder default
        ("a/..%2Fb", False),            # survived the old "exactly one slash" test
        ("owner/repo/extra", False),
        ("/leading", False),
        ("owner/", False),
        ("own er/repo", False),
        ("", False),
    ],
)
def test_the_configured_repo_must_look_like_a_repo(monkeypatch, repo, accepted):
    monkeypatch.setattr(app_updates.settings_module, "load", lambda: {"app_repo": repo})
    assert (app_updates._repo() is not None) is accepted
