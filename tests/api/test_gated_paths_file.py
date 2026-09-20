"""`deploy/gated-paths` must agree with the code, and ship readable.

The platform reads this file from the COMMIT, not the working tree, and
`bin/deploy` refuses when `apps.yml`'s `gated_paths` disagrees with it in
either direction. Two copies exist on purpose - `bin/check-exposure --all`
runs from the platform repository with no app checkout, so a registry silent on
paths could only ever be checked from the box - but this repository is the
authority and the file is how it says so.

Mode 100644, not 100755. It is data; nothing execs it. `deploy/migrations` is
the opposite and is asserted separately, and the two are checked with the same
mechanism and different expected values so the difference is visible rather
than surprising.
"""

import subprocess
from pathlib import Path

from app.routing import GATED_PATHS

ROOT = Path(__file__).resolve().parents[2]
GATED_PATHS_FILE = ROOT / "deploy" / "gated-paths"


def test_the_file_matches_the_constant():
    expected = "\n".join(GATED_PATHS) + "\n"
    assert GATED_PATHS_FILE.read_bytes().decode() == expected


def test_the_file_is_lf_terminated():
    """A CRLF here is read by the box as a path with a stray carriage return,
    which matches no route and gates nothing - and the failure is silent,
    because a prefix that matches nothing simply protects nothing."""
    assert b"\r" not in GATED_PATHS_FILE.read_bytes()


def test_the_file_is_committed_as_data_not_as_a_hook():
    """`git ls-tree HEAD` reads the commit; `git ls-files` reads the index.

    Only the first says what ships, and the second has reported the wrong
    answer on this box before. core.fileMode is false on both development
    machines, so a mode is never picked up from disk and has to be asserted
    against the commit.
    """
    out = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", "deploy/gated-paths"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    if not out:
        # Before the first commit of this file there is nothing in HEAD to
        # check. Skipping silently would make this test vacuous forever, so it
        # says so out loud instead.
        raise AssertionError("deploy/gated-paths is not committed yet")

    mode = out.split()[0]
    assert mode == "100644", out


def test_the_migrations_hook_is_still_executable():
    """The mirror of the mode assertion above, and the reason it is worth
    having both: same mechanism, different expected value. A copy-paste that
    gave gated-paths 100755 would otherwise look consistent with its
    neighbour."""
    out = subprocess.run(
        ["git", "ls-tree", "HEAD", "--", "deploy/migrations"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out.split()[0] == "100755", out
