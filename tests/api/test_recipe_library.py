"""The recipe library: the list, its search and filters.

Every multi-valued filter is tested with two values against three rows, each
row distinct on that filter, so an implementation that ANDs the values or
reads only the first one returns the wrong set rather than an accidentally
right one. The filters that read through the dish - kind, course, region,
label, dish - are `test_dish_library.py`'s.
"""

import pytest
from sqlalchemy import event

from app.models import Author, CookingMethod, Equipment, Ingredient, RecipeCourse

# Every recipe needs a status, and a source a platform; the migration seeds
# both and create_all does not.
pytestmark = pytest.mark.usefixtures("recipe_statuses", "source_platforms")


def create(client, dish="番茄炒蛋", dish_en=None, aliases=(), **body):
    """A recipe of a new dish named `dish` (found again by that name)."""
    if dish_en is not None or aliases:
        made = client.post(
            "/api/edit/dishes",
            json={"name_cn": dish, "name_en": dish_en, "aliases": list(aliases)},
        )
        assert made.status_code == 201, made.text
        body["dish_id"] = made.json()["id"]
    elif "dish_id" not in body:
        body["new_dish"] = {"name_cn": dish}
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def names(client, **params):
    response = client.get("/api/recipes", params=params)
    assert response.status_code == 200, response.text
    return [row["display_name"] for row in response.json()]


@pytest.fixture
def three(client, db, fallback_category, recipe_statuses, source_platforms):
    """Three recipes, each with its own value on every filter dimension of
    its own: recipe i carries method i, equipment i, a source by author i and
    a line naming ingredient i, and has status i. Its dish 菜i is filed under
    course i."""
    statuses = [row.id for row in recipe_statuses.values()]
    youtube = source_platforms["YouTube"].id
    made = {
        "course": [],
        "method": [],
        "equipment": [],
        "ingredient": [],
        "author": [],
    }
    for i in range(3):
        rows = {
            "course": RecipeCourse(name_cn=f"課{i}"),
            "method": CookingMethod(name_cn=f"法{i}"),
            "equipment": Equipment(name_cn=f"具{i}"),
            "ingredient": Ingredient(name_cn=f"料{i}", category_id=fallback_category.id),
            "author": Author(name_cn=f"作者{i}"),
        }
        db.add_all(rows.values())
        db.flush()
        for key, row in rows.items():
            made[key].append(row.id)
    for i in range(3):
        dish = client.post(
            "/api/edit/dishes", json={"name_cn": f"菜{i}", "course_id": made["course"][i]}
        ).json()
        create(
            client,
            dish_id=dish["id"],
            status_id=statuses[i],
            method_ids=[made["method"][i]],
            equipment_ids=[made["equipment"][i]],
            sources=[{"platform_id": youtube, "author_id": made["author"][i]}],
            lines=[{"ingredient_id": made["ingredient"][i]}],
        )
    made["status"] = statuses
    return made


def test_a_list_row_is_a_summary_of_the_recipe(client, db, recipe_statuses, source_platforms):
    can_cook = recipe_statuses["可煮"]
    platform = {name: row.id for name, row in source_platforms.items()}
    course = RecipeCourse(name_cn="主菜")
    fry, steam = CookingMethod(name_cn="炒"), CookingMethod(name_cn="蒸")
    chef, james = Author(name_cn="阿基師"), Author(name_cn="詹姆士")
    db.add_all([course, fry, steam, chef, james])
    db.flush()
    dish = client.post(
        "/api/edit/dishes", json={"name_cn": "番茄炒蛋", "course_id": course.id}
    ).json()
    created = create(
        client,
        dish_id=dish["id"],
        name="阿基師版",
        status_id=can_cook.id,
        time="15m",
        method_ids=[fry.id, steam.id],
        sources=[
            {"platform_id": platform["YouTube"], "author_id": chef.id},
            {"platform_id": platform["網站"], "author_id": james.id},
            {"platform_id": platform["Shorts"], "author_id": chef.id},
            {"platform_id": platform["書"], "title": "家常菜"},
        ],
        steps=[{"body": "蛋打散"}],
    )
    [row] = client.get("/api/recipes").json()
    assert row == {
        "id": created["id"],
        "display_name": "阿基師版",
        "name": "阿基師版",
        "dish": {"id": dish["id"], "display_name": "番茄炒蛋", "kind": "dish"},
        "status": {"id": can_cook.id, "display_name": "可煮"},
        "course": {"id": course.id, "display_name": "主菜"},
        "methods": [
            {"id": fry.id, "display_name": "炒"},
            {"id": steam.id, "display_name": "蒸"},
        ],
        # distinct, in source order, and a source with no author adds nothing
        "authors": [
            {"id": chef.id, "display_name": "阿基師"},
            {"id": james.id, "display_name": "詹姆士"},
        ],
        "time": "15m",
        "written_up": True,
        "cover": None,
    }


