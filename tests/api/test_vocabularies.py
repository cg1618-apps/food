"""The nine managed vocabularies share one router factory, so one parametrised
suite covers all nine. The fixtures that make refusals bite are the in-use
rows: a vocabulary value nothing uses deletes freely, and that is the mirror."""

import pytest

RESOURCES = [
    "recipe-courses",
    "regions",
    "recipe-statuses",
    "source-platforms",
    "cooking-methods",
    "equipment",
    "authors",
    "line-groups",
    "step-groups",
]


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


def _dish(db, **kwargs):
    from app.models import Dish

    dish = Dish(name_cn="番茄炒蛋", **kwargs)
    db.add(dish)
    db.flush()
    return dish


def _recipe(db, status, **kwargs):
    from app.models import Recipe

    recipe = Recipe(dish_id=_dish(db).id, status_id=status.id, **kwargs)
    db.add(recipe)
    db.flush()
    return recipe


def test_a_cooking_method_used_only_by_a_recipe_cannot_be_deleted(client, db, recipe_statuses):
    from app.models import CookingMethod

    method = CookingMethod(name_cn="蒸")
    db.add(method)
    db.flush()
    recipe = _recipe(db, recipe_statuses["想試"])
    recipe.methods.append(method)
    db.flush()

    response = client.delete(f"/api/edit/cooking-methods/{method.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_cooking_method_counts_heating_rows_and_recipes_together(
    client, db, fallback_category, recipe_statuses
):
    from app.models import CookingMethod, Ingredient, IngredientHeating

    method = CookingMethod(name_cn="氣炸")
    ingredient = Ingredient(name_cn="香腸", category_id=fallback_category.id)
    db.add_all([method, ingredient])
    db.flush()
    db.add(IngredientHeating(ingredient_id=ingredient.id, method_id=method.id))
    recipe = _recipe(db, recipe_statuses["想試"])
    recipe.methods.append(method)
    db.flush()

    listed = {row["id"]: row for row in client.get("/api/cooking-methods").json()}
    assert listed[method.id]["usage_count"] == 2


