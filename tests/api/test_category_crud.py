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
