"""Where a route lives, and the one definition of the gated prefix.

This app has no authentication code and will have none. The gate on writes is
Cloudflare Access, which is all-or-nothing per PATH - so the read/write split
has to exist in the URL or there is no gate at all, and a public hostname with
unprotected write endpoints is a public editor.

`WRITE_PREFIX` is the single definition of that path. Every write router
derives its prefix from it, `tests/api/test_route_prefixes.py` asserts no
mutation escapes it, and `deploy/gated-paths` is generated from it for the
platform to read.

The platform's `apps.yml` also carries `gated_paths`, and `bin/deploy` refuses
when the two disagree in either direction. That is two copies on purpose:
`bin/check-exposure --all` runs from the platform repository with no app
checkout, and a registry silent on paths could only ever be checked from the
box. Two copies with a loud refusal beat a security check that cannot run from
where people are - but this file is the authority, and the registry is what is
checked against it.
"""

from fastapi import APIRouter

WRITE_PREFIX = "/api/edit"
READ_PREFIX = "/api"

# What `deploy/gated-paths` contains, and what `apps.yml` must agree with.
# A list rather than a bare string because the registry key is plural and the
# day this app needs a second gated prefix should not be the day the file
# format changes.
GATED_PATHS = [WRITE_PREFIX]


def read_router(resource: str, tag: str) -> APIRouter:
    """A public router. Everything here is readable by anyone, signed out."""
    return APIRouter(prefix=f"{READ_PREFIX}/{resource}", tags=[tag])


def write_router(resource: str, tag: str) -> APIRouter:
    """A router behind Access. Every mutation in this app goes through one.

    Use this rather than writing the prefix by hand: a literal "/api/edit" in
    a router file is a second copy of the thing this module exists to be the
    only copy of.
    """
    return APIRouter(prefix=f"{WRITE_PREFIX}/{resource}", tags=[f"{tag} (edit)"])