def test_the_list_is_sorted_by_display_name(client):
    for name in ["c 菜", "A 菜", "b 菜"]:
        create(client, dish=name)
    create(client, dish="b 菜", name="a 版")  # its own name sorts it
    assert names(client) == ["a 版", "A 菜", "b 菜", "c 菜"]


def test_search_matches_the_dishs_names_and_aliases_and_returns_a_recipe_once(client):
    create(client, dish="紅燒肉", aliases=["東坡肉", "東坡肉塊"])
    create(client, dish="清蒸魚", dish_en="Steamed fish")
    create(client, dish="炒青菜")
    # Two aliases match: a join would return the recipe twice.
    assert names(client, q="東坡") == ["紅燒肉"]
    assert names(client, q="steamed") == ["清蒸魚"]
    assert names(client, q="燒") == ["紅燒肉"]
    assert names(client, q="nothing") == []


def test_search_treats_like_wildcards_as_literal_characters(client):
    # Rows that contain none of the characters are what let "%" and "_"
    # match everything if they reach LIKE unescaped.
    create(client, dish="紅燒肉", aliases=["東坡肉"])
    create(client, dish="100% 果汁", aliases=["a_b"])
    create(client, dish="斜線", dish_en="back\\slash")
    assert names(client, q="%") == ["100% 果汁"]
    assert names(client, q="_") == ["100% 果汁"]
    assert names(client, q="\\") == ["斜線"]
    assert names(client, q="燒") == ["紅燒肉"]  # the mirror: an ordinary term still matches


@pytest.mark.parametrize(
    "param, key",
    [
        ("course_id", "course"),
        ("status_id", "status"),
        ("method_id", "method"),
        ("equipment_id", "equipment"),
        ("author_id", "author"),
        ("ingredient_id", "ingredient"),
    ],
)
def test_a_multi_valued_filter_means_any_of(client, three, param, key):
    assert names(client) == ["菜0", "菜1", "菜2"]
    assert names(client, **{param: [three[key][0], three[key][2]]}) == ["菜0", "菜2"]
    assert names(client, **{param: [three[key][1]]}) == ["菜1"]


def test_different_filters_narrow_each_other(client, three):
    can_cook = three["status"][1]
    assert names(client, course_id=three["course"][0], status_id=can_cook) == []
    assert names(client, course_id=three["course"][1], status_id=can_cook) == ["菜1"]


def test_the_written_up_filter(client):
    create(client, dish="有步驟", steps=[{"body": "煮"}])
    create(client, dish="空白")
    assert names(client, written_up="true") == ["有步驟"]
    assert names(client, written_up="false") == ["空白"]


def test_the_list_issues_the_same_number_of_queries_for_one_recipe_or_many(
    client, three, test_engine
):
    """No N+1: everything a summary reads is loaded per relationship, not per row."""
    statements = []

    def count(*_):
        statements.append(1)

    def run(**params):
        statements.clear()
        event.listen(test_engine, "before_cursor_execute", count)
        try:
            client.get("/api/recipes", params=params)
        finally:
            event.remove(test_engine, "before_cursor_execute", count)
        return len(statements)

    one = run(q="菜0")
    many = run()
    assert one == many


def test_the_creator_filter_and_list_are_gone(client, three):
    """Authors are a vocabulary now: the library filters by `author_id` and
    lists authors at /api/authors."""
    assert client.get("/api/recipe-creators").status_code == 404
    assert names(client, creator="作者1") == ["菜0", "菜1", "菜2"]  # an unknown parameter is ignored
