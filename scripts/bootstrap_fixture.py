"""Restore the golden fixture repo's git history from a bundle.

The synthetic golden project under ``tests/golden_projects/synthetic_pipeline/repo``
is checked into this repository as a flat file tree. A nested git repository
cannot be versioned (it would be recorded as a gitlink / empty submodule), so the
fixture's git history is shipped as a git bundle
(``scripts/golden_fixture_repo.bundle``). This script re-initialises the fixture
directory as a real git repository and restores the two commits pinned in
``tests/golden_projects/synthetic_pipeline/manifest.toml`` (``d32a15ab…`` base,
``cc56d9d…`` change) with byte-identical SHAs.

Usage::

    python scripts/bootstrap_fixture.py [--force] [--check]

``--check`` only verifies the fixture is bootstrapped and exits nonzero otherwise.
The script is idempotent: a correct, already-initialised fixture is left untouched.

The test session calls :func:`teardown_fixture_git` when it finishes so the
fixture's ``.git`` never lingers in the outer working tree (an embedded ``.git``
would be recorded by the outer repository as a submodule gitlink). If a test run
is interrupted, remove ``tests/golden_projects/synthetic_pipeline/repo/.git``
manually before staging the outer repository.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

BASE_SHA = "d32a15ab5958302f059846389f1dd1ada20e64f2"
CHANGE_SHA = "cc56d9d549b13912a80d5cfd3a10be6a7bb79c62"

ROOT = Path(__file__).resolve().parent.parent
REPO_DIR = ROOT / "tests" / "golden_projects" / "synthetic_pipeline" / "repo"
BUNDLE = ROOT / "scripts" / "golden_fixture_repo.bundle"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")


def is_bootstrapped() -> bool:
    """True when the fixture dir holds both pinned commits at the right HEAD."""
    git_dir = REPO_DIR / ".git"
    if not git_dir.exists():
        return False
    head = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR)
    base = _run(["git", "cat-file", "-e", f"{BASE_SHA}^{{commit}}"], cwd=REPO_DIR)
    change = _run(["git", "cat-file", "-e", f"{CHANGE_SHA}^{{commit}}"], cwd=REPO_DIR)
    return head.returncode == 0 and head.stdout.strip() == CHANGE_SHA and base.returncode == 0 and change.returncode == 0


def ensure_fixture_git() -> str:
    """Bootstrap the fixture repo from the bundle if needed. Returns repo path."""
    if is_bootstrapped():
        return str(REPO_DIR)

    if not BUNDLE.exists():
        raise RuntimeError(f"fixture bundle not found: {BUNDLE}")

    git_dir = REPO_DIR / ".git"
    if git_dir.exists():
        _run(["git", "-c", "core.autocrlf=false", "reset", "--hard"], cwd=REPO_DIR)
        shutil.rmtree(git_dir, ignore_errors=True)

    init = _run(["git", "init", "-b", "main", "-q"], cwd=REPO_DIR)
    if init.returncode != 0:
        raise RuntimeError(f"git init failed: {init.stderr.strip()}")

    fetch = _run(
        ["git", "-c", "core.autocrlf=false", "fetch", "-q", str(BUNDLE), "main:refs/remotes/origin/main"],
        cwd=REPO_DIR,
    )
    if fetch.returncode != 0:
        raise RuntimeError(f"git fetch from bundle failed: {fetch.stderr.strip()}")

    reset = _run(["git", "-c", "core.autocrlf=false", "reset", "-q", "--hard", "origin/main"], cwd=REPO_DIR)
    if reset.returncode != 0:
        raise RuntimeError(f"git reset failed: {reset.stderr.strip()}")

    if not is_bootstrapped():
        head = _run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR).stdout.strip()
        raise RuntimeError(f"fixture SHAs do not match manifest pins (HEAD={head})")
    return str(REPO_DIR)


def teardown_fixture_git() -> None:
    """Remove the fixture's git metadata after use.

    The fixture's ``.git`` must not be present when the outer repository stages
    files, otherwise git records it as an embedded gitlink. The test session
    re-creates it on demand (``ensure_fixture_git``) and removes it at teardown.
    Removal retries briefly to ride out transient Windows file locks.
    """
    git_dir = REPO_DIR / ".git"
    if not git_dir.exists():
        return
    for _ in range(5):
        try:
            for path in git_dir.rglob("*"):
                if path.is_file():
                    path.chmod(path.stat().st_mode | stat.S_IWUSR)
            shutil.rmtree(git_dir)
            return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"could not remove fixture git dir: {git_dir}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv
    check_only = "--check" in argv

    if force:
        git_dir = REPO_DIR / ".git"
        if git_dir.exists():
            _run(["git", "-c", "core.autocrlf=false", "reset", "-q", "--hard"], cwd=REPO_DIR)
            shutil.rmtree(git_dir, ignore_errors=True)

    if check_only:
        ok = is_bootstrapped()
        print(f"fixture {'ok' if ok else 'NOT bootstrapped'} ({REPO_DIR})")
        return 0 if ok else 1

    path = ensure_fixture_git()
    print(f"fixture ready: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
