"""常用食材: the ordered list of ingredients the recipe form offers as chips.

Read whole and replaced whole. The `three` fixture is what makes the refusals
and the cascade bite: an empty list replaced by an empty list, or an ingredient
deleted while nothing is listed, passes every assertion here vacuously.
"""

import pytest

from app.models import CommonIngredient, Ingredient

URL = "/api/common-ingredients"
EDIT_URL = "/api/edit/common-ingredients"


@pytest.fixture
def three(db, fallback_category):
    rows = [
        Ingredient(name_cn="蒜", category_id=fallback_category.id),
        Ingredient(name_cn="薑", category_id=fallback_category.id),
        Ingredient(name_cn="蔥", category_id=fallback_category.id, needs_detail=True),
    ]
    db.add_all(rows)
    db.flush()
    return [row.id for row in rows]


def put(client, ids):
    return client.put(EDIT_URL, json={"ingredient_ids": ids})


def listed(client):
    response = client.get(URL)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_list_starts_empty(client):
    assert listed(client) == []


def test_a_put_replaces_the_list_in_the_order_sent(client, three):
    garlic, ginger, scallion = three
    response = put(client, [scallion, garlic, ginger])
    assert response.status_code == 200, response.text
    assert response.json() == listed(client)

    body = listed(client)
    assert [row["ingredient"]["id"] for row in body] == [scallion, garlic, ginger]
    assert [row["sort_order"] for row in body] == [0, 1, 2]
    assert body[0]["ingredient"] == {"id": scallion, "display_name": "蔥", "needs_detail": True}


def test_a_second_put_reorders_and_removes(client, three):
    garlic, ginger, scallion = three
    put(client, [garlic, ginger, scallion])
    assert put(client, [ginger, garlic]).status_code == 200
    assert [row["ingredient"]["id"] for row in listed(client)] == [ginger, garlic]

    assert put(client, []).status_code == 200
    assert listed(client) == []


def test_an_unknown_ingredient_is_422_and_changes_nothing(client, three):
    put(client, three[:2])
    response = put(client, [three[2], 999999])
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    assert [row["ingredient"]["id"] for row in listed(client)] == three[:2]


def test_a_duplicate_is_422_and_changes_nothing(client, three):
    put(client, three[:2])
    response = put(client, [three[2], three[2]])
    assert response.status_code == 422
    assert "detail" in response.json()
    assert [row["ingredient"]["id"] for row in listed(client)] == three[:2]


def test_the_body_refuses_extra_fields(client, three):
    response = client.put(EDIT_URL, json={"ingredient_ids": three, "append": True})
    assert response.status_code == 422


def test_the_write_is_behind_the_edit_prefix_only(client, three):
    assert client.put(URL, json={"ingredient_ids": three}).status_code == 405


def test_deleting_a_listed_ingredient_takes_it_off_the_list(client, db, three):
    garlic, ginger, scallion = three
    put(client, [garlic, ginger, scallion])
    response = client.delete(
        f"/api/edit/ingredients/{ginger}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    assert response.status_code == 204, response.text
    assert [row["ingredient"]["id"] for row in listed(client)] == [garlic, scallion]
    assert db.query(CommonIngredient).count() == 2


def _merge(client, source, into):
    preview = client.get(f"/api/ingredients/{source}/merge-preview", params={"into": into})
    assert preview.status_code == 200, preview.text
    return client.post(
        f"/api/edit/ingredients/{source}/merge",
        json={"into": into, "fingerprint": preview.json()["fingerprint"]},
    )


def test_a_merge_moves_the_sources_entry_to_the_target_in_place(client, three):
    garlic, ginger, scallion = three
    put(client, [garlic, ginger])  # scallion, the target, is not listed
    assert _merge(client, ginger, scallion).status_code == 200
    body = listed(client)
    assert [row["ingredient"]["id"] for row in body] == [garlic, scallion]
    assert [row["sort_order"] for row in body] == [0, 1]


def test_a_merge_into_a_listed_target_drops_the_sources_entry(client, three):
    garlic, ginger, scallion = three
    put(client, [ginger, garlic, scallion])
    assert _merge(client, ginger, scallion).status_code == 200
    assert [row["ingredient"]["id"] for row in listed(client)] == [garlic, scallion]


def test_a_merge_of_an_unlisted_source_leaves_the_list_alone(client, three):
    garlic, ginger, scallion = three
    put(client, [garlic, scallion])
    assert _merge(client, ginger, scallion).status_code == 200
    assert [row["ingredient"]["id"] for row in listed(client)] == [garlic, scallion]
