"""A recipe line resolves three ways - ingredient, recipe, new ingredient - and
the write path is what keeps that honest.

The load-bearing cases from the spec: an id naming nothing is 422; a payload
claiming a type is refused and cannot change the stored one; cycles through
sub-recipes are refused at any depth; a new name typed twice is one stub; a
typed name matching an existing alias reuses that row.
"""

from app.models import Ingredient, IngredientAlias


def create(client, **body):
    body.setdefault("name_cn", "番茄炒蛋")
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_line_naming_a_missing_ingredient_is_422_naming_the_id(client, ingredient):
    response = client.post(
        "/api/edit/recipes", json={"name_cn": "x", "lines": [{"ingredient_id": 999999}]}
    )
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    # Mirror: the ingredient that exists is accepted.
    line = create(client, lines=[{"ingredient_id": ingredient.id}])["lines"][0]
    assert line["ingredient"] == {"id": ingredient.id, "display_name": "生薑", "needs_detail": False}


def test_a_line_naming_a_missing_recipe_is_422(client):
    create(client)  # the recipe table is not empty
    response = client.post(
        "/api/edit/recipes", json={"name_cn": "x", "lines": [{"sub_recipe_id": 999999}]}
    )
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]


def test_a_line_naming_a_base_recipe_shows_it(client):
    base = create(client, name_cn="高湯", kind="base")
    line = create(client, lines=[{"sub_recipe_id": base["id"], "amount": "1 L"}])["lines"][0]
    assert line["ingredient"] is None
    assert line["sub_recipe"] == {"id": base["id"], "display_name": "高湯", "kind": "base"}
    assert client.get(f"/api/recipes/{base['id']}").json()["used_in"][0]["display_name"] == "番茄炒蛋"


def test_a_line_must_name_exactly_one_target(client, ingredient):
    base = create(client, name_cn="高湯")
    for line in (
        {},
        {"amount": "1"},
        {"ingredient_id": ingredient.id, "sub_recipe_id": base["id"]},
        {"ingredient_id": ingredient.id, "new_ingredient": {"name_cn": "蔥"}},
    ):
        response = client.post("/api/edit/recipes", json={"name_cn": "x", "lines": [line]})
        assert response.status_code == 422, line


def test_a_payload_claiming_a_type_is_refused_and_cannot_change_the_stored_one(
    client, ingredient
):
    created = create(client, lines=[{"ingredient_id": ingredient.id}])
    response = client.patch(
        f"/api/edit/recipes/{created['id']}",
        json={"lines": [{"type": "recipe", "ingredient_id": ingredient.id}]},
    )
    assert response.status_code == 422
    line = client.get(f"/api/recipes/{created['id']}").json()["lines"][0]
    assert line["ingredient"]["id"] == ingredient.id
    assert line["sub_recipe"] is None


def test_a_recipe_cannot_use_itself(client):
    created = create(client)
    response = client.patch(
        f"/api/edit/recipes/{created['id']}", json={"lines": [{"sub_recipe_id": created["id"]}]}
    )
    assert response.status_code == 422


def test_a_two_recipe_cycle_is_refused(client):
    a = create(client, name_cn="A")
    b = create(client, name_cn="B", lines=[{"sub_recipe_id": a["id"]}])
    response = client.patch(
        f"/api/edit/recipes/{a['id']}", json={"lines": [{"sub_recipe_id": b["id"]}]}
    )
    assert response.status_code == 422
    assert client.get(f"/api/recipes/{a['id']}").json()["lines"] == []


def test_a_cycle_through_three_recipes_is_refused(client):
    """Depth beyond one: A uses B, B uses C, so C may not use A."""
    c = create(client, name_cn="C")
    b = create(client, name_cn="B", lines=[{"sub_recipe_id": c["id"]}])
    a = create(client, name_cn="A", lines=[{"sub_recipe_id": b["id"]}])
    response = client.patch(
        f"/api/edit/recipes/{c['id']}", json={"lines": [{"sub_recipe_id": a["id"]}]}
    )
    assert response.status_code == 422


def test_a_chain_without_a_cycle_is_fine(client):
    """Mirror of the cycle tests: A uses B, and B using an unrelated C is
    allowed; so is a diamond, where two lines reach one base by two paths."""
    c = create(client, name_cn="C")
    b = create(client, name_cn="B", lines=[{"sub_recipe_id": c["id"]}])
    a = create(client, name_cn="A", lines=[{"sub_recipe_id": b["id"]}, {"sub_recipe_id": c["id"]}])
    d = create(client, name_cn="D")
    response = client.patch(
        f"/api/edit/recipes/{b['id']}",
        json={"lines": [{"sub_recipe_id": c["id"]}, {"sub_recipe_id": d["id"]}]},
    )
    assert response.status_code == 200, response.text
    assert len(client.get(f"/api/recipes/{a['id']}").json()["lines"]) == 2


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
            {"new_ingredient": {"name_cn": "香茅"}, "section": "醃料"},
            {"new_ingredient": {"name_cn": "香茅", "name_en": "lemongrass"}, "section": "湯"},
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
        json={"name_cn": "x", "lines": [{"new_ingredient": {"name_cn": " "}}]},
    )
    assert response.status_code == 422


def test_a_refused_save_creates_no_stub(client, db, fallback_category):
    """One request is one transaction: a line that fails resolution must not
    leave behind the stub an earlier line in the same save asked for."""
    before = db.query(Ingredient).count()
    response = client.post(
        "/api/edit/recipes",
        json={
            "name_cn": "x",
            "lines": [{"new_ingredient": {"name_cn": "香茅"}}, {"ingredient_id": 999999}],
        },
    )
    assert response.status_code == 422
    assert db.query(Ingredient).count() == before
