"""Labels can be added, renamed and deleted; deleting one detaches it."""


def test_a_label_round_trips_and_deleting_it_detaches_it(
    client, fallback_category, recipe_statuses
):
    label = client.post("/api/edit/labels", json={"name_cn": "辣", "scope": "ingredient"}).json()
    assert label["scope"] == "ingredient"
    ingredient = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "辣椒", "category_id": fallback_category.id, "label_ids": [label["id"]]},
    ).json()

    renamed = client.patch(f"/api/edit/labels/{label['id']}", json={"name_en": "spicy"})
    assert renamed.json()["name_en"] == "spicy"
    assert renamed.json()["ingredient_count"] == 1
    assert renamed.json()["scope"] == "ingredient"

    assert client.delete(f"/api/edit/labels/{label['id']}").status_code == 204
    assert client.get(f"/api/ingredients/{ingredient['id']}").json()["labels"] == []


def test_a_label_counts_the_owners_that_carry_it(client, fallback_category, recipe_statuses):
    """Each library's label is counted in its own field. The unused label is
    the mirror: without it, a count that never looked at the link tables at
    all would also pass."""
    def label(name, scope):
        return client.post("/api/edit/labels", json={"name_cn": name, "scope": scope}).json()

    pantry, side, video = label("常備", "ingredient"), label("下飯", "dish"), label("影片", "note")
    unused = label("閒置", "dish")
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "米", "category_id": fallback_category.id, "label_ids": [pantry["id"]]},
    ).raise_for_status()
    client.post(
        "/api/edit/dishes", json={"name_cn": "白飯", "label_ids": [side["id"]]}
    ).raise_for_status()
    client.post(
        "/api/edit/kitchen-notes", json={"title": "煮飯水量", "label_ids": [video["id"]]}
    ).raise_for_status()

    by_id = {row["id"]: row for row in client.get("/api/labels").json()}

    assert by_id[pantry["id"]]["ingredient_count"] == 1
    assert by_id[side["id"]]["dish_count"] == 1
    assert by_id[video["id"]]["note_count"] == 1
    assert by_id[video["id"]]["usage_count"] == 1
    assert by_id[unused["id"]]["usage_count"] == 0
    assert by_id[unused["id"]]["dish_count"] == 0
