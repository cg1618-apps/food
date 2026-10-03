"""A recipe line resolves four ways - ingredient, dish, new ingredient, new
dish - and the write path is what keeps that honest.

The load-bearing cases: an id naming nothing is 422; a payload claiming a type
is refused and cannot change the stored one; a recipe may not use its own
dish; cycles through dishes are refused at any depth; a new name typed twice
is one row; a typed name matching an existing alias reuses that row.
"""

import pytest

from app.models import Dish, Ingredient, IngredientAlias

# Every recipe needs a status; the migration seeds them and create_all does not.
pytestmark = pytest.mark.usefixtures("recipe_statuses")


def create(client, dish="番茄炒蛋", **body):
    """A recipe of the dish named `dish`, found or made by the save."""
    if "dish_id" not in body:
        body["new_dish"] = {"name_cn": dish}
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def set_lines(client, recipe, lines):
    return client.patch(
        f"/api/edit/recipes/{recipe['id']}", json={"line_groups": [], "lines": lines}
    )


def test_a_line_naming_a_missing_ingredient_is_422_naming_the_id(client, ingredient):
    response = client.post(
        "/api/edit/recipes",
        json={"new_dish": {"name_cn": "x"}, "lines": [{"ingredient_id": 999999}]},
    )
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    # Mirror: the ingredient that exists is accepted.
    line = create(client, lines=[{"ingredient_id": ingredient.id}])["lines"][0]
    assert line["ingredient"] == {"id": ingredient.id, "display_name": "生薑", "needs_detail": False}


