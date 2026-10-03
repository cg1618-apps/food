"""Labels can be added, renamed and deleted; deleting one detaches it."""


def test_a_label_round_trips_and_deleting_it_detaches_it(
    client, fallback_category, recipe_statuses
):
    label = client.post("/api/edit/labels", json={"name_cn": "辣"}).json()
    ingredient = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "辣椒", "category_id": fallback_category.id, "label_ids": [label["id"]]},
    ).json()

    renamed = client.patch(f"/api/edit/labels/{label['id']}", json={"name_en": "spicy"})
    assert renamed.json()["name_en"] == "spicy"
    assert renamed.json()["ingredient_count"] == 1

    assert client.delete(f"/api/edit/labels/{label['id']}").status_code == 204
    assert client.get(f"/api/ingredients/{ingredient['id']}").json()["labels"] == []


def test_a_label_counts_every_owner_that_carries_it(client, fallback_category, recipe_statuses):
    """Ingredients, dishes and kitchen notes all carry labels; the count is
    all three. The unused label is the mirror: without it, a count that never
    looked at the link tables at all would also pass."""
    used = client.post("/api/edit/labels", json={"name_cn": "常備"}).json()
    unused = client.post("/api/edit/labels", json={"name_cn": "閒置"}).json()
    ids = [used["id"]]
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "米", "category_id": fallback_category.id, "label_ids": ids},
    ).raise_for_status()
    client.post("/api/edit/dishes", json={"name_cn": "白飯", "label_ids": ids}).raise_for_status()
    client.post(
        "/api/edit/kitchen-notes", json={"title": "煮飯水量", "label_ids": ids}
    ).raise_for_status()

    by_id = {row["id"]: row for row in client.get("/api/labels").json()}

    assert by_id[used["id"]]["ingredient_count"] == 1
    assert by_id[used["id"]]["dish_count"] == 1
    assert by_id[used["id"]]["note_count"] == 1
    assert by_id[used["id"]]["usage_count"] == 3
    assert by_id[unused["id"]]["usage_count"] == 0
    assert by_id[unused["id"]]["dish_count"] == 0
