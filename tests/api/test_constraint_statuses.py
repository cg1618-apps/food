"""Every constraint, driven through HTTP, answering the status it should.

This file is the whole reason the IntegrityError backstop exists. Media
documented the same discipline - mirror each constraint in the schema layer so
a violation is a 422 rather than a 500 - installed no global handler, and
drifted into unhandled 500s for years. About sixty of its tests assert
`IntegrityError`, every one of them at the ORM or session level, and not one
asserts an HTTP status. The promise was about the HTTP layer and was never
tested there.

So: one test per row of the mapping in `app/errors.py`, through the client.

The pairs matter as much as the cases. A handler that returned 409 for
everything would pass half of these, and a handler that returned 422 for
everything would pass the other half. Only both together pin the mapping - and
`23503` appears twice on purpose, because the same foreign-key violation means
a malformed payload going in and a live reference on the way out.
"""

from app.errors import (
    CHECK_VIOLATION,
    FOREIGN_KEY_VIOLATION,
    NOT_NULL_VIOLATION,
    UNIQUE_VIOLATION,
    integrity_status,
)


def test_the_mapping_itself(subtests=None):
    """The table in one place, independent of any route reaching it.

    A unit check of the classifier, so that a change to the mapping fails here
    with a readable diff rather than as five unrelated route tests.
    """
    assert integrity_status(CHECK_VIOLATION, "POST") == 422
    assert integrity_status(NOT_NULL_VIOLATION, "POST") == 422
    assert integrity_status(UNIQUE_VIOLATION, "POST") == 409
    assert integrity_status(FOREIGN_KEY_VIOLATION, "POST") == 422
    assert integrity_status(FOREIGN_KEY_VIOLATION, "PATCH") == 422
    assert integrity_status(FOREIGN_KEY_VIOLATION, "DELETE") == 409
    # An unmapped integrity error is still the database refusing a change.
    assert integrity_status("XXXXX", "POST") == 409


# ---- 23514 check_violation -> 422 ----------------------------------------


def test_an_ingredient_with_no_name_is_422(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients", json={"category_id": fallback_category.id}
    )
    assert response.status_code == 422, response.text


def test_a_blank_string_name_is_422_not_a_row_with_no_usable_name(
    client, fallback_category
):
    """Empty form fields normalise to null, so this hits the same rule.

    Without that normalisation `""` satisfies `num_nonnulls`, the CHECK is
    happy, and the row commits with no name anyone can see - a 201 that is
    worse than either error.
    """
    response = client.post(
        "/api/edit/ingredients",
        json={"category_id": fallback_category.id, "name_cn": "   ", "name_en": ""},
    )
    assert response.status_code == 422, response.text


def test_a_preservation_time_of_zero_is_422(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "category_id": fallback_category.id,
            "name_cn": "生薑",
            "preservation": [{"method": "冷藏", "duration_days": 0}],
        },
    )
    assert response.status_code == 422, response.text


# ---- 23505 unique_violation -> 409 ---------------------------------------


def test_a_duplicate_name_is_409(client, ingredient, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={"category_id": fallback_category.id, "name_cn": ingredient.name_cn},
    )
    assert response.status_code == 409, response.text
    assert "Chinese name" in response.json()["detail"]


def test_a_duplicate_name_differing_only_in_case_is_409(client, ingredient, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={"category_id": fallback_category.id, "name_en": ingredient.name_en.upper()},
    )
    assert response.status_code == 409, response.text


def test_a_duplicate_label_name_is_409(client):
    assert client.post("/api/edit/labels", json={"name_cn": "常備"}).status_code == 201
    response = client.post("/api/edit/labels", json={"name_cn": "常備"})
    assert response.status_code == 409, response.text


def test_two_sibling_categories_sharing_a_name_is_409(client):
    assert client.post("/api/edit/ingredient-categories", json={"name_cn": "調味料"}).status_code == 201
    response = client.post("/api/edit/ingredient-categories", json={"name_cn": "調味料"})
    assert response.status_code == 409, response.text


# ---- 23503 foreign_key_violation, going in -> 422 ------------------------


def test_filing_an_ingredient_in_a_category_that_does_not_exist_is_422(client):
    response = client.post(
        "/api/edit/ingredients", json={"category_id": 9999, "name_cn": "生薑"}
    )
    assert response.status_code == 422, response.text


def test_naming_a_parent_that_does_not_exist_is_422(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={"category_id": fallback_category.id, "name_cn": "生抽", "parent_id": 9999},
    )
    assert response.status_code == 422, response.text


# ---- 23503 foreign_key_violation, on the way out -> 409 ------------------


def test_deleting_an_ingredient_that_has_children_is_409(client, ingredient, fallback_category):
    """The other half of 23503, and the one a flat mapping gets wrong.

    Nothing about the request is malformed: the ingredient exists, the counts
    are right. The state refuses, which is a conflict and not a validation
    error.
    """
    child = client.post(
        "/api/edit/ingredients",
        json={
            "category_id": fallback_category.id,
            "name_cn": "生抽",
            "parent_id": ingredient.id,
        },
    )
    assert child.status_code == 201, child.text

    response = client.delete(
        f"/api/edit/ingredients/{ingredient.id}?aliases=0&preservation=0"
    )
    assert response.status_code == 409, response.text
    assert "still refers to this" in response.json()["detail"]


def test_deleting_a_category_with_ingredients_in_it_is_409(client, ingredient, fallback_category):
    other = client.post("/api/edit/ingredient-categories", json={"name_cn": "根莖類"})
    category_id = other.json()["id"]
    moved = client.patch(
        f"/api/edit/ingredients/{ingredient.id}", json={"category_id": category_id}
    )
    assert moved.status_code == 200, moved.text

    response = client.delete(f"/api/edit/ingredient-categories/{category_id}")
    assert response.status_code == 409, response.text


def test_deleting_an_empty_category_succeeds(client):
    """The mirror. A handler that answered 409 for every DELETE would pass
    every test above this one."""
    created = client.post("/api/edit/ingredient-categories", json={"name_cn": "乾貨"})
    response = client.delete(f"/api/edit/ingredient-categories/{created.json()['id']}")
    assert response.status_code == 204, response.text


# ---- the error body itself ----------------------------------------------


def test_an_error_body_is_a_detail_string(client, ingredient, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={"category_id": fallback_category.id, "name_cn": ingredient.name_cn},
    )
    body = response.json()
    assert isinstance(body["detail"], str)
    assert "code" not in body


def test_a_validation_error_body_carries_the_array_fastapi_produces(client):
    """Not a defect - a documented shape the client must handle.

    FastAPI's automatic validation error puts a LIST under `detail`, unlike
    every hand-raised error in this app. Media's client wrapper assumes a
    string and renders this as "[object Object]", which is the message a
    malformed body produces and therefore the one users actually see. Ours
    joins the messages, and this test is what says the array is real.
    """
    response = client.post("/api/edit/ingredients", json={"category_id": "not an int"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
