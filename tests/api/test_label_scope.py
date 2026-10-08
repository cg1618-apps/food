"""Every label belongs to exactly one library: ingredient, dish or note.

Every refusal here is set up to bite: a label of the OTHER scope exists and is
sent, and the mirror sends a label of the right scope through the same route.
Without the wrong-scope label a check that refused nothing would pass.
"""

import pytest


def _label(client, name, scope):
    response = client.post("/api/edit/labels", json={"name_cn": name, "scope": scope})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def labels(client):
    """One label per library, each named 辣 - the per-scope uniqueness lets
    them share it, and the refusals must not be fooled by the name."""
    return {scope: _label(client, "辣", scope) for scope in ("ingredient", "dish", "note")}


# ---- the label itself ------------------------------------------------------


def test_a_label_needs_a_scope(client):
    response = client.post("/api/edit/labels", json={"name_cn": "辣"})
    assert response.status_code == 422, response.text


def test_an_unknown_scope_is_422(client):
    response = client.post("/api/edit/labels", json={"name_cn": "辣", "scope": "recipe"})
    assert response.status_code == 422, response.text


def test_a_name_is_unique_per_scope_not_globally(client, labels):
    """`labels` already made 辣 in all three scopes; a second ingredient 辣,
    in either slot's case, is the refusal."""
    response = client.post("/api/edit/labels", json={"name_cn": "辣", "scope": "ingredient"})
    assert response.status_code == 409, response.text


def test_the_list_filters_by_scope(client, labels):
    _label(client, "常備", "ingredient")
    dish = client.get("/api/labels", params={"scope": "dish"}).json()
    assert [row["id"] for row in dish] == [labels["dish"]["id"]]
    assert {row["scope"] for row in dish} == {"dish"}

    # The mirror: without the filter every scope comes back.
    every = client.get("/api/labels").json()
    assert {row["scope"] for row in every} == {"ingredient", "dish", "note"}
    assert len(every) == 4


def test_the_list_refuses_an_unknown_scope(client):
    assert client.get("/api/labels", params={"scope": "recipe"}).status_code == 422


def test_an_unused_label_can_move_to_another_library(client):
    label = _label(client, "閒置", "dish")
    moved = client.patch(f"/api/edit/labels/{label['id']}", json={"scope": "note"})
    assert moved.status_code == 200, moved.text
    assert moved.json()["scope"] == "note"


def test_a_label_in_use_cannot_move(client, labels):
    """In use by a dish, so moving it would leave a dish carrying a note
    label. The refusal carries the count, as deleting an in-use value does."""
    client.post(
        "/api/edit/dishes", json={"name_cn": "麻婆豆腐", "label_ids": [labels["dish"]["id"]]}
    ).raise_for_status()

    response = client.patch(f"/api/edit/labels/{labels['dish']['id']}", json={"scope": "note"})
    assert response.status_code == 409, response.text
    assert response.json()["usage_count"] == 1
    by_id = {row["id"]: row for row in client.get("/api/labels").json()}
    assert by_id[labels["dish"]["id"]]["scope"] == "dish"

    # The mirror: the same in-use label still renames, and naming its own
    # scope is not a move.
    renamed = client.patch(
        f"/api/edit/labels/{labels['dish']['id']}", json={"name_en": "hot", "scope": "dish"}
    )
    assert renamed.status_code == 200, renamed.text


def test_a_scope_cannot_be_cleared(client, labels):
    response = client.patch(f"/api/edit/labels/{labels['note']['id']}", json={"scope": None})
    assert response.status_code == 422, response.text


# ---- the owners ------------------------------------------------------------


def test_an_ingredient_takes_only_ingredient_labels(client, labels, fallback_category):
    base = {"category_id": fallback_category.id}
    wrong = client.post(
        "/api/edit/ingredients",
        json={**base, "name_cn": "辣椒", "label_ids": [labels["dish"]["id"]]},
    )
    assert wrong.status_code == 422, wrong.text

    made = client.post(
        "/api/edit/ingredients",
        json={**base, "name_cn": "辣椒", "label_ids": [labels["ingredient"]["id"]]},
    )
    assert made.status_code == 201, made.text

    url = f"/api/edit/ingredients/{made.json()['id']}"
    patched = client.patch(url, json={"label_ids": [labels["note"]["id"]]})
    assert patched.status_code == 422, patched.text
    assert client.patch(url, json={"label_ids": [labels["ingredient"]["id"]]}).status_code == 200


def test_the_attach_endpoint_takes_only_ingredient_labels(client, labels, fallback_category):
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "花椒", "category_id": fallback_category.id}
    ).json()
    url = f"/api/edit/ingredients/{ingredient['id']}/labels"

    assert client.post(f"{url}/{labels['dish']['id']}").status_code == 422
    assert client.post(f"{url}/{labels['ingredient']['id']}").status_code == 204
    shown = client.get(f"/api/ingredients/{ingredient['id']}").json()["labels"]
    assert [row["id"] for row in shown] == [labels["ingredient"]["id"]]


def test_a_dish_takes_only_dish_labels(client, labels):
    wrong = client.post(
        "/api/edit/dishes", json={"name_cn": "麻辣鍋", "label_ids": [labels["ingredient"]["id"]]}
    )
    assert wrong.status_code == 422, wrong.text

    made = client.post(
        "/api/edit/dishes", json={"name_cn": "麻辣鍋", "label_ids": [labels["dish"]["id"]]}
    )
    assert made.status_code == 201, made.text

    url = f"/api/edit/dishes/{made.json()['id']}"
    assert client.patch(url, json={"label_ids": [labels["note"]["id"]]}).status_code == 422
    assert client.patch(url, json={"label_ids": [labels["dish"]["id"]]}).status_code == 200


def test_a_note_takes_only_note_labels(client, labels):
    wrong = client.post(
        "/api/edit/kitchen-notes", json={"title": "辣油", "label_ids": [labels["dish"]["id"]]}
    )
    assert wrong.status_code == 422, wrong.text

    made = client.post(
        "/api/edit/kitchen-notes", json={"title": "辣油", "label_ids": [labels["note"]["id"]]}
    )
    assert made.status_code == 201, made.text

    url = f"/api/edit/kitchen-notes/{made.json()['id']}"
    assert client.patch(url, json={"label_ids": [labels["ingredient"]["id"]]}).status_code == 422
    assert client.patch(url, json={"label_ids": [labels["note"]["id"]]}).status_code == 200


def test_the_scopes_are_served_in_the_settings_order(client):
    """設定 draws a section per scope in this order: 食材, 料理, 筆記."""
    body = client.get("/api/vocabularies/fixed").json()
    assert body["label_scopes"] == [
        {"value": "ingredient", "label": "食材"},
        {"value": "dish", "label": "料理"},
        {"value": "note", "label": "筆記"},
    ]
