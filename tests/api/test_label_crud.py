"""Labels can be added, renamed and deleted; deleting one detaches it."""


def test_a_label_round_trips_and_deleting_it_detaches_it(client, fallback_category):
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
