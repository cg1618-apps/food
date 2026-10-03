"""What uses an ingredient: its "used in", its list count, the recipe filter,
and the delete refusal that follows from it.

"Used in" counts distinct recipes with a line naming the ingredient or any
ingredient below it, and goes no deeper through sub-dishes than zero. The
fixture `soy` is load-bearing for every test here: a parent with two children,
so that a recipe naming BOTH children is the case that tells "distinct
recipes" from "lines", and a sauce recipe naming one child is the case that
tells depth zero from "any depth".
"""

import pytest
from sqlalchemy import event

from app.models import Ingredient

# Every recipe needs a status; the migration seeds them and create_all does not.
pytestmark = pytest.mark.usefixtures("recipe_statuses")

ZERO = {"aliases": 0, "preservation": 0, "heating": 0, "links": 0}


def create_recipe(client, name, lines):
    body = {"new_dish": {"name_cn": name}, "lines": lines}
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def soy(client, db, fallback_category):
    """醬油 with 生抽 and 老抽 under it, a dish naming both children, a base
    naming 生抽, and a dish that uses only the base."""
    parent = Ingredient(name_cn="醬油", category_id=fallback_category.id)
    db.add(parent)
    db.flush()
    light = Ingredient(name_cn="生抽", category_id=fallback_category.id, parent_id=parent.id)
    dark = Ingredient(name_cn="老抽", category_id=fallback_category.id, parent_id=parent.id)
    db.add_all([light, dark])
    db.flush()
    braise = create_recipe(
        client, "紅燒肉", [{"ingredient_id": light.id}, {"ingredient_id": dark.id}]
    )
    sauce = create_recipe(client, "醬汁", [{"ingredient_id": light.id}])
    noodles = create_recipe(client, "拌麵", [{"sub_dish_id": sauce["dish"]["id"]}])
    return {
        "parent": parent.id,
        "light": light.id,
        "dark": dark.id,
        "braise": braise["id"],
        "sauce": sauce["id"],
        "noodles": noodles["id"],
    }


def used_in(client, ingredient_id):
    response = client.get(f"/api/ingredients/{ingredient_id}")
    assert response.status_code == 200, response.text
    return [r["display_name"] for r in response.json()["used_in"]]


def test_a_recipe_using_two_children_counts_once_on_the_parent(client, soy):
    assert used_in(client, soy["parent"]) == ["紅燒肉", "醬汁"]
    rows = {r["id"]: r for r in client.get("/api/ingredients").json()}
    assert rows[soy["parent"]]["used_in_count"] == 2


def test_a_recipe_whose_sauce_uses_the_ingredient_does_not_count(client, soy):
    # 拌麵 uses the dish 醬汁, whose recipe uses 生抽: depth zero through sub-dishes.
    assert "拌麵" not in used_in(client, soy["light"])
    assert used_in(client, soy["light"]) == ["紅燒肉", "醬汁"]
    assert used_in(client, soy["dark"]) == ["紅燒肉"]


def test_the_recipe_filter_uses_the_same_descendant_query(client, soy):
    response = client.get("/api/recipes", params={"ingredient_id": soy["parent"]})
    assert [r["display_name"] for r in response.json()] == ["紅燒肉", "醬汁"]
    response = client.get("/api/recipes", params={"ingredient_id": soy["dark"]})
    assert [r["display_name"] for r in response.json()] == ["紅燒肉"]


def test_list_counts_match_the_full_rows(client, soy):
    rows = {r["id"]: r["used_in_count"] for r in client.get("/api/ingredients").json()}
    for key in ("parent", "light", "dark"):
        assert rows[soy[key]] == len(used_in(client, soy[key]))


def test_an_unused_ingredient_has_no_used_in(client, ingredient):
    assert used_in(client, ingredient.id) == []
    rows = {r["id"]: r for r in client.get("/api/ingredients").json()}
    assert rows[ingredient.id]["used_in_count"] == 0


def test_parent_and_children_summaries_carry_their_counts(client, soy):
    body = client.get(f"/api/ingredients/{soy['light']}").json()
    assert body["parent"]["used_in_count"] == 2
    parent = client.get(f"/api/ingredients/{soy['parent']}").json()
    assert {c["display_name"]: c["used_in_count"] for c in parent["children"]} == {
        "生抽": 2,
        "老抽": 1,
    }


def test_the_list_counts_in_a_fixed_number_of_queries(client, db, fallback_category, test_engine):
    """`used_in_count` for 1 ingredient or 3 costs the same statements."""
    made = []
    for i in range(3):
        row = Ingredient(name_cn=f"料{i}", category_id=fallback_category.id)
        db.add(row)
        db.flush()
        made.append(row.id)
        create_recipe(client, f"菜{i}", [{"ingredient_id": row.id}])

    statements = []

    def count(*_):
        statements.append(1)

    def run(**params):
        statements.clear()
        event.listen(test_engine, "before_cursor_execute", count)
        try:
            body = client.get("/api/ingredients", params=params).json()
        finally:
            event.remove(test_engine, "before_cursor_execute", count)
        assert all(r["used_in_count"] == 1 for r in body)
        return len(statements), len(body)

    one, one_rows = run(q="料0")
    many, many_rows = run(q="料")
    assert (one_rows, many_rows) == (1, 3)
    assert one == many


def test_an_ingredient_named_by_a_line_cannot_be_deleted(client, soy, db):
    response = client.delete(f"/api/edit/ingredients/{soy['dark']}", params=ZERO)
    assert response.status_code == 409
    assert response.json()["used_in"] == [{"id": soy["braise"], "display_name": "紅燒肉"}]
    assert client.get(f"/api/ingredients/{soy['dark']}").status_code == 200


def test_an_unused_ingredient_deletes(client, soy, fallback_category):
    # The mirror, on the same fixture: a sibling no line names goes.
    other = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "白醬油", "category_id": fallback_category.id, "parent_id": soy["parent"]},
    ).json()
    assert client.delete(f"/api/edit/ingredients/{other['id']}", params=ZERO).status_code == 204


def test_the_cascade_preview_counts_the_recipes_that_block_a_delete(client, soy, ingredient):
    assert client.get(f"/api/ingredients/{soy['light']}/cascade").json()["recipes"] == 2
    assert client.get(f"/api/ingredients/{ingredient.id}/cascade").json()["recipes"] == 0
