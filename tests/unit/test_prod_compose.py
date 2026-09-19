"""The production compose file's invariants.

These are the properties that are easy to break by accident and expensive to
notice: a published port exposes the app outside the tunnel, a missing restart
policy means the box comes back from a power cut without the app, and a probe
against "/" reports healthy with the database down.

The file these assert against is never exercised by this suite - it runs on a
machine CI cannot reach - so structure is the only thing that can be checked
here. That makes it worth checking.

The ingress is not this repository's business. PostgreSQL and the Cloudflare
Tunnel belong to cg1618-apps/platform, and the tunnel's rules are generated
there from apps.yml. What remains here is the end of the contract this
repository owns: the network alias the generated ingress points at.

This app has no bind mounts yet. It is expected to grow one - dishes,
ingredients and snack packages all want photographs - so the assertion below
pins the rule that survives that change rather than the current emptiness: a
mount may name a DIRECTORY and never a single file.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.prod.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_file_exists():
    assert COMPOSE.is_file(), f"{COMPOSE} is missing"


def test_the_app_is_the_only_service(compose):
    # db and cloudflared are the platform's. An app repository that grows a
    # database service again has stopped sharing the box's PostgreSQL, which is
    # a decision to be made deliberately, not an edit to this file.
    assert set(compose["services"]) == {"app"}


def test_the_app_publishes_no_port(compose):
    # The tunnel is the only ingress. A published port would bypass Cloudflare
    # entirely and put the app on the LAN.
    assert "ports" not in compose["services"]["app"]


def test_the_app_restarts_unless_stopped(compose):
    # Load-bearing since depends_on went away with the database: this is the
    # only thing that recovers the app when it starts before PostgreSQL does.
    #
    # Not "always": a deliberate `docker compose stop` must survive a daemon
    # restart, or debugging on the box fights the restart policy.
    assert compose["services"]["app"]["restart"] == "unless-stopped"


def test_the_app_does_not_hardcode_a_container_name(compose):
    # Compose derives names from COMPOSE_PROJECT_NAME, which makes the project
    # name the one place a name is written. A hardcoded container_name is a
    # second place for a stale one to hide.
    assert "container_name" not in compose["services"]["app"]


def test_the_app_joins_the_shared_network_as_food_app(compose):
    # This alias is the contract with the generated ingress in
    # cg1618-apps/platform, which routes food.cg1618.com to
    # http://food-app:8001. Change it here alone and the hostname 502s while
    # both files still read as correct on their own.
    app_networks = compose["services"]["app"]["networks"]
    assert app_networks["cg1618"]["aliases"] == ["food-app"]
    assert compose["services"]["app"]["environment"]["PORT"] == 8001


def test_the_shared_network_is_external(compose):
    # The platform's compose project creates it. Defining it here as well is
    # how a second, empty network ends up carrying half the containers.
    assert compose["networks"]["cg1618"]["external"] is True


def test_the_app_declares_no_depends_on(compose):
    # Not an oversight to be tidied back in: compose cannot order services
    # across projects, and a depends_on naming a service this file does not
    # define fails the whole `up` with "service not found".
    assert "depends_on" not in compose["services"]["app"]


def test_the_app_healthcheck_does_not_probe_the_catch_all_route(compose):
    # app/main.py's catch-all route serves the SPA for any path, so a check
    # against "/" returns 200 with the database down, and a healthcheck that
    # lies is worse than none.
    #
    # /health retires that reasoning by opening a real session, reading
    # alembic_version, and comparing it to the head the running code expects -
    # so it fails when the database is gone AND when the schema and the image
    # disagree, which is the state a half-rolled-back deploy leaves behind.
    #
    # This pins the DISTINCTION, not the presence. Repointing the probe at "/"
    # must fail rather than pass quietly, because that single character is the
    # whole difference between a check and a lie.
    probe = " ".join(compose["services"]["app"]["healthcheck"]["test"])
    assert "/health" in probe, probe

    # And it must probe the port the app is actually told to listen on.
    # Pinning the path alone lets PORT and the probe's URL drift apart
    # silently: the container then reports unhealthy forever while each line
    # reads as correct on its own.
    port = compose["services"]["app"]["environment"]["PORT"]
    assert f":{port}/health" in probe, probe


def test_app_carries_an_image_name_alongside_build(compose):
    # Keeps the move to a registry a one-line change: the service already
    # refers to an image by name, so only what that name points at changes.
    app = compose["services"]["app"]
    assert app["build"]["context"] == "."
    assert app["image"] == "food-app:local"


def test_no_mount_names_a_single_file(compose):
    # Docker creates a missing bind source as a DIRECTORY. A mount whose
    # source is a file that does not exist on the box therefore shadows the
    # file inside the image with an empty directory, and the app fails to
    # read its own shipped file - a failure that names the file rather than
    # the mount.
    #
    # Written before the first mount exists, so the first one added is
    # checked rather than the rule being remembered at the time.
    for mount in compose["services"]["app"].get("volumes", []):
        source = mount["source"] if isinstance(mount, dict) else mount.split(":")[0]
        assert "." not in Path(source).name, (
            f"{source} looks like a file; bind-mount the directory holding it instead"
        )


def test_the_compose_file_sits_beside_the_env_it_interpolates():
    """Compose loads `.env` from the compose file's own directory.

    Moving this file into a subdirectory makes every ${...} interpolate to an
    empty string, while `env_file:` keeps working - so the app still starts,
    with a database password of "". That is the quiet version of this failure,
    and it is why the file lives at the repository root.
    """
    assert COMPOSE.parent == ROOT, (
        f"{COMPOSE.name} must sit beside .env at the repository root; found it in {COMPOSE.parent}"
    )
