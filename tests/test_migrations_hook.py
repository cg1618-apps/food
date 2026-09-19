"""The hook's shape. The platform calls it; a wrong exit code misleads a deploy."""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "deploy" / "migrations"


def code() -> str:
    lines = HOOK.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_it_fails_fast():
    assert "set -euo pipefail" in HOOK.read_text(encoding="utf-8")


def test_it_implements_the_three_subcommands():
    body = code()
    for command in ("current", "added", "downgrade"):
        assert f"{command})" in body, command


def test_current_reads_the_database_not_the_files():
    # The revision the DATABASE believes it is at is the only authoritative
    # answer during a rollback; asking the image tells you what that image
    # knows, which is the thing that has just changed.
    assert "alembic_version" in code()


def test_an_unknown_subcommand_exits_non_zero_and_says_so():
    # The other tests read the script's text, which cannot tell a working
    # branch from an empty one. This runs it: bash is available here and the
    # usage path touches neither docker nor the database.
    # Try to find bash in common locations
    bash_candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        shutil.which("bash"),
    ]
    bash_exe = next((b for b in bash_candidates if b and Path(b).exists()), None)
    if not bash_exe:
        bash_exe = shutil.which("bash") or "bash"

    result = subprocess.run(
        [bash_exe, str(HOOK), "nonsense"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "usage:" in result.stderr.lower(), result.stderr
    assert result.stdout.strip() == "", "usage belongs on stderr, not stdout"


def bash() -> str:
    """The bash that runs the hook. Windows has no /bin/bash on PATH."""
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        shutil.which("bash"),
    ]
    found = next((b for b in candidates if b and Path(b).exists()), None)
    return found or shutil.which("bash") or "bash"


def run_current(tmp_path: Path, version_table: str | None) -> subprocess.CompletedProcess:
    """Run the hook's `current` against a stub database.

    `version_table` is the contents of alembic_version: None for "the table
    does not exist", "" for "it exists and is empty", otherwise the revision.

    The stub stands in for `docker`, so this exercises the hook's real control
    flow - the quoting, the exit codes and which SQL it sends - without a
    container. A text assertion cannot tell a working branch from an empty one.
    """
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    exists = "f" if version_table is None else "t"
    rows = "" if not version_table else version_table
    (stub_dir / "docker").write_text(
        "#!/usr/bin/env bash\n"
        "# The SQL is the last argument of `... psql -U u -d d -tAc <sql>`.\n"
        'sql="${!#}"\n'
        "case \"${sql}\" in\n"
        f'    *to_regclass*) echo "{exists}" ;;\n'
        f'    *alembic_version*) printf "%s\n" "{rows}" ;;\n'
        '    *) echo "stub got unexpected SQL: ${sql}" >&2; exit 1 ;;\n'
        "esac\n",
        encoding="utf-8",
        newline="\n",
    )
    (stub_dir / "docker").chmod(0o755)

    env = {
        "PATH": f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "POSTGRES_USER": "food",
        "POSTGRES_DB": "food",
        "PLATFORM_DIR": str(tmp_path),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    return subprocess.run(
        [bash(), str(HOOK), "current"],
        capture_output=True,
        text=True,
        env=env,
    )


def test_current_answers_base_when_nothing_has_been_migrated(tmp_path):
    # Every app's FIRST deploy runs against a database with no
    # alembic_version table, because nothing has created it yet. That is a
    # state with a correct answer, not an error: `base` is Alembic's own name
    # for "before the first revision", and `alembic downgrade base` is a real
    # command. Erroring here refuses the deploy that would have created the
    # schema - which is how food's first deploy failed.
    result = run_current(tmp_path, version_table=None)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "base", result.stdout


def test_current_answers_base_when_the_table_exists_but_is_empty(tmp_path):
    # `alembic downgrade base` leaves the table behind with no rows. A
    # rollback that lands there and is then rolled back again must not error.
    result = run_current(tmp_path, version_table="")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "base", result.stdout


def test_current_answers_the_revision_when_one_is_applied(tmp_path):
    # The mirror of the two above: with a revision present the hook must
    # report THAT, not `base`. Without this, a hook hard-coded to print
    # `base` would pass both tests above and destroy the schema on a
    # rollback.
    result = run_current(tmp_path, version_table="0001_baseline")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0001_baseline", result.stdout
