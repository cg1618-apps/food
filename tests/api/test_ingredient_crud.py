"""An ingredient can be added, read, searched, edited and deleted over HTTP."""

from app.models import IngredientCategory, Label


def test_an_ingredient_round_trips_through_create_read_update_delete(client, fallback_category, db):
    meat = IngredientCategory(name_cn="肉類")
    spicy = Label(name_cn="辣")
    db.add_all([meat, spicy])
    db.flush()

    created = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "雞腿",
            "name_en": "chicken leg",
            "category_id": meat.id,
            "description": "帶骨",
            "aliases": ["雞腿肉", "drumstick"],
            "label_ids": [spicy.id],
        },
    )
    assert created.status_code == 201, created.text
    ingredient_id = created.json()["id"]

    read = client.get(f"/api/ingredients/{ingredient_id}").json()
    assert read["category"]["display_name"] == "肉類"
    assert read["aliases"] == ["drumstick", "雞腿肉"]
    assert [label["display_name"] for label in read["labels"]] == ["辣"]

    updated = client.patch(
        f"/api/edit/ingredients/{ingredient_id}",
        json={"description": None, "aliases": ["雞腿肉"], "label_ids": []},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["description"] is None
    assert body["aliases"] == ["雞腿肉"]
    assert body["labels"] == []
    assert body["name_en"] == "chicken leg"  # untouched: not sent

    counts = client.get(f"/api/ingredients/{ingredient_id}/cascade").json()
    deleted = client.delete(
        f"/api/edit/ingredients/{ingredient_id}",
        params={k: counts[k] for k in ("aliases", "preservation", "heating", "links")},
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/ingredients/{ingredient_id}").status_code == 404


def test_search_matches_any_name_slot_and_aliases_once(client, fallback_category):
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "青蔥", "category_id": fallback_category.id, "aliases": ["蔥", "蔥花"]},
    )
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "洋蔥", "name_en": "onion", "category_id": fallback_category.id},
    )
    by_alias = client.get("/api/ingredients", params={"q": "蔥花"}).json()
    assert [row["name_cn"] for row in by_alias] == ["青蔥"]

    by_both = client.get("/api/ingredients", params={"q": "蔥"}).json()
    assert sorted(row["name_cn"] for row in by_both) == ["洋蔥", "青蔥"]

    by_english = client.get("/api/ingredients", params={"q": "ONION"}).json()
    assert [row["name_cn"] for row in by_english] == ["洋蔥"]


def test_search_treats_like_wildcards_as_literal_characters(client, fallback_category):
    # The other rows contain neither character, so an unescaped "%" or "_"
    # would return them too.
    for body in (
        {"name_cn": "青蔥", "aliases": ["蔥花"]},
        {"name_cn": "可可 70%", "aliases": ["dark_chocolate"]},
    ):
        client.post("/api/edit/ingredients", json={**body, "category_id": fallback_category.id})
    for q in ("%", "_"):
        found = client.get("/api/ingredients", params={"q": q}).json()
        assert [row["name_cn"] for row in found] == ["可可 70%"], q
    found = client.get("/api/ingredients", params={"q": "蔥"}).json()
    assert [row["name_cn"] for row in found] == ["青蔥"]


def test_an_ingredient_with_children_cannot_be_deleted(client, fallback_category):
    parent = client.post(
        "/api/edit/ingredients", json={"name_cn": "醬油", "category_id": fallback_category.id}
    ).json()
    client.post(
        "/api/edit/ingredients",
        json={"name_cn": "生抽", "category_id": fallback_category.id, "parent_id": parent["id"]},
    )
    response = client.delete(
        f"/api/edit/ingredients/{parent['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    assert response.status_code == 409
    assert client.get(f"/api/ingredients/{parent['id']}").status_code == 200


def test_reparenting_into_a_descendant_is_refused(client, fallback_category):
    a = client.post("/api/edit/ingredients", json={"name_cn": "甲", "category_id": fallback_category.id}).json()
    b = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "乙", "category_id": fallback_category.id, "parent_id": a["id"]},
    ).json()
    response = client.patch(f"/api/edit/ingredients/{a['id']}", json={"parent_id": b["id"]})
    assert response.status_code == 422


def test_an_unknown_ingredient_is_404_on_read_update_and_delete(client):
    assert client.get("/api/ingredients/999999").status_code == 404
    assert client.patch("/api/edit/ingredients/999999", json={"name_cn": "x"}).status_code == 404
    response = client.delete(
        "/api/edit/ingredients/999999",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    assert response.status_code == 404


def test_resending_existing_aliases_and_storage_notes_on_update_keeps_them(client, fallback_category):
    created = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "薑",
            "category_id": fallback_category.id,
            "aliases": ["ginger", "姜"],
            "preservation": [{"state": "unused", "method": "冷藏", "duration_max_days": 3}],
        },
    ).json()

    updated = client.patch(
        f"/api/edit/ingredients/{created['id']}",
        json={
            "aliases": ["ginger", "生薑"],
            "preservation": [
                {"state": "unused", "method": "冷藏", "duration_min_days": 1, "duration_max_days": 5}
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["aliases"] == ["ginger", "生薑"]
    assert len(body["preservation"]) == 1
    assert body["preservation"][0]["duration_min_days"] == 1
    assert body["preservation"][0]["duration_max_days"] == 5


def test_a_variety_on_its_parent_carries_where_to_get_it(client, fallback_category):
    """The ingredient page lists varieties with where each is bought, so a
    child summary on the full row carries `sourcing_notes`; a list row does
    not."""
    parent = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    child = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "愛文芒果",
            "category_id": fallback_category.id,
            "parent_id": parent["id"],
            "rating": "S",
            "sourcing_notes": "屏東果菜市場",
        },
    ).json()

    body = client.get(f"/api/ingredients/{parent['id']}").json()
    assert [(c["id"], c["rating"], c["sourcing_notes"]) for c in body["children"]] == [
        (child["id"], "S", "屏東果菜市場")
    ]
    assert client.get(f"/api/ingredients/{child['id']}").json()["parent"]["sourcing_notes"] is None
    rows = {r["id"]: r for r in client.get("/api/ingredients").json()}
    assert "sourcing_notes" not in rows[child["id"]]