def test_equipment_used_by_a_recipe_cannot_be_deleted(client, db, recipe_statuses):
    from app.models import Equipment

    pan = Equipment(name_cn="電鍋")
    db.add(pan)
    db.flush()
    recipe = _recipe(db, recipe_statuses["想試"])
    recipe.equipment.append(pan)
    db.flush()

    response = client.delete(f"/api/edit/equipment/{pan.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_course_a_dish_is_filed_in_cannot_be_deleted(client, db):
    from app.models import RecipeCourse

    course = RecipeCourse(name_cn="主食")
    db.add(course)
    db.flush()
    _dish(db, course_id=course.id)

    response = client.delete(f"/api/edit/recipe-courses/{course.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_region_a_dish_is_from_cannot_be_deleted(client, db):
    """The dish is the fixture that makes the 409 bite; the mirror is the
    parametrised round trip above, where an unused region deletes."""
    from app.models import Region

    region = Region(name_cn="日式")
    db.add(region)
    db.flush()
    _dish(db, region_id=region.id)

    listed = {row["id"]: row for row in client.get("/api/regions").json()}
    assert listed[region.id]["usage_count"] == 1
    response = client.delete(f"/api/edit/regions/{region.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1


def test_a_course_a_dish_only_serves_as_can_be_deleted(client, db):
    """Serves-as links CASCADE and are not a reason to refuse - the mirror of
    the test above, with a link in place so the count had something to miss."""
    from app.models import RecipeCourse

    course = RecipeCourse(name_cn="配菜")
    db.add(course)
    db.flush()
    dish = _dish(db)
    dish.serves_as.append(course)
    db.flush()

    listed = {row["id"]: row for row in client.get("/api/recipe-courses").json()}
    assert listed[course.id]["usage_count"] == 0
    assert client.delete(f"/api/edit/recipe-courses/{course.id}").status_code == 204


def test_a_status_a_recipe_is_in_cannot_be_deleted(client, db, recipe_statuses):
    """The recipe on 可煮 is the fixture that makes the 409 bite; 常煮, which
    nothing uses, is the mirror and deletes."""
    _recipe(db, recipe_statuses["可煮"])

    listed = {row["name_cn"]: row for row in client.get("/api/recipe-statuses").json()}
    assert listed["可煮"]["usage_count"] == 1
    assert listed["常煮"]["usage_count"] == 0

    response = client.delete(f"/api/edit/recipe-statuses/{recipe_statuses['可煮'].id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1
    unused = client.delete(f"/api/edit/recipe-statuses/{recipe_statuses['常煮'].id}")
    assert unused.status_code == 204


def test_a_platform_a_source_names_cannot_be_deleted(
    client, db, recipe_statuses, source_platforms
):
    """Two sources on one recipe count twice: the count is the rows that would
    stop the delete, as a method counts heating rows and recipes together."""
    from app.models import RecipeSource

    recipe = _recipe(db, recipe_statuses["想試"])
    book = source_platforms["書"]
    db.add_all(
        [
            RecipeSource(recipe_id=recipe.id, platform_id=book.id, title="家常菜", sort_order=0),
            RecipeSource(recipe_id=recipe.id, platform_id=book.id, title="快手菜", sort_order=1),
        ]
    )
    db.flush()

    listed = {row["name_cn"]: row for row in client.get("/api/source-platforms").json()}
    assert listed["書"]["usage_count"] == 2
    assert listed["其他"]["usage_count"] == 0

    response = client.delete(f"/api/edit/source-platforms/{book.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 2
    other = source_platforms["其他"]
    assert client.delete(f"/api/edit/source-platforms/{other.id}").status_code == 204


def test_an_author_a_source_names_cannot_be_deleted(
    client, db, recipe_statuses, source_platforms
):
    """Two sources by one author count twice, as a platform's do. The sources
    are the fixture that makes the 409 bite; the unused author is the mirror
    and deletes."""
    from app.models import Author, RecipeSource

    used, unused = Author(name_cn="阿基師"), Author(name_en="James")
    db.add_all([used, unused])
    db.flush()
    recipe = _recipe(db, recipe_statuses["想試"])
    youtube = source_platforms["YouTube"]
    db.add_all(
        [
            RecipeSource(recipe_id=recipe.id, platform_id=youtube.id, author_id=used.id),
            RecipeSource(
                recipe_id=recipe.id, platform_id=youtube.id, author_id=used.id, sort_order=1
            ),
        ]
    )
    db.flush()

    listed = {row["display_name"]: row for row in client.get("/api/authors").json()}
    assert listed["阿基師"]["usage_count"] == 2
    assert listed["James"]["usage_count"] == 0

    response = client.delete(f"/api/edit/authors/{used.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 2
    assert client.delete(f"/api/edit/authors/{unused.id}").status_code == 204


def test_authors_list_by_name(client):
    """Authors are never hand-ordered: every one is created with sort_order 0,
    so the factory's (sort_order, name) order is name order."""
    for name in ["詹姆士", "Babish", "阿基師", "adam"]:
        assert client.post("/api/edit/authors", json={"name_cn": name}).status_code == 201
    names = [row["display_name"] for row in client.get("/api/authors").json()]
    assert names == sorted(["詹姆士", "Babish", "阿基師", "adam"], key=str.casefold)


def test_statuses_and_platforms_list_in_sort_order(client, recipe_statuses, source_platforms):
    statuses = [row["display_name"] for row in client.get("/api/recipe-statuses").json()]
    platforms = [row["display_name"] for row in client.get("/api/source-platforms").json()]
    assert statuses == ["想試", "可煮", "常煮"]
    assert platforms == ["YouTube", "Shorts", "網站", "書", "其他"]


def test_the_recipe_fixed_vocabularies_are_served_with_labels(client):
    """Statuses and platforms are managed vocabularies now, not closed lists;
    the kind is the dish's."""
    body = client.get("/api/vocabularies/fixed").json()
    assert body["dish_kinds"] == [
        {"value": "dish", "label": "料理"},
        {"value": "sauce", "label": "醬料"},
    ]
    assert "recipe_kinds" not in body
    assert "recipe_statuses" not in body
    assert "source_platforms" not in body
