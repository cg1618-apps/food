"""Categories can be added, renamed, moved and deleted - and the fallback cannot."""


def test_a_category_round_trips_and_can_be_renamed_and_moved(client, fallback_category):
    root = client.post("/api/edit/ingredient-categories", json={"name_cn": "蔬菜"}).json()
    child = client.post(
        "/api/edit/ingredient-categories", json={"name_cn": "葉菜", "parent_id": root["id"]}
    )
    assert child.status_code == 201, child.text
    child = child.json()

    renamed = client.patch(
        f"/api/edit/ingredient-categories/{child['id']}", json={"name_cn": "葉菜類"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "葉菜類"

    moved = client.patch(f"/api/edit/ingredient-categories/{child['id']}", json={"parent_id": None})
    assert moved.json()["parent_id"] is None

    tree = client.get("/api/ingredient-categories").json()
    assert {node["name_cn"] for node in tree} >= {"蔬菜", "葉菜類", "未分類"}

    assert client.delete(f"/api/edit/ingredient-categories/{child['id']}").status_code == 204


def test_a_category_holding_an_ingredient_cannot_be_deleted(client, fallback_category):
    meat = client.post("/api/edit/ingredient-categories", json={"name_cn": "肉類"}).json()
    client.post("/api/edit/ingredients", json={"name_cn": "雞腿", "category_id": meat["id"]})
    assert client.delete(f"/api/edit/ingredient-categories/{meat['id']}").status_code == 409


def test_the_fallback_category_cannot_be_deleted(client, fallback_category):
    response = client.delete(f"/api/edit/ingredient-categories/{fallback_category.id}")
    assert response.status_code == 409


def test_a_category_description_round_trips_with_its_line_breaks(client, fallback_category):
    """A family's own notes - how to pick fresh chicken, how long it keeps -
    live on the category, since 雞肉 is never itself bought or cited. Line
    breaks are kept: the notes are short lines read on a phone."""
    notes = "挑選：肉色粉紅、有彈性\n冷藏 1-2 天"
    created = client.post(
        "/api/edit/ingredient-categories", json={"name_cn": "雞肉", "description": notes}
    )
    assert created.status_code == 201, created.text
    assert created.json()["description"] == notes
    category_id = created.json()["id"]

    tree = client.get("/api/ingredient-categories").json()
    node = next(n for n in tree if n["id"] == category_id)
    assert node["description"] == notes

    changed = client.patch(
        f"/api/edit/ingredient-categories/{category_id}", json={"description": "冷凍 3 個月"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["description"] == "冷凍 3 個月"

    # A PATCH not naming the description leaves it alone.
    renamed = client.patch(f"/api/edit/ingredient-categories/{category_id}", json={"name_en": "Chicken"})
    assert renamed.json()["description"] == "冷凍 3 個月"

    cleared = client.patch(f"/api/edit/ingredient-categories/{category_id}", json={"description": None})
    assert cleared.json()["description"] is None


def test_a_child_category_carries_its_description_in_the_tree(client, fallback_category):
    meat = client.post("/api/edit/ingredient-categories", json={"name_cn": "肉類"}).json()
    chicken = client.post(
        "/api/edit/ingredient-categories",
        json={"name_cn": "雞肉", "parent_id": meat["id"], "description": "冷藏 1-2 天"},
    ).json()

    tree = client.get("/api/ingredient-categories").json()
    root = next(n for n in tree if n["id"] == meat["id"])
    assert root["description"] is None
    assert [(c["id"], c["description"]) for c in root["children"]] == [(chicken["id"], "冷藏 1-2 天")]


def test_a_blank_category_description_is_stored_as_null(client, fallback_category, db):
    from app.models import IngredientCategory

    created = client.post(
        "/api/edit/ingredient-categories", json={"name_cn": "雞肉", "description": "  \n "}
    ).json()
    assert created["description"] is None

    client.patch(f"/api/edit/ingredient-categories/{created['id']}", json={"description": "冷藏"})
    blanked = client.patch(
        f"/api/edit/ingredient-categories/{created['id']}", json={"description": "   "}
    )
    assert blanked.json()["description"] is None
    db.expire_all()
    assert db.get(IngredientCategory, created["id"]).description is None
