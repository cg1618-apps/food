"""The recipe library: the list, its search and filters, and the creators list.

Every multi-valued filter is tested with two values against three rows, each
row distinct on that filter, so an implementation that ANDs the values or
reads only the first one returns the wrong set rather than an accidentally
right one.
"""

import pytest
from sqlalchemy import event

from app.models import CookingMethod, Equipment, Ingredient, Label, RecipeCourse


def create(client, **body):
    body.setdefault("name_cn", "番茄炒蛋")
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def names(client, **params):
    response = client.get("/api/recipes", params=params)
    assert response.status_code == 200, response.text
    return [row["display_name"] for row in response.json()]


@pytest.fixture
def three(client, db, fallback_category):
    """Three recipes, each with its own value on every filter dimension.

    Recipe i is filed under course i, carries label i, method i, equipment i,
    a source by creator i and a line naming ingredient i, and has status i.
    """
    statuses = ["want_to_try", "can_cook", "regular"]
    made = {"course": [], "label": [], "method": [], "equipment": [], "ingredient": []}
    for i in range(3):
        rows = {
            "course": RecipeCourse(name_cn=f"課{i}"),
            "label": Label(name_cn=f"標{i}"),
            "method": CookingMethod(name_cn=f"法{i}"),
            "equipment": Equipment(name_cn=f"具{i}"),
            "ingredient": Ingredient(name_cn=f"料{i}", category_id=fallback_category.id),
        }
        db.add_all(rows.values())
        db.flush()
        for key, row in rows.items():
            made[key].append(row.id)
    for i in range(3):
        create(
            client,
            name_cn=f"菜{i}",
            status=statuses[i],
            kind="base" if i == 1 else "dish",
            course_id=made["course"][i],
            label_ids=[made["label"][i]],
            method_ids=[made["method"][i]],
            equipment_ids=[made["equipment"][i]],
            sources=[{"platform": "youtube", "creator": f"作者{i}"}],
            lines=[{"ingredient_id": made["ingredient"][i]}],
        )
    made["status"] = statuses
    made["creator"] = ["作者0", "作者1", "作者2"]
    return made


def test_a_list_row_is_a_summary_of_the_recipe(client, db):
    course = RecipeCourse(name_cn="主菜")
    fry, steam = CookingMethod(name_cn="炒"), CookingMethod(name_cn="蒸")
    db.add_all([course, fry, steam])
    db.flush()
    created = create(
        client,
        name_cn="番茄炒蛋",
        name_en="tomato and egg",
        status="can_cook",
        course_id=course.id,
        time="15m",
        method_ids=[fry.id, steam.id],
        sources=[
            {"platform": "youtube", "creator": "阿基師"},
            {"platform": "website", "creator": "詹姆士"},
            {"platform": "shorts", "creator": "阿基師"},
            {"platform": "book", "title": "家常菜"},
        ],
        steps=[{"body": "蛋打散"}],
    )
    [row] = client.get("/api/recipes").json()
    assert row == {
        "id": created["id"],
        "display_name": "番茄炒蛋",
        "name_cn": "番茄炒蛋",
        "name_en": "tomato and egg",
        "name_alt": None,
        "kind": "dish",
        "status": "can_cook",
        "course": {"id": course.id, "display_name": "主菜"},
        "methods": [
            {"id": fry.id, "display_name": "炒"},
            {"id": steam.id, "display_name": "蒸"},
        ],
        # distinct, in source order, and a source with no creator adds nothing
        "creators": ["阿基師", "詹姆士"],
        "time": "15m",
        "written_up": True,
        "cover": None,
    }


def test_the_list_is_sorted_by_display_name(client):
    for name in ["c 菜", "A 菜", "b 菜"]:
        create(client, name_cn=None, name_en=name)
    assert names(client) == ["A 菜", "b 菜", "c 菜"]


def test_search_matches_name_slots_and_aliases_and_returns_a_recipe_once(client):
    create(client, name_cn="紅燒肉", aliases=["東坡肉", "東坡肉塊"])
    create(client, name_cn="清蒸魚", name_en="Steamed fish")
    create(client, name_cn="炒青菜")
    # Two aliases match: a join would return the recipe twice.
    assert names(client, q="東坡") == ["紅燒肉"]
    assert names(client, q="steamed") == ["清蒸魚"]
    assert names(client, q="燒") == ["紅燒肉"]
    assert names(client, q="nothing") == []


@pytest.mark.parametrize(
    "param, key",
    [
        ("course_id", "course"),
        ("status", "status"),
        ("label_id", "label"),
        ("method_id", "method"),
        ("equipment_id", "equipment"),
        ("creator", "creator"),
        ("ingredient_id", "ingredient"),
    ],
)
def test_a_multi_valued_filter_means_any_of(client, three, param, key):
    assert names(client) == ["菜0", "菜1", "菜2"]
    assert names(client, **{param: [three[key][0], three[key][2]]}) == ["菜0", "菜2"]
    assert names(client, **{param: [three[key][1]]}) == ["菜1"]


def test_the_kind_filter_means_any_of(client, three):
    assert names(client, kind="base") == ["菜1"]
    assert names(client, kind="dish") == ["菜0", "菜2"]
    assert names(client, kind=["dish", "base"]) == ["菜0", "菜1", "菜2"]


def test_different_filters_narrow_each_other(client, three):
    assert names(client, course_id=three["course"][0], status="can_cook") == []
    assert names(client, course_id=three["course"][1], status="can_cook") == ["菜1"]


def test_creator_matches_exactly(client, three):
    assert names(client, creator="作者") == []
    assert names(client, creator="作者1") == ["菜1"]


def test_the_written_up_filter(client):
    create(client, name_cn="有步驟", steps=[{"body": "煮"}])
    create(client, name_cn="空白")
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


def test_recipe_creators_are_distinct_sorted_and_skip_missing(client):
    create(
        client,
        name_cn="甲",
        sources=[
            {"platform": "youtube", "creator": "詹姆士"},
            {"platform": "book", "title": "無作者"},
        ],
    )
    create(
        client,
        name_cn="乙",
        sources=[
            {"platform": "youtube", "creator": "阿基師"},
            {"platform": "shorts", "creator": "詹姆士"},
        ],
    )
    response = client.get("/api/recipe-creators")
    assert response.status_code == 200
    assert response.json() == sorted(["詹姆士", "阿基師"])
