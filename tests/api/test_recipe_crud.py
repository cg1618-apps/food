"""A recipe can be added, read, edited and deleted over HTTP.

Line resolution - ids, stubs, cycles - is `test_recipe_lines.py`; the dish
itself is `test_dish_crud.py`. This file is the recipe: its columns, its
dish, its lists, its other versions, and delete. Every refusal test sets up
the thing it refuses, and has a mirror that commits.
"""

import pytest

from app.models import (
    Author,
    CookingMethod,
    Dish,
    Equipment,
    Label,
    Recipe,
    RecipeCourse,
    RecipeStatus,
)

# Every recipe needs a status, and a source a platform; the migration seeds
# both and create_all does not.
pytestmark = pytest.mark.usefixtures("recipe_statuses", "source_platforms")


@pytest.fixture
def vocab(db):
    """One of each vocabulary a recipe names, so the id lists are non-empty."""
    rows = {
        "course": RecipeCourse(name_cn="主菜"),
        "label": Label(name_cn="下飯", scope="dish"),
        "method": CookingMethod(name_cn="炒"),
        "equipment": Equipment(name_cn="炒鍋"),
        "author": Author(name_cn="阿基師"),
    }
    db.add_all(rows.values())
    db.flush()
    return rows


def create(client, **body):
    if "dish_id" not in body:
        body.setdefault("new_dish", {"name_cn": "番茄炒蛋"})
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def delete_params(client, recipe_id):
    counts = client.get(f"/api/recipes/{recipe_id}/cascade").json()
    return {k: counts[k] for k in ("sources", "lines", "steps")}


