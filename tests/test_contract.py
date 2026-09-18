"""What can be checked before there is an application.

These assert the parts of the platform contract that exist in this repository
today. They are thin on purpose - the rest of the contract is about a running
container, and there is not one yet.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_env_example_declares_the_database_connection():
    # DATABASE_URL from the environment is one of the four things the platform
    # requires, and .env.example is where a fresh machine learns it exists.
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DATABASE_URL=" in text
    assert "POSTGRES_PASSWORD=" in text


def test_the_env_example_carries_no_filled_in_secret():
    # It is committed. A value here is a published credential.
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            assert line.strip() == "POSTGRES_PASSWORD=", line


def test_the_compose_project_name_is_pinned():
    # Compose derives it from the directory otherwise, and a different project
    # means a different volume - which looks exactly like data loss.
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "COMPOSE_PROJECT_NAME=food" in text


def test_the_secrets_are_ignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for name in (".env", "credentials.json", "CLAUDE.local.md"):
        assert name in ignored, name
