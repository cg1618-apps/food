"""What can be checked before there is an application.

These assert the parts of the platform contract that exist in this repository
today. They are thin on purpose - the rest of the contract is about a running
container, and there is not one yet.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A filled-in value on any variable whose name says it holds a secret...
SECRET_ASSIGNMENT = re.compile(r"^([A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|KEY))=(.*)$")
# ...and a password inside a connection URL, which carries no such name.
URL_CREDENTIAL = re.compile(r"://[^\s:/@]+:([^\s@/]+)@")


def test_the_env_example_declares_the_database_connection():
    # DATABASE_URL from the environment is one of the four things the platform
    # requires, and .env.example is where a fresh machine learns it exists.
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in text
    assert "POSTGRES_PASSWORD=" in text


def test_the_env_example_carries_no_filled_in_secret():
    # It is committed. A value here is a published credential.
    #
    # Every line is examined - commented ones included, since an example is
    # written as a comment - and a password inside a connection URL as well as
    # the right-hand side of an assignment. Inspecting only lines that begin
    # `POSTGRES_PASSWORD=` would miss a credential pasted into a DATABASE_URL
    # example, which is the shape this file has actually carried and exactly
    # what this test exists to catch.
    for raw in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = raw.lstrip("#").strip()

        assignment = SECRET_ASSIGNMENT.match(line)
        assert not (assignment and assignment.group(2)), raw

        assert URL_CREDENTIAL.search(line) is None, raw


def test_the_compose_project_name_is_pinned():
    # Compose derives it from the directory otherwise, and a different project
    # means a different volume - which looks exactly like data loss.
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "COMPOSE_PROJECT_NAME=food" in text


def test_the_secrets_are_ignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for name in (".env", "credentials.json", "CLAUDE.local.md"):
        assert name in ignored, name


def test_the_dev_launcher_has_a_cmd_wrapper():
    """`dev.cmd` exists so the dev server starts from a double-click or from
    cmd.exe, without anyone having to know the PowerShell execution-policy
    incantation. media and travel both ship one; this is the same file."""
    assert (ROOT / "dev.cmd").is_file()
    assert (ROOT / "dev.ps1").is_file()


def test_batch_files_are_pinned_to_crlf():
    """The non-obvious half of shipping a .cmd, and the reason this test
    exists rather than the file being enough on its own.

    Git stores the blob with LF whatever the working tree holds, so the
    checkout is governed entirely by .gitattributes. Without a rule, a machine
    with core.autocrlf=false gets an LF batch file. cmd.exe survives that in a
    two-line wrapper and misparses it once the file grows a label or an
    if-block, which makes it a defect that appears long after the change that
    caused it.

    media ships dev.cmd and has NO such rule; travel added one. Copying the
    pair that works is the point - the two apps look identical at the file
    level and differ in the attribute that decides what lands on disk.
    """
    import subprocess

    result = subprocess.run(
        ["git", "check-attr", "eol", "--", "dev.cmd"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip().endswith(": eol: crlf"), result.stdout