def test_a_recipe_round_trips_through_create_read_update_delete(
    client, vocab, ingredient, recipe_statuses, source_platforms
):
    can_cook = recipe_statuses["可煮"]
    youtube = source_platforms["YouTube"]
    dish = client.post(
        "/api/edit/dishes",
        json={
            "name_cn": "番茄炒蛋",
            "course_id": vocab["course"].id,
            "label_ids": [vocab["label"].id],
        },
    ).json()
    created = create(
        client,
        dish_id=dish["id"],
        name="阿基師版",
        status_id=can_cook.id,
        servings="2 人",
        time="15m",
        storage_notes="當天吃完",
        notes="蛋先炒",
        sources=[
            {"platform_id": youtube.id, "author_id": vocab["author"].id, "url": "https://example.com/v"}
        ],
        lines=[{"ingredient_id": ingredient.id, "amount": "1 小塊"}],
        steps=[{"body": "蛋打散"}, {"body": "下番茄"}],
        method_ids=[vocab["method"].id],
        equipment_ids=[vocab["equipment"].id],
    )
    read = client.get(f"/api/recipes/{created['id']}").json()
    assert read["display_name"] == "阿基師版"
    assert read["name"] == "阿基師版"
    # The dish as the recipe's page shows it: read-only, from the dish.
    assert read["dish"] == {
        "id": dish["id"],
        "display_name": "番茄炒蛋",
        "kind": "dish",
        "course": {"id": vocab["course"].id, "display_name": "主菜"},
        "region": None,
        "labels": [{"id": vocab["label"].id, "display_name": "下飯"}],
        "serves_as": [],
    }
    assert read["status"] == {"id": can_cook.id, "display_name": "可煮"}
    assert read["sources"][0]["author"] == {"id": vocab["author"].id, "display_name": "阿基師"}
    assert read["sources"][0]["platform"] == {"id": youtube.id, "display_name": "YouTube"}
    assert read["sources"][0]["sort_order"] == 0
    assert read["lines"][0]["ingredient"]["display_name"] == "生薑"
    assert read["lines"][0]["sub_dish"] is None
    assert read["lines"][0]["position"] == 0
    assert [s["body"] for s in read["steps"]] == ["蛋打散", "下番茄"]
    assert [x["display_name"] for x in read["methods"]] == ["炒"]
    assert [x["display_name"] for x in read["equipment"]] == ["炒鍋"]
    assert read["written_up"] is True
    assert read["images"] == []
    assert read["other_recipes"] == []
    for gone in ("name_cn", "kind", "course", "labels", "aliases", "variant_of", "description"):
        assert gone not in read, gone

    updated = client.patch(f"/api/edit/recipes/{created['id']}", json={"notes": None, "name": ""})
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["notes"] is None
    assert body["name"] is None
    assert body["display_name"] == "番茄炒蛋"  # the dish's, once the recipe has none
    assert body["time"] == "15m"  # not sent, untouched

    counts = client.get(f"/api/recipes/{created['id']}/cascade").json()
    assert counts == {"sources": 1, "lines": 1, "steps": 2}
    deleted = client.delete(
        f"/api/edit/recipes/{created['id']}", params=delete_params(client, created["id"])
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/recipes/{created['id']}").status_code == 404


def test_a_bare_recipe_is_untried_not_written_up_and_named_by_its_dish(client):
    created = create(client, new_dish={"name_en": "curry"})
    assert created["dish"]["kind"] == "dish"
    assert created["status"]["display_name"] == "想試"
    assert created["written_up"] is False
    assert created["display_name"] == "curry"
    assert created["name"] is None


def test_a_step_alone_makes_a_recipe_written_up(client):
    assert create(client, steps=[{"body": "煮"}])["written_up"] is True


# --- the dish ---------------------------------------------------------------


def test_a_recipe_needs_a_dish(client):
    for body in ({}, {"name": "x"}, {"new_dish": {"name_cn": " "}}, {"new_dish": {}}):
        assert client.post("/api/edit/recipes", json=body).status_code == 422, body


def test_a_recipe_names_a_dish_id_or_a_new_dish_not_both(client, db):
    dish = Dish(name_cn="咖哩")
    db.add(dish)
    db.flush()
    both = {"dish_id": dish.id, "new_dish": {"name_cn": "拉麵"}}
    assert client.post("/api/edit/recipes", json=both).status_code == 422
    # Mirror: each alone.
    assert create(client, dish_id=dish.id)["dish"]["id"] == dish.id
    assert create(client, new_dish={"name_cn": "拉麵"})["dish"]["display_name"] == "拉麵"


def test_a_missing_dish_is_422_naming_it(client, db):
    db.add(Dish(name_cn="咖哩"))  # the dish table is not empty
    db.flush()
    response = client.post("/api/edit/recipes", json={"dish_id": 999999})
    assert response.status_code == 422
    assert response.json()["detail"] == "No such dish: 999999."


def test_a_new_dish_is_created_with_the_kind_chosen(client, db):
    created = create(client, new_dish={"name_cn": "照燒醬", "kind": "sauce"})
    assert created["dish"]["kind"] == "sauce"
    assert db.query(Dish).filter_by(name_cn="照燒醬").one().kind == "sauce"
    bad = client.post("/api/edit/recipes", json={"new_dish": {"name_cn": "x", "kind": "base"}})
    assert bad.status_code == 422


def test_a_new_dish_whose_name_exists_reuses_that_dish(client, db):
    """The existing dish - answering by an alias, in another case - is the
    fixture: with none, every new_dish creates and a reuse that never happened
    would pass. The existing kind is kept."""
    response = client.post(
        "/api/edit/dishes",
        json={"name_cn": "照燒雞腿排", "aliases": ["Teriyaki Chicken"], "kind": "dish"},
    )
    existing = response.json()
    one = create(client, new_dish={"name_en": "teriyaki chicken", "kind": "sauce"})
    two = create(client, new_dish={"name_cn": "照燒雞腿排"})
    assert one["dish"]["id"] == two["dish"]["id"] == existing["id"]
    assert one["dish"]["kind"] == "dish"
    assert db.query(Dish).count() == 1


def test_a_recipe_can_move_to_another_dish(client, db):
    created = create(client, new_dish={"name_cn": "咖哩"})
    other = Dish(name_cn="咖哩飯")
    db.add(other)
    db.flush()
    moved = client.patch(f"/api/edit/recipes/{created['id']}", json={"dish_id": other.id})
    assert moved.status_code == 200, moved.text
    assert moved.json()["dish"]["id"] == other.id
    # An explicit null cannot leave it without one.
    cleared = client.patch(f"/api/edit/recipes/{created['id']}", json={"dish_id": None})
    assert cleared.status_code == 422


def test_other_recipes_are_the_dishs_other_recipes(client):
    first = create(client, new_dish={"name_cn": "照燒雞腿排"}, name="A 版")
    second = create(client, new_dish={"name_cn": "照燒雞腿排"}, name="B 版")
    third = create(client, new_dish={"name_cn": "照燒雞腿排"})
    unrelated = create(client, new_dish={"name_cn": "白飯"})

    read = client.get(f"/api/recipes/{first['id']}").json()
    assert [r["id"] for r in read["other_recipes"]] == [second["id"], third["id"]]
    assert read["other_recipes"][1]["display_name"] == "照燒雞腿排"
    assert read["other_recipes"][0]["dish"]["display_name"] == "照燒雞腿排"
    assert client.get(f"/api/recipes/{unrelated['id']}").json()["other_recipes"] == []


# --- the rest of the recipe --------------------------------------------------


def test_patch_leaves_absent_lists_alone_and_replaces_sent_ones(
    client, vocab, ingredient, source_platforms
):
    created = create(
        client,
        sources=[{"platform_id": source_platforms["書"].id, "title": "家常菜"}],
        lines=[{"ingredient_id": ingredient.id}],
        steps=[{"body": "one"}],
        method_ids=[vocab["method"].id],
        equipment_ids=[vocab["equipment"].id],
    )
    body = client.patch(
        f"/api/edit/recipes/{created['id']}",
        json={"steps": [{"body": "two"}, {"body": "three"}], "step_groups": [], "method_ids": []},
    ).json()
    assert [s["body"] for s in body["steps"]] == ["two", "three"]
    assert body["methods"] == []
    assert body["sources"][0]["title"] == "家常菜"
    assert len(body["lines"]) == 1
    assert [x["display_name"] for x in body["equipment"]] == ["炒鍋"]


def test_re_sending_the_same_lists_unchanged_does_not_collide_with_itself(
    client, ingredient, vocab, source_platforms
):
    """The unit of work INSERTs before it DELETEs, so a wholesale replace that
    reuses position 0 collides with uq_recipe_line_position / _step_position
    unless the old rows are cleared and flushed first. Two lines and two steps,
    so positions 0 AND 1 are both reused."""
    payload = {
        "sources": [{"platform_id": source_platforms["網站"].id, "url": "https://example.com"}],
        "lines": [{"ingredient_id": ingredient.id}, {"ingredient_id": ingredient.id, "amount": "2"}],
        "line_groups": [],
        "steps": [{"body": "one"}, {"body": "two"}],
        "step_groups": [],
        "method_ids": [vocab["method"].id],
    }
    created = create(client, **payload)
    for _ in range(2):
        response = client.patch(f"/api/edit/recipes/{created['id']}", json=payload)
        assert response.status_code == 200, response.text
    body = response.json()
    assert [line["amount"] for line in body["lines"]] == [None, "2"]
    assert [s["body"] for s in body["steps"]] == ["one", "two"]


def test_a_status_only_patch_changes_the_status_and_nothing_else(
    client, ingredient, recipe_statuses
):
    regular = recipe_statuses["常煮"]
    created = create(client, lines=[{"ingredient_id": ingredient.id}], notes="keep")
    body = client.patch(
        f"/api/edit/recipes/{created['id']}", json={"status_id": regular.id}
    ).json()
    assert body["status"] == {"id": regular.id, "display_name": "常煮"}
    assert body["notes"] == "keep"
    assert len(body["lines"]) == 1


@pytest.mark.parametrize("value", [999999, None])
def test_an_unknown_or_empty_status_is_refused(client, value):
    """The statuses fixture makes the table non-empty, so 999999 is refused
    for naming nothing rather than for there being nothing to name."""
    created = create(client)
    response = client.patch(f"/api/edit/recipes/{created['id']}", json={"status_id": value})
    assert response.status_code == 422
    body = {"new_dish": {"name_cn": "x"}, "status_id": value}
    assert client.post("/api/edit/recipes", json=body).status_code == 422


@pytest.mark.parametrize("field", ["kind", "name_cn", "aliases", "label_ids", "variant_of_id"])
def test_the_fields_that_moved_to_the_dish_are_refused_on_a_recipe(client, field):
    value = {"kind": "dish", "name_cn": "x", "aliases": [], "label_ids": [], "variant_of_id": None}
    body = {"new_dish": {"name_cn": "x"}, field: value[field]}
    assert client.post("/api/edit/recipes", json=body).status_code == 422
    # Mirror: the same body without it saves.
    assert client.post("/api/edit/recipes", json={"new_dish": {"name_cn": "x"}}).status_code == 201


def test_a_known_status_is_accepted(client, recipe_statuses):
    regular = recipe_statuses["常煮"]
    assert create(client, status_id=regular.id)["status"]["id"] == regular.id


def test_a_recipe_saved_without_a_status_gets_the_first_in_sort_order(
    client, db, recipe_statuses
):
    """Reordered so the first is no longer the one with the lowest id: the
    default follows sort_order, not insertion."""
    recipe_statuses["常煮"].sort_order = 1
    db.flush()
    created = create(client)
    assert created["status"]["display_name"] == "常煮"


def test_a_recipe_saved_without_a_status_when_there_are_none_is_422(client, db):
    """The table is emptied first - the fixture filled it - so this is the
    empty case on purpose; every other save in this file is the mirror. The
    refused save leaves no new dish behind either."""
    db.query(RecipeStatus).delete()
    db.flush()
    response = client.post("/api/edit/recipes", json={"new_dish": {"name_cn": "x"}})
    assert response.status_code == 422
    assert "狀態" in response.json()["detail"]
    assert db.query(Recipe).count() == 0
    assert db.query(Dish).count() == 0


@pytest.mark.parametrize(
    "source",
    [
        {"platform_id": "YouTube"},  # none of author, url, title
        {"platform_id": "YouTube", "title": "  "},  # blank is absent
        {"platform_id": "YouTube", "new_author": {"name_cn": " "}},  # a new author needs a name
        {"platform_id": "YouTube", "new_author": {}},
        {"platform_id": 999999, "title": "x"},  # a platform that does not exist
        {"platform_id": None, "title": "x"},  # a source needs a platform
        {"title": "x"},
        {"platform_id": "YouTube", "author_id": 999999},  # an author that does not exist
        {"platform_id": "YouTube", "creator": "x"},  # the old free-text field is gone
        {"platform_id": "網站", "url": "javascript:alert(1)"},
        {"platform_id": "書", "title": "x", "sort_order": 3},  # order is the list's
    ],
)
def test_a_bad_source_is_refused(client, db, source_platforms, source):
    """A platform is written by name here and swapped for its id, so the
    platforms table is non-empty and 999999 is refused for naming nothing. An
    author exists for the same reason."""
    db.add(Author(name_cn="阿基師"))
    db.flush()
    source = dict(source)
    if isinstance(source.get("platform_id"), str):
        source["platform_id"] = source_platforms[source["platform_id"]].id
    body = {"new_dish": {"name_cn": "x"}, "sources": [source]}
    assert client.post("/api/edit/recipes", json=body).status_code == 422


def test_a_source_may_not_name_an_author_and_a_new_one(client, db, source_platforms):
    author = Author(name_cn="阿基師")
    db.add(author)
    db.flush()
    youtube = source_platforms["YouTube"].id
    both = {"platform_id": youtube, "author_id": author.id, "new_author": {"name_cn": "詹姆士"}}
    body = {"new_dish": {"name_cn": "x"}, "sources": [both]}
    assert client.post("/api/edit/recipes", json=body).status_code == 422
    # The mirror: either one alone is fine.
    create(client, sources=[{"platform_id": youtube, "author_id": author.id}])
    create(client, sources=[{"platform_id": youtube, "new_author": {"name_cn": "詹姆士"}}])


def test_a_source_with_only_an_author_is_accepted(client, db, source_platforms):
    author = Author(name_cn="阿基師")
    db.add(author)
    db.flush()
    shorts, book = source_platforms["Shorts"].id, source_platforms["書"].id
    created = create(
        client,
        sources=[{"platform_id": shorts, "author_id": author.id}, {"platform_id": book, "title": "y"}],
    )
    assert [
        (s["platform"]["display_name"], s["author"], s["sort_order"]) for s in created["sources"]
    ] == [
        ("Shorts", {"id": author.id, "display_name": "阿基師"}, 0),
        ("書", None, 1),
    ]


# --- new_author: typed in the source row, made by the save ---------------------


def authors(db):
    return {(a.name_cn, a.name_en) for a in db.query(Author).all()}


def test_a_new_author_is_created_by_the_save(client, db, source_platforms):
    youtube = source_platforms["YouTube"].id
    created = create(
        client,
        sources=[
            {"platform_id": youtube, "new_author": {"name_cn": "阿基師"}},
            {"platform_id": youtube, "new_author": {"name_en": "Babish"}, "url": "https://b.example"},
        ],
    )
    assert authors(db) == {(None, "Babish"), ("阿基師", None)}
    made = {a.display_name: a.id for a in db.query(Author).all()}
    assert [s["author"] for s in created["sources"]] == [
        {"id": made["阿基師"], "display_name": "阿基師"},
        {"id": made["Babish"], "display_name": "Babish"},
    ]


def test_a_new_author_whose_name_exists_reuses_that_author(client, db, source_platforms):
    """The existing author is the fixture: with none, every new_author creates
    and a reuse that never happened would pass. Matched case-insensitively and
    in either slot - a name typed as Chinese can match an English name."""
    james = Author(name_cn="詹姆士", name_en="James")
    db.add(james)
    db.flush()
    youtube = source_platforms["YouTube"].id
    created = create(
        client,
        sources=[
            {"platform_id": youtube, "new_author": {"name_en": "JAMES"}},
            {"platform_id": youtube, "new_author": {"name_cn": "詹姆士"}},
        ],
    )
    assert [s["author"]["id"] for s in created["sources"]] == [james.id, james.id]
    assert authors(db) == {("詹姆士", "James")}


def test_one_new_author_named_by_two_sources_is_one_author(client, db, source_platforms):
    youtube, shorts = source_platforms["YouTube"].id, source_platforms["Shorts"].id
    created = create(
        client,
        sources=[
            {"platform_id": youtube, "new_author": {"name_en": "Babish"}},
            {"platform_id": shorts, "new_author": {"name_en": "babish"}},
        ],
    )
    assert authors(db) == {(None, "Babish")}
    assert created["sources"][0]["author"] == created["sources"][1]["author"]


def test_a_refused_save_creates_no_author_and_no_dish(client, db, source_platforms):
    """Validation runs before the first write: a source naming a platform
    that does not exist refuses the save, and the new author on the other
    source - and the new dish - must not be left behind."""
    youtube = source_platforms["YouTube"].id
    response = client.post(
        "/api/edit/recipes",
        json={
            "new_dish": {"name_cn": "x"},
            "sources": [
                {"platform_id": youtube, "new_author": {"name_cn": "阿基師"}},
                {"platform_id": 999999, "title": "y"},
            ],
        },
    )
    assert response.status_code == 422
    assert authors(db) == set()
    assert db.query(Dish).count() == 0


def test_a_blank_step_is_refused(client):
    body = {"new_dish": {"name_cn": "x"}, "steps": [{"body": " "}]}
    assert client.post("/api/edit/recipes", json=body).status_code == 422


def test_an_unknown_field_is_refused(client):
    body = {"new_dish": {"name_cn": "x"}, "id": 5}
    assert client.post("/api/edit/recipes", json=body).status_code == 422


@pytest.mark.parametrize("field", ["method_ids", "equipment_ids"])
def test_an_id_in_the_body_that_names_nothing_is_422(client, vocab, field):
    """The vocab fixture makes each table non-empty, so the refusal is about
    the id rather than an empty table; the round trip is the mirror."""
    missing = 999999
    body = {"new_dish": {"name_cn": "x"}, field: [missing]}
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 422, response.text
    assert str(missing) in response.json()["detail"]


def test_a_missing_recipe_in_the_url_is_404(client):
    assert client.get("/api/recipes/999999").status_code == 404
    assert client.get("/api/recipes/999999/cascade").status_code == 404
    assert client.patch("/api/edit/recipes/999999", json={"notes": "x"}).status_code == 404
    params = {"sources": 0, "lines": 0, "steps": 0}
    assert client.delete("/api/edit/recipes/999999", params=params).status_code == 404


# --- delete -----------------------------------------------------------------


def test_deleting_the_last_recipe_of_a_dish_keeps_the_dish(client, db):
    created = create(client, new_dish={"name_cn": "咖哩"})
    deleted = client.delete(
        f"/api/edit/recipes/{created['id']}", params=delete_params(client, created["id"])
    )
    assert deleted.status_code == 204
    assert db.get(Dish, created["dish"]["id"]) is not None
    assert client.get(f"/api/dishes/{created['dish']['id']}").json()["recipes"] == []


def test_a_recipe_whose_dish_is_used_elsewhere_still_deletes(client):
    """Lines name the dish, never a recipe of it, so nothing refuses deleting
    a recipe - the dish stays, and so does the line naming it."""
    sauce = create(client, new_dish={"name_cn": "高湯", "kind": "sauce"})
    ramen = create(client, new_dish={"name_cn": "拉麵"}, lines=[{"sub_dish_id": sauce["dish"]["id"]}])
    response = client.delete(
        f"/api/edit/recipes/{sauce['id']}", params=delete_params(client, sauce["id"])
    )
    assert response.status_code == 204
    line = client.get(f"/api/recipes/{ramen['id']}").json()["lines"][0]
    assert line["sub_dish"]["display_name"] == "高湯"


def test_a_delete_with_a_stale_count_is_refused_naming_the_count(client):
    created = create(client, steps=[{"body": "one"}, {"body": "two"}])
    params = delete_params(client, created["id"])
    params["steps"] = 1
    response = client.delete(f"/api/edit/recipes/{created['id']}", params=params)
    assert response.status_code == 409
    assert response.json()["field"] == "steps"
    assert (response.json()["expected"], response.json()["actual"]) == (1, 2)
