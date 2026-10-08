"""The dish library: the list, its search and its filters - and the recipe
library's filters that now read through the dish.

As `test_recipe_library.py`: every multi-valued filter is tested with two
values against three rows, each distinct on that filter, so an implementation
that ANDs the values or reads only the first returns the wrong set.
"""

import pytest

from app.models import Label, RecipeCourse, Region

pytestmark = pytest.mark.usefixtures("recipe_statuses")


def dish_names(client, **params):
    response = client.get("/api/dishes", params=params)
    assert response.status_code == 200, response.text
    return [row["display_name"] for row in response.json()]


def recipe_names(client, **params):
    response = client.get("/api/recipes", params=params)
    assert response.status_code == 200, response.text
    return [row["display_name"] for row in response.json()]


@pytest.fixture
def three(client, db):
    """Three dishes, dish i with course i, region i, label i, and one recipe
    each; dish 1 is a sauce."""
    made = {"course": [], "region": [], "label": [], "dish": []}
    for i in range(3):
        rows = {
            "course": RecipeCourse(name_cn=f"課{i}"),
            "region": Region(name_cn=f"區{i}"),
            "label": Label(name_cn=f"標{i}", scope="dish"),
        }
        db.add_all(rows.values())
        db.flush()
        for key, row in rows.items():
            made[key].append(row.id)
    for i in range(3):
        dish = client.post(
            "/api/edit/dishes",
            json={
                "name_cn": f"菜{i}",
                "kind": "sauce" if i == 1 else "dish",
                "course_id": made["course"][i],
                "region_id": made["region"][i],
                "label_ids": [made["label"][i]],
            },
        ).json()
        made["dish"].append(dish["id"])
        response = client.post(
            "/api/edit/recipes", json={"dish_id": dish["id"], "name": f"做法{i}"}
        )
        assert response.status_code == 201, response.text
    return made


def test_a_list_row_is_a_summary_of_the_dish(client, three):
    row = client.get("/api/dishes").json()[1]
    assert row == {
        "id": three["dish"][1],
        "display_name": "菜1",
        "name_cn": "菜1",
        "name_en": None,
        "name_alt": None,
        "kind": "sauce",
        "course": {"id": three["course"][1], "display_name": "課1"},
        "region": {"id": three["region"][1], "display_name": "區1"},
        "labels": [{"id": three["label"][1], "display_name": "標1"}],
        "recipe_count": 1,
        "cover": None,
    }


def test_search_matches_name_slots_and_aliases_and_returns_a_dish_once(client):
    client.post("/api/edit/dishes", json={"name_cn": "咖哩", "aliases": ["curry", "curry rice"]})
    client.post("/api/edit/dishes", json={"name_cn": "拉麵", "name_alt": "ラーメン"})
    assert dish_names(client, q="CURRY") == ["咖哩"]
    assert dish_names(client, q="ラー") == ["拉麵"]
    assert dish_names(client, q="%") == []


@pytest.mark.parametrize(
    "param, key", [("course_id", "course"), ("region_id", "region"), ("label_id", "label")]
)
def test_a_multi_valued_dish_filter_means_any_of(client, three, param, key):
    assert dish_names(client, **{param: [three[key][0], three[key][2]]}) == ["菜0", "菜2"]


def test_the_kind_filter_means_any_of_and_narrows_others(client, three):
    assert dish_names(client, kind=["sauce"]) == ["菜1"]
    assert dish_names(client, kind=["dish", "sauce"]) == ["菜0", "菜1", "菜2"]
    assert dish_names(client, kind=["dish"], course_id=[three["course"][1]]) == []


@pytest.mark.parametrize(
    "param, key", [("course_id", "course"), ("region_id", "region"), ("label_id", "label")]
)
def test_the_recipe_filters_that_moved_to_the_dish_filter_through_it(client, three, param, key):
    assert recipe_names(client, **{param: [three[key][0], three[key][2]]}) == ["做法0", "做法2"]


def test_the_recipe_list_filters_by_dish_and_by_the_dishs_kind(client, three):
    assert recipe_names(client, dish_id=[three["dish"][1], three["dish"][2]]) == ["做法1", "做法2"]
    assert recipe_names(client, kind=["sauce"]) == ["做法1"]
    assert recipe_names(client, kind=["dish"]) == ["做法0", "做法2"]


def test_a_recipe_search_matches_its_own_name_or_its_dishs(client, three):
    assert recipe_names(client, q="菜1") == ["做法1"]
    assert recipe_names(client, q="做法2") == ["做法2"]


def test_a_recipe_row_carries_its_dish(client, three):
    row = client.get("/api/recipes", params={"dish_id": [three["dish"][0]]}).json()[0]
    assert row["dish"] == {"id": three["dish"][0], "display_name": "菜0", "kind": "dish"}
    assert row["name"] == "做法0"
    assert row["course"] == {"id": three["course"][0], "display_name": "課0"}


def test_recipe_count_counts_every_recipe_of_the_dish(client):
    dish = client.post("/api/edit/dishes", json={"name_cn": "咖哩"}).json()
    for name in ("A", "B"):
        client.post("/api/edit/recipes", json={"dish_id": dish["id"], "name": name})
    client.post("/api/edit/dishes", json={"name_cn": "白飯"})
    counts = {row["display_name"]: row["recipe_count"] for row in client.get("/api/dishes").json()}
    assert counts == {"咖哩": 2, "白飯": 0}
