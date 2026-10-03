"""The probe the edit pages use to reach the Cloudflare Access login.

This route checks nothing and authenticates nobody: Access answers before the
app does, so a request that arrives here has already been let through. That is
the whole of what it reports.

It exists because a single-page app changes page without a document load, and
a page under /edit reached by a click inside the app never goes past Access.
Its writes do - as background requests - and a background request that Access
redirects to its login is one the browser refuses to follow across origins, so
it dies as "Failed to fetch". The edit pages therefore ask here first, with
`redirect: 'manual'`: a 204 means signed in, a redirect means not, and the
browser is then sent here as a top-level navigation with `next`, which Access
CAN take through its login and back. This route then returns it to the page it
left.

`next` is confined to edit pages. An open redirect on a signed-in path is a
phishing link carrying this hostname, and nothing outside /edit needs a
sign-in to come back to.
"""

from fastapi import HTTPException, Query, Response
from fastapi.responses import RedirectResponse

from app.routing import EDIT_PAGES_PREFIX, write_router

router = write_router("session", "Session")


def is_edit_page(path: str) -> bool:
    """A same-origin path to an edit page, and nothing that could leave it.

    A path starting "/edit/" cannot be protocol-relative, and the backslash and
    control-character checks shut the two ways a browser or a header could
    read something else into it.
    """
    if "\\" in path or any(ord(char) < 0x20 or ord(char) == 0x7F for char in path):
        return False
    return (
        path == EDIT_PAGES_PREFIX
        or path.startswith(f"{EDIT_PAGES_PREFIX}/")
        or path.startswith(f"{EDIT_PAGES_PREFIX}?")
    )


@router.get("", status_code=204, response_class=Response)
def session(next: str | None = Query(None, description="The edit page to return to.")):
    if next is None:
        return Response(status_code=204)
    if not is_edit_page(next):
        raise HTTPException(status_code=400, detail="next must be a path under /edit")
    return RedirectResponse(next, status_code=303)
