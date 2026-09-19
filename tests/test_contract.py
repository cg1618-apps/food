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