def test_a_line_naming_a_missing_dish_is_422(client):
    create(client)  # the dish table is not empty
    response = client.post(
        "/api/edit/recipes", json={"new_dish": {"name_cn": "x"}, "lines": [{"sub_dish_id": 999999}]}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "No such dish: 999999."


def test_a_line_naming_a_sauce_shows_it_and_the_sauce_is_used_in_the_recipe(client):
    stock = create(client, dish="高湯")["dish"]
    recipe = create(client, lines=[{"sub_dish_id": stock["id"], "amount": "1 L"}])
    line = recipe["lines"][0]
    assert line["ingredient"] is None
    assert line["sub_dish"] == {"id": stock["id"], "display_name": "高湯", "kind": "dish"}
    used_in = client.get(f"/api/dishes/{stock['id']}").json()["used_in"]
    assert [r["id"] for r in used_in] == [recipe["id"]]


def test_id_zero_on_a_line_is_422_naming_it(client, ingredient):
    # Zero is falsy: a truthiness filter skipped it and left the foreign key
    # to refuse it without the id. The real ingredient is the mirror.
    create(client, dish="real", lines=[{"ingredient_id": ingredient.id}])
    for line, what in (({"ingredient_id": 0}, "ingredient"), ({"sub_dish_id": 0}, "dish")):
        body = {"new_dish": {"name_cn": "x"}, "lines": [line]}
        response = client.post("/api/edit/recipes", json=body)
        assert response.status_code == 422, line
        assert response.json()["detail"] == f"No such {what}: 0.", line


def test_a_line_must_name_exactly_one_target(client, ingredient):
    stock = create(client, dish="高湯")["dish"]
    for line in (
        {},
        {"amount": "1"},
        {"ingredient_id": ingredient.id, "sub_dish_id": stock["id"]},
        {"ingredient_id": ingredient.id, "new_ingredient": {"name_cn": "蔥"}},
        {"sub_dish_id": stock["id"], "new_dish": {"name_cn": "醬"}},
        {"sub_recipe_id": 1},  # the old target is gone
    ):
        body = {"new_dish": {"name_cn": "x"}, "lines": [line]}
        assert client.post("/api/edit/recipes", json=body).status_code == 422, line


def test_a_payload_claiming_a_type_is_refused_and_cannot_change_the_stored_one(
    client, ingredient
):
    created = create(client, lines=[{"ingredient_id": ingredient.id}])
    response = set_lines(client, created, [{"type": "dish", "ingredient_id": ingredient.id}])
    assert response.status_code == 422
    line = client.get(f"/api/recipes/{created['id']}").json()["lines"][0]
    assert line["ingredient"]["id"] == ingredient.id
    assert line["sub_dish"] is None


def test_a_recipe_cannot_use_its_own_dish(client):
    """Another recipe of the dish exists, so "its own dish" is not the only
    dish there is; the mirror names a different one."""
    created = create(client, dish="咖哩")
    create(client, dish="咖哩", name="另一份")
    response = set_lines(client, created, [{"sub_dish_id": created["dish"]["id"]}])
    assert response.status_code == 422
    assert "own dish" in response.json()["detail"]
    other = create(client, dish="白飯")["dish"]
    assert set_lines(client, created, [{"sub_dish_id": other["id"]}]).status_code == 200


def test_a_new_dish_on_a_line_with_the_recipes_own_new_name_is_refused(client, db):
    response = client.post(
        "/api/edit/recipes",
        json={"new_dish": {"name_cn": "咖哩"}, "lines": [{"new_dish": {"name_cn": "咖哩"}}]},
    )
    assert response.status_code == 422
    assert db.query(Dish).count() == 0


def test_a_two_dish_cycle_is_refused(client):
    a = create(client, dish="A")
    b = create(client, dish="B", lines=[{"sub_dish_id": a["dish"]["id"]}])
    response = set_lines(client, a, [{"sub_dish_id": b["dish"]["id"]}])
    assert response.status_code == 422
    assert client.get(f"/api/recipes/{a['id']}").json()["lines"] == []


def test_a_cycle_through_another_recipe_of_the_dish_is_refused(client):
    """The edge is the DISH's: B is used by a recipe of A, so no recipe of B -
    not just the one that was there - may use A, and no other recipe of A
    makes a difference."""
    a1 = create(client, dish="A")
    b = create(client, dish="B")
    create(client, dish="A", name="A2", lines=[{"sub_dish_id": b["dish"]["id"]}])
    response = set_lines(client, b, [{"sub_dish_id": a1["dish"]["id"]}])
    assert response.status_code == 422


def test_a_cycle_through_three_dishes_is_refused(client):
    """Depth beyond one: A uses B, B uses C, so C may not use A."""
    c = create(client, dish="C")
    b = create(client, dish="B", lines=[{"sub_dish_id": c["dish"]["id"]}])
    create(client, dish="A", lines=[{"sub_dish_id": b["dish"]["id"]}])
    a_id = client.get("/api/dishes", params={"q": "A"}).json()[0]["id"]
    assert set_lines(client, c, [{"sub_dish_id": a_id}]).status_code == 422


def test_a_chain_without_a_cycle_is_fine(client):
    """Mirror of the cycle tests: A uses B, and B using an unrelated C is
    allowed; so is a diamond, where two lines reach one dish by two paths."""
    c = create(client, dish="C")["dish"]
    b = create(client, dish="B", lines=[{"sub_dish_id": c["id"]}])
    a = create(client, dish="A", lines=[{"sub_dish_id": b["dish"]["id"]}, {"sub_dish_id": c["id"]}])
    d = create(client, dish="D")["dish"]
    response = set_lines(client, b, [{"sub_dish_id": c["id"]}, {"sub_dish_id": d["id"]}])
    assert response.status_code == 200, response.text
    assert len(client.get(f"/api/recipes/{a['id']}").json()["lines"]) == 2


def test_moving_a_recipe_to_a_dish_its_lines_name_is_refused(client):
    sauce = create(client, dish="醬")["dish"]
    recipe = create(client, dish="麵", lines=[{"sub_dish_id": sauce["id"]}])
    response = client.patch(f"/api/edit/recipes/{recipe['id']}", json={"dish_id": sauce["id"]})
    assert response.status_code == 422
    # Mirror: moving to an unrelated dish keeps the line.
    other = create(client, dish="飯")["dish"]
    moved = client.patch(f"/api/edit/recipes/{recipe['id']}", json={"dish_id": other["id"]})
    assert moved.status_code == 200, moved.text
    assert moved.json()["lines"][0]["sub_dish"]["id"] == sauce["id"]


def test_a_new_dish_on_a_line_is_a_sauce_unless_told(client, db):
    lines = create(
        client,
        lines=[{"new_dish": {"name_cn": "照燒醬"}}, {"new_dish": {"name_cn": "白飯", "kind": "dish"}}],
    )["lines"]
    assert [line["sub_dish"]["kind"] for line in lines] == ["sauce", "dish"]
    assert {d.name_cn for d in db.query(Dish).all()} == {"番茄炒蛋", "照燒醬", "白飯"}


def test_a_new_dish_typed_twice_or_matching_an_alias_is_one_dish(client, db):
    existing = client.post(
        "/api/edit/dishes", json={"name_cn": "柴魚高湯", "aliases": ["dashi"], "kind": "sauce"}
    ).json()
    before = db.query(Dish).count()
    lines = create(
        client,
        lines=[
            {"new_dish": {"name_en": "DASHI"}},
            {"new_dish": {"name_cn": "昆布醬"}},
            {"new_dish": {"name_cn": "昆布醬"}},
        ],
    )["lines"]
    assert lines[0]["sub_dish"]["id"] == existing["id"]
    assert lines[1]["sub_dish"]["id"] == lines[2]["sub_dish"]["id"]
    # The recipe's own new dish and one new sub-dish.
    assert db.query(Dish).count() == before + 2


def test_a_new_ingredient_becomes_a_stub_in_the_fallback_category(
    client, db, fallback_category
):
    line = create(client, lines=[{"new_ingredient": {"name_cn": "香茅"}}])["lines"][0]
    assert line["ingredient"]["display_name"] == "香茅"
    assert line["ingredient"]["needs_detail"] is True
    stub = db.get(Ingredient, line["ingredient"]["id"])
    assert stub.category_id == fallback_category.id


def test_a_new_name_typed_twice_in_one_save_is_one_stub(client, db, fallback_category):
    before = db.query(Ingredient).count()
    lines = create(
        client,
        lines=[
            {"new_ingredient": {"name_cn": "香茅"}},
            {"new_ingredient": {"name_cn": "香茅", "name_en": "lemongrass"}},
            {"new_ingredient": {"name_en": "LEMONGRASS"}},
        ],
    )["lines"]
    assert db.query(Ingredient).count() == before + 1
    assert len({line["ingredient"]["id"] for line in lines}) == 1


def test_a_typed_name_matching_an_existing_alias_reuses_that_row(client, db, ingredient):
    db.add(IngredientAlias(ingredient_id=ingredient.id, value="老薑"))
    db.flush()
    before = db.query(Ingredient).count()
    lines = create(
        client,
        lines=[
            {"new_ingredient": {"name_cn": "老薑"}},
            {"new_ingredient": {"name_en": "GINGER"}},  # a name slot, any case
        ],
    )["lines"]
    assert db.query(Ingredient).count() == before
    assert [line["ingredient"]["id"] for line in lines] == [ingredient.id, ingredient.id]
    assert lines[0]["ingredient"]["needs_detail"] is False


def test_a_new_ingredient_needs_a_name(client, fallback_category):
    response = client.post(
        "/api/edit/recipes",
        json={"new_dish": {"name_cn": "x"}, "lines": [{"new_ingredient": {"name_cn": " "}}]},
    )
    assert response.status_code == 422


def test_a_refused_save_creates_no_stub_and_no_dish(client, db, fallback_category):
    """One request is one transaction: a line that fails resolution must not
    leave behind the stub or the dishes an earlier line asked for."""
    before = db.query(Ingredient).count()
    response = client.post(
        "/api/edit/recipes",
        json={
            "new_dish": {"name_cn": "x"},
            "lines": [
                {"new_ingredient": {"name_cn": "香茅"}},
                {"new_dish": {"name_cn": "醬"}},
                {"ingredient_id": 999999},
            ],
        },
    )
    assert response.status_code == 422
    assert db.query(Ingredient).count() == before
    assert db.query(Dish).count() == 0
