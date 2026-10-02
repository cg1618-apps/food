"""The three managed vocabularies share one router factory, so one parametrised
suite covers all three. The fixtures that make refusals bite are the in-use
rows: a vocabulary value nothing uses deletes freely, and that is the mirror."""

import pytest

RESOURCES = ["recipe-courses", "cooking-methods", "equipment"]


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_vocabulary_value_can_be_created_listed_renamed_and_deleted(client, resource):
    created = client.post(f"/api/edit/{resource}", json={"name_cn": "測試", "sort_order": 5})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["display_name"] == "測試"
    assert body["usage_count"] == 0

    listed = client.get(f"/api/{resource}").json()
    assert [row["name_cn"] for row in listed] == ["測試"]

    renamed = client.patch(
        f"/api/edit/{resource}/{body['id']}", json={"name_cn": "改名", "name_en": "renamed"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "改名"

    deleted = client.delete(f"/api/edit/{resource}/{body['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/{resource}").json() == []


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_vocabulary_value_needs_a_name(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "  "}).status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_two_values_may_not_share_an_english_name_case_insensitively(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_en": "Pan"}).status_code == 201
    assert client.post(f"/api/edit/{resource}", json={"name_en": "pan"}).status_code == 409


@pytest.mark.parametrize("resource", RESOURCES)
def test_any_number_of_values_may_leave_the_english_name_empty(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "甲"}).status_code == 201
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "乙"}).status_code == 201


@pytest.mark.parametrize("resource", RESOURCES)
def test_renaming_away_every_name_is_refused(client, resource):
    row = client.post(f"/api/edit/{resource}", json={"name_cn": "甲"}).json()
    response = client.patch(f"/api/edit/{resource}/{row['id']}", json={"name_cn": None})
    assert response.status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_an_unknown_id_is_404(client, resource):
    assert client.patch(f"/api/edit/{resource}/999999", json={"name_cn": "x"}).status_code == 404
    assert client.delete(f"/api/edit/{resource}/999999").status_code == 404


def test_values_list_in_sort_order_then_name(client):
    client.post("/api/edit/equipment", json={"name_cn": "乙", "sort_order": 1})
    client.post("/api/edit/equipment", json={"name_cn": "甲", "sort_order": 2})
    client.post("/api/edit/equipment", json={"name_cn": "丙", "sort_order": 1})
    names = [row["name_cn"] for row in client.get("/api/equipment").json()]
    assert names == ["丙", "乙", "甲"]


# --- in use by a recipe ----------------------------------------------------
#
# The fixtures below are the load-bearing ones: each puts a recipe on the value
# so the 409 has something to refuse. The mirror is the first test in this file,
# where an unused value deletes.


def _recipe(db, **kwargs):
    from app.models import Recipe

    recipe = Recipe(name_cn="番茄炒蛋", **kwargs)
    db.add(recipe)
    db.flush()
    return recipe


def test_a_cooking_method_used_only_by_a_recipe_cannot_be_deleted(client, db):
    from app.models import CookingMethod

    method = CookingMethod(name_cn="蒸")
    db.add(method)
    db.flush()
    recipe = _recipe(db)
    recipe.methods.append(method)
    db.flush()

    response = client.delete(f"/api/edit/cooking-methods/{method.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_cooking_method_counts_heating_rows_and_recipes_together(
    client, db, fallback_category
):
    from app.models import CookingMethod, Ingredient, IngredientHeating

    method = CookingMethod(name_cn="氣炸")
    ingredient = Ingredient(name_cn="香腸", category_id=fallback_category.id)
    db.add_all([method, ingredient])
    db.flush()
    db.add(IngredientHeating(ingredient_id=ingredient.id, method_id=method.id))
    recipe = _recipe(db)
    recipe.methods.append(method)
    db.flush()

    listed = {row["id"]: row for row in client.get("/api/cooking-methods").json()}
    assert listed[method.id]["usage_count"] == 2


def test_equipment_used_by_a_recipe_cannot_be_deleted(client, db):
    from app.models import Equipment

    pan = Equipment(name_cn="電鍋")
    db.add(pan)
    db.flush()
    recipe = _recipe(db)
    recipe.equipment.append(pan)
    db.flush()

    response = client.delete(f"/api/edit/equipment/{pan.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_course_a_recipe_is_filed_in_cannot_be_deleted(client, db):
    from app.models import RecipeCourse

    course = RecipeCourse(name_cn="主食")
    db.add(course)
    db.flush()
    _recipe(db, course_id=course.id)

    response = client.delete(f"/api/edit/recipe-courses/{course.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_course_a_recipe_only_serves_as_can_be_deleted(client, db):
    """Serves-as links CASCADE and are not a reason to refuse - the mirror of
    the test above, with a link in place so the count had something to miss."""
    from app.models import RecipeCourse

    course = RecipeCourse(name_cn="配菜")
    db.add(course)
    db.flush()
    recipe = _recipe(db)
    recipe.serves_as.append(course)
    db.flush()

    listed = {row["id"]: row for row in client.get("/api/recipe-courses").json()}
    assert listed[course.id]["usage_count"] == 0
    assert client.delete(f"/api/edit/recipe-courses/{course.id}").status_code == 204


def test_the_recipe_fixed_vocabularies_are_served_with_labels(client):
    body = client.get("/api/vocabularies/fixed").json()
    assert [e["value"] for e in body["recipe_kinds"]] == ["dish", "base"]
    assert {"value": "want_to_try", "label": "想試"} in body["recipe_statuses"]
    assert [e["value"] for e in body["source_platforms"]] == [
        "youtube",
        "shorts",
        "website",
        "book",
        "other",
    ]
