"""A dish can be added, read, edited and deleted over HTTP, and shows its
recipes and what uses it.

Every refusal test sets up the thing it refuses - a recipe of the dish, a line
naming it - and has a mirror that commits.
"""

import pytest

from app.models import Dish, Label, RecipeCourse, Region

pytestmark = pytest.mark.usefixtures("recipe_statuses", "source_platforms")


@pytest.fixture
def vocab(db):
    rows = {
        "course": RecipeCourse(name_cn="主菜"),
        "side": RecipeCourse(name_cn="配菜"),
        "region": Region(name_cn="日式"),
        "label": Label(name_cn="下飯"),
    }
    db.add_all(rows.values())
    db.flush()
    return rows


def create_dish(client, **body):
    body.setdefault("name_cn", "照燒雞腿排")
    response = client.post("/api/edit/dishes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def create_recipe(client, **body):
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def delete_params(client, dish_id):
    return {"aliases": client.get(f"/api/dishes/{dish_id}/cascade").json()["aliases"]}


def test_a_dish_round_trips_through_create_read_update_delete(client, vocab):
    created = create_dish(
        client,
        name_cn="照燒雞腿排",
        name_en="teriyaki chicken",
        kind="dish",
        course_id=vocab["course"].id,
        region_id=vocab["region"].id,
        description="甜鹹",
        aliases=["照燒雞"],
        serves_as_ids=[vocab["side"].id],
        label_ids=[vocab["label"].id],
    )
    read = client.get(f"/api/dishes/{created['id']}").json()
    assert read["display_name"] == "照燒雞腿排"
    assert read["name_en"] == "teriyaki chicken"
    assert read["kind"] == "dish"
    assert read["course"] == {"id": vocab["course"].id, "display_name": "主菜"}
    assert read["region"] == {"id": vocab["region"].id, "display_name": "日式"}
    assert read["description"] == "甜鹹"
    assert read["aliases"] == ["照燒雞"]
    assert [c["display_name"] for c in read["serves_as"]] == ["配菜"]
    assert [x["display_name"] for x in read["labels"]] == ["下飯"]
    assert read["images"] == [] and read["recipes"] == [] and read["used_in"] == []

    updated = client.patch(
        f"/api/edit/dishes/{created['id']}",
        json={"kind": "sauce", "region_id": None, "aliases": [], "label_ids": []},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert (body["kind"], body["region"], body["aliases"], body["labels"]) == ("sauce", None, [], [])
    assert body["description"] == "甜鹹"  # not sent, untouched

    assert client.get(f"/api/dishes/{created['id']}/cascade").json() == {
        "aliases": 0,
        "recipes": 0,
        "used_in": 0,
    }
    deleted = client.delete(f"/api/edit/dishes/{created['id']}", params={"aliases": 0})
    assert deleted.status_code == 204
    assert client.get(f"/api/dishes/{created['id']}").status_code == 404


@pytest.mark.parametrize("kind", ["base", "snack", None])
def test_an_unknown_or_empty_kind_is_refused(client, kind):
    created = create_dish(client)
    assert client.patch(f"/api/edit/dishes/{created['id']}", json={"kind": kind}).status_code == 422
    assert client.post("/api/edit/dishes", json={"name_cn": "x", "kind": kind}).status_code == 422
    # Mirror: both known kinds.
    assert create_dish(client, name_cn="y", kind="sauce")["kind"] == "sauce"


def test_a_dish_needs_a_name_and_keeps_one(client):
    assert client.post("/api/edit/dishes", json={"name_cn": " ", "name_en": ""}).status_code == 422
    created = create_dish(client, name_cn="咖哩", name_en="curry")
    one = client.patch(f"/api/edit/dishes/{created['id']}", json={"name_cn": None})
    assert one.status_code == 200 and one.json()["display_name"] == "curry"
    assert client.patch(f"/api/edit/dishes/{created['id']}", json={"name_en": ""}).status_code == 422


@pytest.mark.parametrize("field", ["course_id", "region_id", "serves_as_ids", "label_ids"])
def test_an_id_that_names_nothing_is_422(client, vocab, field):
    """The vocab fixture makes each table non-empty."""
    value = [999999] if field.endswith("_ids") else 999999
    response = client.post("/api/edit/dishes", json={"name_cn": "x", field: value})
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]


def test_a_dish_lists_its_recipes_and_the_recipes_that_use_it(client, source_platforms, db):
    sauce = create_dish(client, name_cn="照燒醬", kind="sauce")
    chicken = create_dish(client, name_cn="照燒雞腿排")
    youtube = source_platforms["YouTube"].id
    a = create_recipe(
        client,
        dish_id=chicken["id"],
        name="A 版",
        sources=[{"platform_id": youtube, "new_author": {"name_cn": "阿基師"}}],
        lines=[{"sub_dish_id": sauce["id"]}],
    )
    b = create_recipe(client, dish_id=chicken["id"], name="B 版")
    own = create_recipe(client, dish_id=sauce["id"])

    read_chicken = client.get(f"/api/dishes/{chicken['id']}").json()
    assert [r["id"] for r in read_chicken["recipes"]] == [a["id"], b["id"]]
    first = read_chicken["recipes"][0]
    assert first["display_name"] == "A 版"
    assert first["authors"][0]["display_name"] == "阿基師"
    assert first["status"]["display_name"] == "想試"
    assert read_chicken["used_in"] == []

    read_sauce = client.get(f"/api/dishes/{sauce['id']}").json()
    assert [r["id"] for r in read_sauce["recipes"]] == [own["id"]]
    assert read_sauce["used_in"] == [
        {
            "id": a["id"],
            "display_name": "A 版",
            "dish": {"id": chicken["id"], "display_name": "照燒雞腿排", "kind": "dish"},
        }
    ]


def test_a_dish_with_recipes_cannot_be_deleted(client, db):
    """The recipe is the fixture that makes this bite; the mirror deletes the
    recipe and then the dish goes."""
    dish = create_dish(client)
    recipe = create_recipe(client, dish_id=dish["id"], name="A 版")
    assert client.get(f"/api/dishes/{dish['id']}/cascade").json()["recipes"] == 1

    response = client.delete(f"/api/edit/dishes/{dish['id']}", params={"aliases": 0})
    assert response.status_code == 409
    assert response.json()["recipes"] == [{"id": recipe["id"], "display_name": "A 版"}]
    assert response.json()["used_in"] == []
    assert db.get(Dish, dish["id"]) is not None

    params = {"sources": 0, "lines": 0, "steps": 0}
    assert client.delete(f"/api/edit/recipes/{recipe['id']}", params=params).status_code == 204
    assert client.delete(f"/api/edit/dishes/{dish['id']}", params={"aliases": 0}).status_code == 204


def test_a_dish_a_line_names_cannot_be_deleted(client):
    """The line naming it is the fixture; the mirror clears the line."""
    sauce = create_dish(client, name_cn="高湯", kind="sauce")
    ramen = create_recipe(client, new_dish={"name_cn": "拉麵"}, lines=[{"sub_dish_id": sauce["id"]}])
    assert client.get(f"/api/dishes/{sauce['id']}/cascade").json()["used_in"] == 1

    response = client.delete(f"/api/edit/dishes/{sauce['id']}", params={"aliases": 0})
    assert response.status_code == 409
    assert response.json()["recipes"] == []
    assert response.json()["used_in"] == [{"id": ramen["id"], "display_name": "拉麵"}]

    client.patch(f"/api/edit/recipes/{ramen['id']}", json={"lines": [], "line_groups": []})
    assert client.delete(f"/api/edit/dishes/{sauce['id']}", params={"aliases": 0}).status_code == 204


def test_a_delete_with_a_stale_alias_count_is_refused(client):
    dish = create_dish(client, aliases=["a", "b"])
    response = client.delete(f"/api/edit/dishes/{dish['id']}", params={"aliases": 1})
    assert response.status_code == 409
    assert (response.json()["field"], response.json()["actual"]) == ("aliases", 2)
    assert client.delete(f"/api/edit/dishes/{dish['id']}", params=delete_params(client, dish["id"])).status_code == 204


def test_a_missing_dish_in_the_url_is_404(client):
    assert client.get("/api/dishes/999999").status_code == 404
    assert client.get("/api/dishes/999999/cascade").status_code == 404
    assert client.patch("/api/edit/dishes/999999", json={"description": "x"}).status_code == 404
    assert client.delete("/api/edit/dishes/999999", params={"aliases": 0}).status_code == 404
    assert client.put("/api/edit/dishes/999999/images", json=[]).status_code == 404
