"""常用食材: the chips the recipe form offers, ungrouped first, then in groups.

Read whole and replaced whole. The `four` fixture is what makes the refusals
and the cascade bite: an empty structure replaced by an empty one, or an
ingredient deleted while nothing is listed, passes every assertion here
vacuously. The duplicate refusals name their repeat across two DIFFERENT
places (two groups, a group and 未分組), each beside the mirror case that
succeeds, so a green proves the check looks across the whole structure.
"""

import pytest

from app.models import CommonIngredient, CommonIngredientGroup, Ingredient

URL = "/api/common-ingredients"
EDIT_URL = "/api/edit/common-ingredients"


@pytest.fixture
def four(db, fallback_category):
    rows = [
        Ingredient(name_cn="蒜", category_id=fallback_category.id),
        Ingredient(name_cn="薑", category_id=fallback_category.id),
        Ingredient(name_cn="蔥", category_id=fallback_category.id, needs_detail=True),
        Ingredient(name_cn="雞腿", category_id=fallback_category.id),
    ]
    db.add_all(rows)
    db.flush()
    return [row.id for row in rows]


def put(client, ungrouped=(), groups=()):
    return client.put(EDIT_URL, json={"ungrouped": list(ungrouped), "groups": list(groups)})


def read(client):
    response = client.get(URL)
    assert response.status_code == 200, response.text
    return response.json()


def ids(refs):
    return [ref["id"] for ref in refs]


def shape(body):
    """The structure as ids: (ungrouped, [(name, ids)])."""
    return ids(body["ungrouped"]), [(g["name"], ids(g["ingredients"])) for g in body["groups"]]


def test_the_structure_starts_empty(client):
    assert read(client) == {"ungrouped": [], "groups": []}


def test_an_ungrouped_put_keeps_the_order_sent(client, four):
    garlic, ginger, scallion, _ = four
    response = put(client, [scallion, garlic, ginger])
    assert response.status_code == 200, response.text
    assert response.json() == read(client)
    body = read(client)
    assert body["groups"] == []
    assert ids(body["ungrouped"]) == [scallion, garlic, ginger]
    assert body["ungrouped"][0] == {"id": scallion, "display_name": "蔥", "needs_detail": True}


def test_groups_keep_their_order_and_their_chips_order(client, four):
    garlic, ginger, scallion, thigh = four
    response = put(
        client,
        [ginger],
        [
            {"name": "調味料", "ingredient_ids": [scallion, garlic]},
            {"name": "肉", "ingredient_ids": [thigh]},
        ],
    )
    assert response.status_code == 200, response.text
    assert shape(read(client)) == ([ginger], [("調味料", [scallion, garlic]), ("肉", [thigh])])
    assert all(isinstance(group["id"], int) for group in read(client)["groups"])


def test_a_group_may_be_empty(client, four):
    assert put(client, four[:1], [{"name": "肉", "ingredient_ids": []}]).status_code == 200
    assert shape(read(client)) == ([four[0]], [("肉", [])])


def test_a_group_sent_with_its_id_is_renamed_and_moved_not_replaced(client, four):
    garlic, ginger, scallion, thigh = four
    put(
        client,
        [],
        [{"name": "肉", "ingredient_ids": [thigh]}, {"name": "調味料", "ingredient_ids": [garlic]}],
    )
    meat, seasoning = (group["id"] for group in read(client)["groups"])

    response = put(
        client,
        [ginger],
        [
            {"id": seasoning, "name": "辛香料", "ingredient_ids": [garlic, scallion]},
            {"id": meat, "name": "肉", "ingredient_ids": [thigh]},
        ],
    )
    assert response.status_code == 200, response.text
    body = read(client)
    assert [(g["id"], g["name"]) for g in body["groups"]] == [(seasoning, "辛香料"), (meat, "肉")]
    assert shape(body) == ([ginger], [("辛香料", [garlic, scallion]), ("肉", [thigh])])


