# Logging

food's half of a contract that belongs to the platform. The contract itself is
`cg1618-apps/platform`'s `docs/logging.md` — the field names, the formats, the
request-id rules — and this page says how food implements it and what is
specific to food. **Where the two disagree, the contract wins**, because the
collector on the box indexes every app's output and four vocabularies is the
same as none.

Audit trails are a different thing and are not here. "Who changed this
ingredient" is domain data, and it belongs in food's own tables and its own UI.

## The two files

| File | Holds |
| --- | --- |
| `app/logging_config.py` | `configure()`, the two formatters, the request-id filter, the uvicorn takeover |
| `app/request_context.py` | the `ContextVar`, the ASGI middleware, and the inbound-header rules |

`configure()` is called once, at the top of `create_app()` in `app/main.py`,
before anything else can log. `RequestIdMiddleware` is added **first**, so it is
the outermost middleware and the id exists before `errors.install(app)` puts the
handlers in — which is the code most likely to be logging when any of this
matters.

## What a line looks like

Production is JSON lines on stdout, one object per line:

```json
{"timestamp":"2026-09-20T13:48:53.214+00:00","level":"INFO","logger":"app.routers.ingredient","message":"picked salt from shelf","app":"food","request_id":"9f2c..."}
```

Development is the plain human format, with the request id appended only when
there is one:

```
2026-09-20 13:48:53,214 INFO     app.routers.ingredient: picked salt from shelf [request_id=9f2c...]
```

Which one is chosen by `settings.is_development`, which reads `APP_ENV` — not by
a separate switch. A second flag is a second thing to get wrong, and the way it
goes wrong is that production quietly emits the development format for months
while every line still looks fine to a human reading `docker logs`.

`request_id` is **omitted** outside a request, never written as `null`. That is
what makes its presence mean "this happened inside a request", and it keeps an
empty field off every startup and migration line.

## `app` is `"food"`, and the container is `food-app-1`

They are supposed to differ, and neither is wrong: one is what the application
calls itself — the name in the platform's `apps.yml` — and the other is what
docker calls the process. The collector labels streams by container; the field
is what tells you which app a line came from when it arrives with no label, in a
terminal or a bug report.

Do not "fix" either to match the other. Deriving `app` from the container name
empties it outside a container; renaming the container breaks the `food-app`
network alias the generated ingress routes to, and `food.cg1618.com` answers 502
while `apps.yml` and `docker-compose.prod.yml` each still read correctly alone.

## uvicorn's three loggers are taken over, and they have to be

`app/logging_config.py` names `uvicorn`, `uvicorn.error` and `uvicorn.access`,
gives each the same console handler and sets `propagate: False` on each.

Without that, food emits a **half-structured stream**: uvicorn installs its own
handlers at startup and sets `propagate = False`, so a `dictConfig` that
configures only the root logger leaves every access line in plain text while the
app's own lines turn JSON. The unparsed half is the access log — the
highest-volume and most useful part — and the whole thing looks completely fine
in `docker logs`, which is where anyone would check.

`propagate: False` matters in the other direction too: this handler *plus*
uvicorn's own emits every access line twice.

This is why the JSON formatter and the takeover landed in one commit. The window
between them is exactly that mixed stream, and it is invisible.

## The inbound `X-Request-ID` is validated, because food is public

food is `exposure: public` and cloudflared forwards client headers to the origin
unmodified, so on this hostname the header arrives **from the open internet**.

`app/request_context.py` accepts it only against `^[A-Za-z0-9_-]{1,64}$`, and
otherwise ignores what was sent and generates a fresh `uuid4().hex`. The
response always echoes the id that was *used*, not the one that arrived.

JSON encoding already prevents the classic log-forging attack — a newline in the
value is escaped rather than written — so this is not a hole for injected lines.
What it prevents:

- an unbounded value riding on **every line** of that request and going straight
  into the collector's storage;
- a client deliberately reusing another request's id, which makes correlation
  lie while the log still reads as coherent.

## `%s`, never f-strings

```python
logger.info("picked %s from %s", name, shelf)   # yes
logger.info(f"picked {name} from {shelf}")      # no
```

An f-string renders at the call site, so `record.msg` holds a finished sentence
and `record.args` is empty. The template stops being a grouping key for the
collector, formatting happens even when the level would discard the line, and
the arguments can never be promoted to fields later without rewriting every call
site — which `media` had to do for 85 of them.

`tests/unit/test_logging_config.py::test_no_log_call_formats_its_own_message`
walks `app/` with an AST scan and fails on the first one.

## What is asserted, and the two tests that look like decoration

`tests/unit/test_logging_config.py` and `tests/unit/test_request_id.py`.

Two of them are load-bearing in a way that is easy to miss, and both exist
because the test next to them would pass without them:

- **`test_the_f_string_guard_can_actually_fail`.** The AST scan asserts it found
  nothing. A detector that never matches anything passes that exactly as well as
  a working one, and would keep passing through the change that fills this app
  with f-string log calls. This one proves the detector fires.
- **`test_an_id_of_exactly_sixty_four_characters_is_honoured`.** Every rejection
  test asserts "a fresh id was generated instead". A validator that rejected
  *everything* would satisfy all of them. This is the boundary case proving it
  accepts, and it sits on the limit rather than safely inside it.

`test_uvicorns_own_loggers_are_taken_over` asserts the handler **by identity**
against the root console handler, not that some handler exists — uvicorn's own
handler would satisfy the weaker check while the bug is present.

## The docker side

`docker-compose.prod.yml` caps the log driver: `json-file`, `max-size: "10m"`,
`max-file: "5"`. Both quoted, because `max-file` as a YAML integer is rejected
when the container starts.

That bounds a buffer and is not retention: a `docker compose up -d` that
recreates the container discards its log outright. Anything meant to survive a
deploy goes to the collector described in `cg1618-apps/platform`'s
`docs/logging.md` — which is built but not serving yet.
