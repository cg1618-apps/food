"""The request id that ties a log line to the request that produced it.

Four applications share one tunnel and one log collector, so a line saying
"IntegrityError" is worth very little on its own. Every line logged while
handling a request carries the same `request_id`, and the response carries it
back in `X-Request-ID`, so a reader who saw a failure in the browser can find
every line that belongs to it.

The contract is the platform's `docs/logging.md`; this file is food's half of
it, and deliberately matches media's.

Pure ASGI rather than `BaseHTTPMiddleware`: that class runs the rest of the
application in a task of its own, and a `ContextVar` set around `call_next`
then lives in a different context from the endpoint that logs. Setting the
variable here happens in the same task that awaits the app below it, so the
value is simply in scope.
"""

import re
from contextvars import ContextVar, Token
from uuid import uuid4

from starlette.datastructures import MutableHeaders

REQUEST_ID_HEADER = "X-Request-ID"

# The header is caller-supplied and food is `exposure: public`, so on this
# hostname its value arrives from the open internet. JSON encoding stops the
# classic log-forging case - a newline is escaped rather than written - but an
# unbounded value rides on EVERY line of the request and goes straight into the
# collector's storage, and a client can reuse another request's id to make
# correlation lie while the log still reads as coherent. A generated id is 32
# hex characters, so anything that is not a short, boring token is replaced
# rather than trusted.
_SAFE_REQUEST_ID = re.compile(r"\A[A-Za-z0-9_-]{1,64}\Z")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """The id of the request being handled, or None outside a request."""
    return _request_id.get()


def set_request_id(value: str | None) -> Token:
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def _incoming_id(scope) -> str:
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name == b"x-request-id":
            candidate = raw_value.decode("latin-1")
            if _SAFE_REQUEST_ID.match(candidate):
                return candidate
            break
    return uuid4().hex


class RequestIdMiddleware:
    """Give every HTTP request an id, and echo it back to the caller."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Lifespan and websocket traffic have no request to identify.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_id(scope)
        token = set_request_id(request_id)

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            reset_request_id(token)
