"""A recipe can be added, read, edited and deleted over HTTP.

Line resolution - ids, stubs, cycles - is `test_recipe_lines.py`. This file is
the recipe itself: its columns, its lists, the version rule, and delete.
Every refusal test sets up the thing it refuses, and has a mirror that commits.
"""

import pytest

from app.models import (
    Author,
    CookingMethod,
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
        "side": RecipeCourse(name_cn="配菜"),
        "label": Label(name_cn="下飯"),
        "method": CookingMethod(name_cn="炒"),
        "equipment": Equipment(name_cn="炒鍋"),
        "author": Author(name_cn="阿基師"),
    }
    db.add_all(rows.values())
    db.flush()
    return rows


def create(client, **body):
    body.setdefault("name_cn", "番茄炒蛋")
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def delete_params(client, recipe_id):
    counts = client.get(f"/api/recipes/{recipe_id}/cascade").json()
    return {k: counts[k] for k in ("aliases", "sources", "lines", "steps")}


def test_a_recipe_round_trips_through_create_read_update_delete(
    client, vocab, ingredient, recipe_statuses, source_platforms
):
    can_cook = recipe_statuses["可煮"]
    youtube = source_platforms["YouTube"]
    created = create(
        client,
        name_cn="番茄炒蛋",
        name_en="tomato and egg",
        kind="dish",
        status_id=can_cook.id,
        course_id=vocab["course"].id,
        servings="2 人",
        time="15m",
        description="家常",
        storage_notes="當天吃完",
        notes="蛋先炒",
        aliases=["西紅柿炒雞蛋"],
        sources=[
            {"platform_id": youtube.id, "author_id": vocab["author"].id, "url": "https://example.com/v"}
        ],
        lines=[{"ingredient_id": ingredient.id, "amount": "1 小塊", "section": "爆香"}],
        steps=[{"body": "蛋打散"}, {"section": "炒", "body": "下番茄"}],
        serves_as_ids=[vocab["side"].id],
        label_ids=[vocab["label"].id],
        method_ids=[vocab["method"].id],
        equipment_ids=[vocab["equipment"].id],
    )
    read = client.get(f"/api/recipes/{created['id']}").json()
    assert read["display_name"] == "番茄炒蛋"
    assert read["status"] == {"id": can_cook.id, "display_name": "可煮"}
    assert read["course"]["display_name"] == "主菜"
    assert read["aliases"] == ["西紅柿炒雞蛋"]
    assert read["sources"][0]["author"] == {"id": vocab["author"].id, "display_name": "阿基師"}
    assert read["sources"][0]["platform"] == {"id": youtube.id, "display_name": "YouTube"}
    assert read["sources"][0]["sort_order"] == 0
    assert read["lines"][0]["ingredient"]["display_name"] == "生薑"
    assert read["lines"][0]["sub_recipe"] is None
    assert read["lines"][0]["position"] == 0
    assert [s["body"] for s in read["steps"]] == ["蛋打散", "下番茄"]
    assert [s["position"] for s in read["steps"]] == [0, 1]
    assert [c["display_name"] for c in read["serves_as"]] == ["配菜"]
    assert [x["display_name"] for x in read["labels"]] == ["下飯"]
    assert [x["display_name"] for x in read["methods"]] == ["炒"]
    assert [x["display_name"] for x in read["equipment"]] == ["炒鍋"]
    assert read["written_up"] is True
    assert read["images"] == []
    assert read["variant_of"] is None
    assert read["versions"] == []
    assert read["used_in"] == []

    updated = client.patch(
        f"/api/edit/recipes/{created['id']}",
        json={"notes": None, "aliases": [], "label_ids": []},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["notes"] is None
    assert body["aliases"] == []
    assert body["labels"] == []
    assert body["name_en"] == "tomato and egg"  # not sent, untouched

    counts = client.get(f"/api/recipes/{created['id']}/cascade").json()
    assert counts == {"aliases": 0, "sources": 1, "lines": 1, "steps": 2, "used_in": 0}
    deleted = client.delete(
        f"/api/edit/recipes/{created['id']}", params=delete_params(client, created["id"])
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/recipes/{created['id']}").status_code == 404


def test_a_bare_recipe_is_a_dish_nobody_has_tried_and_not_written_up(client):
    created = create(client, name_cn=None, name_en="curry")
    assert created["kind"] == "dish"
    assert created["status"]["display_name"] == "想試"
    assert created["written_up"] is False
    assert created["display_name"] == "curry"


def test_a_step_alone_makes_a_recipe_written_up(client):
    assert create(client, steps=[{"body": "煮"}])["written_up"] is True


def test_patch_leaves_absent_lists_alone_and_replaces_sent_ones(
    client, vocab, ingredient, source_platforms
):
    created = create(
        client,
        aliases=["a"],
        sources=[{"platform_id": source_platforms["書"].id, "title": "家常菜"}],
        lines=[{"ingredient_id": ingredient.id}],
        steps=[{"body": "one"}],
        label_ids=[vocab["label"].id],
        method_ids=[vocab["method"].id],
    )
    body = client.patch(
        f"/api/edit/recipes/{created['id']}",
        json={"steps": [{"body": "two"}, {"body": "three"}], "method_ids": []},
    ).json()
    assert [s["body"] for s in body["steps"]] == ["two", "three"]
    assert body["methods"] == []
    assert body["aliases"] == ["a"]
    assert body["sources"][0]["title"] == "家常菜"
    assert len(body["lines"]) == 1
    assert [x["display_name"] for x in body["labels"]] == ["下飯"]


def test_re_sending_the_same_lists_unchanged_does_not_collide_with_itself(
    client, ingredient, vocab, source_platforms
):
    """The unit of work INSERTs before it DELETEs, so a wholesale replace that
    reuses position 0 collides with uq_recipe_line_position / _step_position
    unless the old rows are cleared and flushed first. Two lines and two steps,
    so positions 0 AND 1 are both reused."""
    payload = {
        "aliases": ["x", "y"],
        "sources": [{"platform_id": source_platforms["網站"].id, "url": "https://example.com"}],
        "lines": [{"ingredient_id": ingredient.id}, {"ingredient_id": ingredient.id, "amount": "2"}],
        "steps": [{"body": "one"}, {"body": "two"}],
        "label_ids": [vocab["label"].id],
        "serves_as_ids": [vocab["side"].id],
    }
    created = create(client, **payload)
    for _ in range(2):
        response = client.patch(f"/api/edit/recipes/{created['id']}", json=payload)
        assert response.status_code == 200, response.text
    body = response.json()
    assert [line["amount"] for line in body["lines"]] == [None, "2"]
    assert [s["body"] for s in body["steps"]] == ["one", "two"]
    assert body["aliases"] == ["x", "y"]


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


@pytest.mark.parametrize(
    "field, value",
    [("kind", "snack"), ("status_id", 999999), ("kind", None), ("status_id", None)],
)
def test_an_unknown_or_empty_kind_or_status_is_refused(client, field, value):
    """The statuses fixture makes the table non-empty, so 999999 is refused
    for naming nothing rather than for there being nothing to name."""
    created = create(client)
    response = client.patch(f"/api/edit/recipes/{created['id']}", json={field: value})
    assert response.status_code == 422
    assert client.post("/api/edit/recipes", json={"name_cn": "x", field: value}).status_code == 422


def test_a_known_kind_and_status_are_accepted(client, recipe_statuses):
    regular = recipe_statuses["常煮"]
    created = create(client, kind="base", status_id=regular.id)
    assert (created["kind"], created["status"]["id"]) == ("base", regular.id)


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
    empty case on purpose; every other save in this file is the mirror."""
    db.query(RecipeStatus).delete()
    db.flush()
    response = client.post("/api/edit/recipes", json={"name_cn": "x"})
    assert response.status_code == 422
    assert "狀態" in response.json()["detail"]
    assert db.query(Recipe).count() == 0


def test_a_recipe_needs_a_name(client):
    response = client.post("/api/edit/recipes", json={"name_cn": "  ", "name_en": ""})
    assert response.status_code == 422


def test_clearing_the_only_name_is_refused_but_clearing_one_of_two_is_not(client):
    created = create(client, name_cn="咖哩", name_en="curry")
    cleared_one = client.patch(f"/api/edit/recipes/{created['id']}", json={"name_cn": None})
    assert cleared_one.status_code == 200
    assert cleared_one.json()["display_name"] == "curry"
    cleared_all = client.patch(f"/api/edit/recipes/{created['id']}", json={"name_en": ""})
    assert cleared_all.status_code == 422
    assert client.get(f"/api/recipes/{created['id']}").json()["name_en"] == "curry"


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
    response = client.post("/api/edit/recipes", json={"name_cn": "x", "sources": [source]})
    assert response.status_code == 422


def test_a_source_may_not_name_an_author_and_a_new_one(client, db, source_platforms):
    author = Author(name_cn="阿基師")
    db.add(author)
    db.flush()
    youtube = source_platforms["YouTube"].id
    both = {"platform_id": youtube, "author_id": author.id, "new_author": {"name_cn": "詹姆士"}}
    response = client.post("/api/edit/recipes", json={"name_cn": "x", "sources": [both]})
    assert response.status_code == 422
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


def test_a_refused_save_creates_no_author(client, db, source_platforms):
    """Validation runs before the first write: a source naming a platform
    that does not exist refuses the save, and the new author on the other
    source must not be left behind."""
    youtube = source_platforms["YouTube"].id
    response = client.post(
        "/api/edit/recipes",
        json={
            "name_cn": "x",
            "sources": [
                {"platform_id": youtube, "new_author": {"name_cn": "阿基師"}},
                {"platform_id": 999999, "title": "y"},
            ],
        },
    )
    assert response.status_code == 422
    assert authors(db) == set()


def test_a_blank_step_is_refused(client):
    response = client.post("/api/edit/recipes", json={"name_cn": "x", "steps": [{"body": " "}]})
    assert response.status_code == 422


def test_an_unknown_field_is_refused(client):
    assert client.post("/api/edit/recipes", json={"name_cn": "x", "id": 5}).status_code == 422


@pytest.mark.parametrize(
    "field", ["serves_as_ids", "label_ids", "method_ids", "equipment_ids", "course_id"]
)
def test_an_id_in_the_body_that_names_nothing_is_422(client, vocab, field):
    """The vocab fixture makes each table non-empty, so the refusal is about
    the id rather than an empty table; the round trip is the mirror."""
    missing = 999999
    value = missing if field == "course_id" else [missing]
    response = client.post("/api/edit/recipes", json={"name_cn": "x", field: value})
    assert response.status_code == 422, response.text
    assert str(missing) in response.json()["detail"]


def test_a_missing_recipe_in_the_url_is_404(client):
    assert client.get("/api/recipes/999999").status_code == 404
    assert client.get("/api/recipes/999999/cascade").status_code == 404
    assert client.patch("/api/edit/recipes/999999", json={"notes": "x"}).status_code == 404
    params = {"aliases": 0, "sources": 0, "lines": 0, "steps": 0}
    assert client.delete("/api/edit/recipes/999999", params=params).status_code == 404


# --- versions ---------------------------------------------------------------


def test_versions_are_listed_from_the_parent_and_from_each_version(client):
    parent = create(client, name_cn="咖哩")
    first = create(client, name_cn="咖哩", name_en="japanese", variant_of_id=parent["id"])
    second = create(client, name_cn="咖哩", name_en="thai", variant_of_id=parent["id"])

    read_parent = client.get(f"/api/recipes/{parent['id']}").json()
    assert sorted(v["id"] for v in read_parent["versions"]) == sorted([first["id"], second["id"]])
    assert read_parent["variant_of"] is None

    read_first = client.get(f"/api/recipes/{first['id']}").json()
    assert read_first["variant_of"]["id"] == parent["id"]
    assert [v["id"] for v in read_first["versions"]] == [second["id"]]


def test_a_version_of_a_missing_recipe_is_refused(client):
    # The foreign key would answer 422 too, so the status alone passes with the
    # service's check deleted: the id in the detail is the service's own. The
    # real recipe is the mirror - a version of it is permitted.
    real = create(client, name_cn="real")
    response = client.post("/api/edit/recipes", json={"name_cn": "x", "variant_of_id": 999999})
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    assert create(client, name_cn="x", variant_of_id=real["id"])["variant_of"]["id"] == real["id"]


def test_a_recipe_cannot_be_a_version_of_itself(client):
    created = create(client)
    response = client.patch(
        f"/api/edit/recipes/{created['id']}", json={"variant_of_id": created["id"]}
    )
    assert response.status_code == 422


def test_a_version_of_a_version_is_refused(client):
    parent = create(client)
    version = create(client, variant_of_id=parent["id"])
    response = client.post(
        "/api/edit/recipes", json={"name_cn": "x", "variant_of_id": version["id"]}
    )
    assert response.status_code == 422


def test_a_recipe_with_versions_cannot_become_a_version(client):
    other = create(client, name_cn="other")
    parent = create(client)
    create(client, variant_of_id=parent["id"])
    response = client.patch(
        f"/api/edit/recipes/{parent['id']}", json={"variant_of_id": other["id"]}
    )
    assert response.status_code == 422
    # Mirror: a recipe with no versions of its own may become one.
    alone = create(client, name_cn="alone")
    moved = client.patch(f"/api/edit/recipes/{alone['id']}", json={"variant_of_id": other["id"]})
    assert moved.status_code == 200, moved.text
    assert moved.json()["variant_of"]["id"] == other["id"]


def test_deleting_a_versions_parent_leaves_the_version(client, db):
    parent = create(client)
    version = create(client, name_en="v2", variant_of_id=parent["id"])
    deleted = client.delete(
        f"/api/edit/recipes/{parent['id']}", params=delete_params(client, parent["id"])
    )
    assert deleted.status_code == 204
    read = client.get(f"/api/recipes/{version['id']}").json()
    assert read["variant_of"] is None
    assert db.get(Recipe, version["id"]).variant_of_id is None


# --- delete -----------------------------------------------------------------


def test_a_recipe_used_as_a_sub_recipe_cannot_be_deleted(client):
    base = create(client, name_cn="高湯", kind="base")
    dish = create(client, name_cn="拉麵", lines=[{"sub_recipe_id": base["id"]}])
    assert client.get(f"/api/recipes/{base['id']}/cascade").json()["used_in"] == 1

    response = client.delete(
        f"/api/edit/recipes/{base['id']}", params=delete_params(client, base["id"])
    )
    assert response.status_code == 409
    assert response.json()["used_in"] == [{"id": dish["id"], "display_name": "拉麵"}]
    assert client.get(f"/api/recipes/{base['id']}").status_code == 200

    # Mirror: once nothing names it, it deletes.
    client.patch(f"/api/edit/recipes/{dish['id']}", json={"lines": []})
    response = client.delete(
        f"/api/edit/recipes/{base['id']}", params=delete_params(client, base["id"])
    )
    assert response.status_code == 204


def test_a_delete_with_a_stale_count_is_refused_naming_the_count(client):
    created = create(client, steps=[{"body": "one"}, {"body": "two"}])
    params = delete_params(client, created["id"])
    params["steps"] = 1
    response = client.delete(f"/api/edit/recipes/{created['id']}", params=params)
    assert response.status_code == 409
    assert response.json()["field"] == "steps"
    assert (response.json()["expected"], response.json()["actual"]) == (1, 2)