def test_two_groups_may_swap_names_in_one_put(client, four):
    """The unique index on lower(name) is checked row by row, so a swap
    written naively collides with itself halfway through."""
    put(client, [], [{"name": "甲", "ingredient_ids": []}, {"name": "乙", "ingredient_ids": []}])
    first, second = (group["id"] for group in read(client)["groups"])
    response = put(
        client,
        [],
        [{"id": first, "name": "乙", "ingredient_ids": []}, {"id": second, "name": "甲", "ingredient_ids": []}],
    )
    assert response.status_code == 200, response.text
    assert [(g["id"], g["name"]) for g in read(client)["groups"]] == [(first, "乙"), (second, "甲")]


def test_a_group_not_sent_is_deleted_and_its_chips_go_where_the_put_puts_them(client, db, four):
    """Deleting a group in 設定 sends its chips at the end of 未分組; the
    server writes exactly that, and nothing is lost."""
    garlic, ginger, scallion, thigh = four
    put(client, [garlic], [{"name": "肉", "ingredient_ids": [thigh, ginger]}])
    response = put(client, [garlic, thigh, ginger], [])
    assert response.status_code == 200, response.text
    assert shape(read(client)) == ([garlic, thigh, ginger], [])
    assert db.query(CommonIngredientGroup).count() == 0
    assert db.query(CommonIngredient).count() == 3


def test_a_group_deleted_underneath_its_chips_leaves_them_ungrouped(client, db, four):
    """SET NULL is the schema's backstop: whatever deletes a group, its chips
    survive it, as ungrouped ones."""
    garlic, ginger, _, thigh = four
    put(client, [garlic], [{"name": "肉", "ingredient_ids": [thigh, ginger]}])
    db.query(CommonIngredientGroup).delete()
    db.flush()
    db.expire_all()
    body = read(client)
    assert body["groups"] == []
    assert set(ids(body["ungrouped"])) == {garlic, thigh, ginger}


def test_a_put_can_empty_everything(client, four):
    put(client, four[:1], [{"name": "肉", "ingredient_ids": four[1:2]}])
    assert put(client).status_code == 200
    assert read(client) == {"ungrouped": [], "groups": []}


# ---- refusals: 422, nothing written ---------------------------------------


@pytest.fixture
def stored(client, four):
    """Something on the list, so "nothing changed" is not vacuous."""
    garlic, ginger, scallion, thigh = four
    assert put(client, [garlic], [{"name": "肉", "ingredient_ids": [thigh]}]).status_code == 200
    return read(client)


def test_an_ingredient_in_two_groups_is_422_and_changes_nothing(client, four, stored):
    garlic, ginger, scallion, thigh = four
    response = put(
        client,
        [],
        [{"name": "甲", "ingredient_ids": [ginger]}, {"name": "乙", "ingredient_ids": [scallion, ginger]}],
    )
    assert response.status_code == 422
    assert "detail" in response.json()
    assert read(client) == stored

    # The mirror: the same two groups without the repeat are accepted.
    mirror = put(
        client,
        [],
        [{"name": "甲", "ingredient_ids": [ginger]}, {"name": "乙", "ingredient_ids": [scallion]}],
    )
    assert mirror.status_code == 200, mirror.text


def test_an_ingredient_both_ungrouped_and_in_a_group_is_422(client, four, stored):
    garlic, ginger, scallion, thigh = four
    response = put(client, [ginger], [{"name": "甲", "ingredient_ids": [ginger]}])
    assert response.status_code == 422
    assert read(client) == stored
    assert put(client, [ginger], [{"name": "甲", "ingredient_ids": [scallion]}]).status_code == 200


def test_an_unknown_ingredient_is_422_and_changes_nothing(client, four, stored):
    response = put(client, [], [{"name": "甲", "ingredient_ids": [four[1], 999999]}])
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    assert read(client) == stored


def test_an_unknown_group_id_is_422_and_changes_nothing(client, four, stored):
    response = put(client, [], [{"id": 999999, "name": "甲", "ingredient_ids": []}])
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    assert read(client) == stored


def test_a_group_id_sent_twice_is_422(client, four, stored):
    meat = stored["groups"][0]["id"]
    response = put(
        client,
        [],
        [{"id": meat, "name": "甲", "ingredient_ids": []}, {"id": meat, "name": "乙", "ingredient_ids": []}],
    )
    assert response.status_code == 422
    assert read(client) == stored


