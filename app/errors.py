"""One error shape, and the backstop that keeps a constraint from being a 500.

On the wire every error is `{"detail": "<a sentence>"}`. There is no
machine-readable code field: one user, no translations, and the HTTP status
already says which kind of failure this is. Nothing branches on the prose, so
any message here can be reworded without breaking a caller.

**Where a caller must ACT on an error, the error carries data beside the
detail** - not a code. `AppError` serialises its extras into the body, so a
dialog can say "this now removes 4, not 3" and re-offer the button instead of
telling the user to reload. That is a pattern from the first use rather than a
hand-built response somebody escapes the idiom for: `HTTPException` carries
`detail` and nothing else, which is precisely what defeated media's one
attempt at this, and the extra field it needed was then dropped by its client
wrapper anyway.

The `IntegrityError` handler is a BACKSTOP, not the mechanism. The schema layer
mirrors each constraint so the ordinary path answers 422 before the database is
touched. The backstop exists because media documented exactly that discipline,
installed no global handler, and drifted into unhandled 500s for years - while
about sixty tests asserted `IntegrityError` at the ORM level and not one
asserted an HTTP status. `tests/api/test_constraint_statuses.py` is what stops
the same thing happening here.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# Decided once, with every constraint in the schema in front of us, rather than
# per-constraint as each one first appears. Classified by SQLSTATE rather than
# by constraint name, so a constraint added later is mapped by what kind of
# violation it is instead of by whether anyone remembered to add it here.
#
# 23503 is the split that would have been missed: the same foreign-key
# violation means "your payload names a row that does not exist" on a write and
# "something still references this row" on a delete. Flattening both to 409
# would be wrong for the first, and to 422 wrong for the second.
CHECK_VIOLATION = "23514"
NOT_NULL_VIOLATION = "23502"
UNIQUE_VIOLATION = "23505"
FOREIGN_KEY_VIOLATION = "23503"

# A sentence per constraint we can name. Anything absent falls back to the
# generic line for its SQLSTATE - which is why adding a constraint does not
# require editing this dict, only improves the message when it does.
CONSTRAINT_MESSAGES = {
    "ck_ingredient_has_a_name": "An ingredient needs at least one name.",
    "ck_ingredient_category_has_a_name": "A category needs at least one name.",
    "ck_label_has_a_name": "A label needs at least one name.",
    "ck_recipe_course_has_a_name": "A course needs at least one name.",
    "uq_recipe_course_name_cn": "Another course already has that Chinese name.",
    "uq_recipe_course_name_en": "Another course already has that English name.",
    "ck_recipe_status_has_a_name": "A status needs at least one name.",
    "uq_recipe_status_name_cn": "Another status already has that Chinese name.",
    "uq_recipe_status_name_en": "Another status already has that English name.",
    "ck_source_platform_has_a_name": "A source platform needs at least one name.",
    "uq_source_platform_name_cn": "Another source platform already has that Chinese name.",
    "uq_source_platform_name_en": "Another source platform already has that English name.",
    "ck_cooking_method_has_a_name": "A cooking method needs at least one name.",
    "uq_cooking_method_name_cn": "Another cooking method already has that Chinese name.",
    "uq_cooking_method_name_en": "Another cooking method already has that English name.",
    "ck_author_has_a_name": "An author needs at least one name.",
    "uq_author_name_cn": "Another author already has that Chinese name.",
    "uq_author_name_en": "Another author already has that English name.",
    "ck_equipment_has_a_name": "A piece of equipment needs at least one name.",
    "uq_equipment_name_cn": "Another piece of equipment already has that Chinese name.",
    "uq_equipment_name_en": "Another piece of equipment already has that English name.",
    "ck_ingredient_preservation_duration_positive": (
        "A storage time has to be a positive number of days, or left empty."
    ),
    "ck_ingredient_preservation_duration_order": (
        "The shortest storage time cannot be longer than the longest."
    ),
    "ck_ingredient_heating_temperature_positive": "A temperature has to be positive.",
    "uq_image_checksum": "That image is already in the library.",
    "uq_ingredient_image_position": "Two images cannot share one position.",
    "uq_ingredient_image_once": "That image is already in this gallery.",
    "uq_ingredient_name_cn": "Another ingredient already has that Chinese name.",
    "uq_ingredient_name_en": "Another ingredient already has that English name.",
    "uq_label_name_cn": "Another label already has that Chinese name.",
    "uq_label_name_en": "Another label already has that English name.",
    "uq_ingredient_alias": "That ingredient already carries that alias.",
    "uq_ingredient_preservation_state_method": (
        "That ingredient already has a note for that state and storage method."
    ),
    "uq_ingredient_category_sibling_cn": (
        "Another category in the same place already has that name."
    ),
    "uq_ingredient_category_one_fallback": (
        "There is already a fallback category, and there may only be one."
    ),
    "ck_recipe_has_a_name": "A recipe needs at least one name.",
    "ck_recipe_not_its_own_version": "A recipe cannot be a version of itself.",
    "uq_recipe_alias": "That recipe already carries that alias.",
    "ck_recipe_source_has_content": "A source needs an author, a link or a title.",
    "uq_recipe_line_position": "Two ingredient lines cannot share one position.",
    "ck_recipe_line_one_target": (
        "An ingredient line names exactly one ingredient or one recipe."
    ),
    "ck_recipe_line_not_itself": "A recipe cannot use itself as an ingredient.",
    "uq_recipe_step_position": "Two steps cannot share one position.",
    "uq_recipe_image_position": "Two images cannot share one position.",
    "uq_recipe_image_once": "That image is already in this gallery.",
    "ck_tbd_link_has_a_url": "A link needs a URL.",
}

GENERIC_MESSAGES = {
    CHECK_VIOLATION: "That change does not satisfy a rule on the data.",
    NOT_NULL_VIOLATION: "Something required was left empty.",
    UNIQUE_VIOLATION: "Something else already has that value.",
}


class AppError(Exception):
    """An error with a sentence, a status, and optionally data to act on."""

    def __init__(self, status_code: int, detail: str, **extras):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.extras = extras


class StaleCountError(AppError):
    """The row count shown in a confirmation dialog is no longer true.

    Any delete that cascades rows the user was shown a count of takes that
    count as a required parameter and raises this when it has moved. It is an
    optimistic check and not a lock - nothing is held between the count and the
    delete - and it guards human staleness rather than a concurrent writer. In
    a one-user app the stale tab is the whole case, and it is the common one.

    `expected` and `actual` ride on the body so the dialog can correct itself
    in place. Without them the only recovery a page has is a full reload, which
    is why media's equivalent message ends "Reload and confirm again" - the
    sentence is an artifact of having nothing to hand back.

    `field` names which count moved, using the delete's query-parameter names.
    Several counts can share a value, so a dialog matching `expected` against
    its own numbers would correct the wrong one and loop.
    """

    def __init__(self, field: str, what: str, expected: int, actual: int):
        super().__init__(
            409,
            f"This now removes {actual} {what}, not {expected}. Check and confirm again.",
            field=field,
            expected=expected,
            actual=actual,
        )


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(
        getattr(exc, "orig", None), "pgcode", None
    )


def _constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None)


def integrity_status(sqlstate: str | None, method: str) -> int:
    """The status a constraint violation answers with. See the note above."""
    if sqlstate in (CHECK_VIOLATION, NOT_NULL_VIOLATION):
        return 422
    if sqlstate == UNIQUE_VIOLATION:
        return 409
    if sqlstate == FOREIGN_KEY_VIOLATION:
        # Going in, a bad reference is a malformed payload. On the way out, a
        # live reference is the state refusing a request that is itself fine.
        return 409 if method == "DELETE" else 422
    # An integrity error we have no mapping for is still the database refusing
    # a change, not the server falling over - 409 says that without claiming to
    # know which rule it was. It is logged at error so it stops being unnamed.
    return 409


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail, **exc.extras}
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        sqlstate = _sqlstate(exc)
        constraint = _constraint_name(exc)
        status = integrity_status(sqlstate, request.method)

        detail = CONSTRAINT_MESSAGES.get(constraint) or GENERIC_MESSAGES.get(sqlstate)
        if detail is None:
            detail = (
                "Something else still refers to this, so it cannot be removed."
                if status == 409 and request.method == "DELETE"
                else "The database refused that change."
            )

        logger.warning(
            "integrity error on %s %s: sqlstate=%s constraint=%s",
            request.method,
            request.url.path,
            sqlstate,
            constraint,
        )
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500, content={"detail": "An unexpected server error occurred."}
        )