@pytest.mark.parametrize("name", ["", "   ", None])
def test_a_blank_group_name_is_422(client, four, stored, name):
    response = put(client, [], [{"name": name, "ingredient_ids": []}])
    assert response.status_code == 422
    assert read(client) == stored


def test_a_duplicate_group_name_any_case_is_422_and_changes_nothing(client, four, stored):
    response = put(
        client,
        [],
        [{"name": "Meat", "ingredient_ids": []}, {"name": " meat ", "ingredient_ids": []}],
    )
    assert response.status_code == 422
    assert read(client) == stored
    # The mirror: two different names are accepted.
    assert put(client, [], [{"name": "Meat", "ingredient_ids": []}, {"name": "Fish", "ingredient_ids": []}]).status_code == 200


def test_a_group_name_is_stored_trimmed(client, four):
    assert put(client, [], [{"name": "  肉 ", "ingredient_ids": []}]).status_code == 200
    assert read(client)["groups"][0]["name"] == "肉"


def test_the_body_refuses_extra_fields(client, four):
    response = client.put(EDIT_URL, json={"ungrouped": four, "groups": [], "append": True})
    assert response.status_code == 422
    response = client.put(
        EDIT_URL, json={"ungrouped": [], "groups": [{"name": "甲", "ingredient_ids": [], "x": 1}]}
    )
    assert response.status_code == 422


def test_the_old_flat_body_is_refused(client, four):
    assert client.put(EDIT_URL, json={"ingredient_ids": four}).status_code == 422


def test_the_write_is_behind_the_edit_prefix_only(client, four):
    assert client.put(URL, json={"ungrouped": four, "groups": []}).status_code == 405


# ---- an ingredient deleted or merged ---------------------------------------


def test_deleting_a_listed_ingredient_takes_it_off_the_list(client, db, four):
    garlic, ginger, scallion, thigh = four
    put(client, [garlic, ginger], [{"name": "肉", "ingredient_ids": [thigh, scallion]}])
    for gone in (ginger, thigh):
        response = client.delete(
            f"/api/edit/ingredients/{gone}",
            params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
        )
        assert response.status_code == 204, response.text
    assert shape(read(client)) == ([garlic], [("肉", [scallion])])
    assert db.query(CommonIngredient).count() == 2


def _merge(client, source, into):
    preview = client.get(f"/api/ingredients/{source}/merge-preview", params={"into": into})
    assert preview.status_code == 200, preview.text
    return client.post(
        f"/api/edit/ingredients/{source}/merge",
        json={"into": into, "fingerprint": preview.json()["fingerprint"]},
    )


def test_a_merge_moves_the_sources_entry_to_the_target_in_place(client, four):
    garlic, ginger, scallion, _ = four
    put(client, [garlic, ginger])  # scallion, the target, is not listed
    assert _merge(client, ginger, scallion).status_code == 200
    assert shape(read(client)) == ([garlic, scallion], [])


def test_a_merge_keeps_the_sources_group_and_place(client, four):
    garlic, ginger, scallion, thigh = four
    put(client, [garlic], [{"name": "辛香料", "ingredient_ids": [ginger, thigh]}])
    assert _merge(client, ginger, scallion).status_code == 200
    assert shape(read(client)) == ([garlic], [("辛香料", [scallion, thigh])])


def test_a_merge_into_a_listed_target_drops_the_sources_entry(client, four):
    garlic, ginger, scallion, thigh = four
    put(client, [scallion], [{"name": "辛香料", "ingredient_ids": [ginger, garlic]}])
    assert _merge(client, ginger, scallion).status_code == 200
    # The target keeps its own place; the source's, in another group, goes.
    assert shape(read(client)) == ([scallion], [("辛香料", [garlic])])


def test_a_merge_of_an_unlisted_source_leaves_the_list_alone(client, four):
    garlic, ginger, scallion, _ = four
    put(client, [garlic, scallion])
    assert _merge(client, ginger, scallion).status_code == 200
    assert shape(read(client)) == ([garlic, scallion], [])
