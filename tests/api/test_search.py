"""The universal search, GET /api/search: one bucket per type, each matched
by the rule its library's own `q` uses and ranked exact, then prefix, then
contains, then by name.

Every bucket test makes the bucket hold a row that does NOT match beside the
one that does, so a bucket answering everything fails rather than passing on
a table with one row in it.
"""

import pytest
from sqlalchemy import event

from app.models import (
    Author,
    Dish,
    DishAlias,
    DishImage,
    HeatingNote,
    Image,
    Ingredient,
    IngredientAlias,
    IngredientCategory,
    KitchenNote,
    Recipe,
    RecipeSource,
    TbdEntry,
    TbdLink,
)

URL = "/api/search"
BUCKETS = ["dishes", "recipes", "ingredients", "notes", "authors", "heating", "tbd"]


def search(client, q, **params):
    response = client.get(URL, params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def names(client, q, bucket, **params):
    return [row["display_name"] for row in search(client, q, **params)["results"][bucket]]


def _dish(db, name_cn, name_en=None, aliases=(), kind="dish"):
    dish = Dish(name_cn=name_cn, name_en=name_en, kind=kind)
    db.add(dish)
    db.flush()
    db.add_all(DishAlias(dish_id=dish.id, value=value) for value in aliases)
    db.flush()
    return dish


def _ingredient(db, category, name_cn, name_en=None, aliases=()):
    row = Ingredient(name_cn=name_cn, name_en=name_en, category_id=category.id)
    db.add(row)
    db.flush()
    db.add_all(IngredientAlias(ingredient_id=row.id, value=value) for value in aliases)
    db.flush()
    return row


def _recipe(db, statuses, dish, name=None):
    row = Recipe(dish_id=dish.id, name=name, status_id=statuses["想試"].id)
    db.add(row)
    db.flush()
    return row


# --- the shape ---------------------------------------------------------------


def test_every_bucket_is_present_and_empty_when_nothing_matches(client):
    body = search(client, "沒有這種東西")
    assert body == {"query": "沒有這種東西", "results": {bucket: [] for bucket in BUCKETS}}


@pytest.mark.parametrize("q", ["", "   "])
def test_a_blank_query_answers_empty_buckets_rather_than_everything(client, db, q):
    """Load-bearing rows: with nothing in the tables, empty buckets would be
    the answer whatever the endpoint did with a blank query."""
    _dish(db, "咖哩")
    db.add(HeatingNote(name="冷凍吐司", sort_order=0))
    db.flush()
    assert search(client, q)["results"] == {bucket: [] for bucket in BUCKETS}
    # The mirror: the same rows are found by a real query.
    assert names(client, "咖", "dishes") == ["咖哩"]


def test_a_missing_query_is_blank_too(client):
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json()["results"] == {bucket: [] for bucket in BUCKETS}


def test_a_wildcard_is_matched_literally(client, db):
    _dish(db, "咖哩")
    assert names(client, "%", "dishes") == []
    assert names(client, "_", "dishes") == []


def test_the_search_is_public_and_read_only(client):
    assert not URL.startswith("/api/edit")
    assert client.post(URL).status_code == 405


# --- each bucket by name and by alias, CN and EN ------------------------------


def test_dishes_match_names_and_aliases(client, db):
    _dish(db, "咖哩", "Curry", aliases=["カレー"], kind="dish")
    _dish(db, "拉麵", aliases=["ramen"])
    assert names(client, "咖哩", "dishes") == ["咖哩"]
    assert names(client, "CURRY", "dishes") == ["咖哩"]
    assert names(client, "カレ", "dishes") == ["咖哩"]
    assert names(client, "Ramen", "dishes") == ["拉麵"]


def test_a_dish_row_carries_its_kind_and_cover(client, db):
    sauce = _dish(db, "油蔥酥", kind="sauce")
    image = Image(
        checksum="a" * 64,
        storage_key="library/a.jpg",
        thumb_key="library/thumbs/a.jpg",
        byte_size=1,
        width=1,
        height=1,
    )
    db.add(image)
    db.flush()
    db.add(DishImage(dish_id=sauce.id, image_id=image.id, position=0, focus="center"))
    db.flush()
    [row] = search(client, "油蔥")["results"]["dishes"]
    assert row == {
        "id": sauce.id,
        "display_name": "油蔥酥",
        "detail": "醬料",
        "cover": {"thumb_url": "/images/library/thumbs/a.jpg", "focus": "center"},
    }


def test_recipes_match_their_own_name_and_their_dishs_names_and_aliases(
    client, db, recipe_statuses
):
    curry = _dish(db, "咖哩", "Curry", aliases=["カレー"])
    other = _dish(db, "拉麵")
    named = _recipe(db, recipe_statuses, curry, name="快速版")
    _recipe(db, recipe_statuses, other)
    assert names(client, "快速", "recipes") == ["快速版"]
    assert names(client, "curry", "recipes") == ["快速版"]
    assert names(client, "カレー", "recipes") == ["快速版"]
    [row] = search(client, "快速")["results"]["recipes"]
    assert row["id"] == named.id
    # A recipe with a name of its own says whose recipe it is.
    assert row["detail"] == "咖哩"
    assert row["cover"] is None


def test_a_recipe_row_names_its_authors(client, db, recipe_statuses, source_platforms):
    dish = _dish(db, "滷肉飯")
    recipe = _recipe(db, recipe_statuses, dish)
    author = Author(name_cn="阿基師")
    db.add(author)
    db.flush()
    db.add(
        RecipeSource(
            recipe_id=recipe.id, platform_id=source_platforms["YouTube"].id, author_id=author.id
        )
    )
    db.flush()
    [row] = search(client, "滷肉")["results"]["recipes"]
    # Named after its dish, so the dish is not repeated; the author is.
    assert row["display_name"] == "滷肉飯"
    assert row["detail"] == "阿基師"


def test_ingredients_match_names_and_aliases(client, db, fallback_category):
    _ingredient(db, fallback_category, "生薑", "ginger", aliases=["老薑"])
    _ingredient(db, fallback_category, "蒜頭", "garlic")
    assert names(client, "生薑", "ingredients") == ["生薑"]
    assert names(client, "GINGER", "ingredients") == ["生薑"]
    assert names(client, "老薑", "ingredients") == ["生薑"]


def test_an_ingredient_row_names_its_category_and_its_stub_state(client, db):
    category = IngredientCategory(name_cn="辛香料", sort_order=0)
    db.add(category)
    db.flush()
    row = Ingredient(name_cn="八角", category_id=category.id, needs_detail=True)
    db.add(row)
    db.flush()
    [hit] = search(client, "八角")["results"]["ingredients"]
    assert hit["detail"] == "辛香料 · 待補"


def test_notes_match_the_title_or_the_body_as_their_library_does(client, db):
    db.add_all(
        [
            KitchenNote(title="切洋蔥", body="不流淚的方法"),
            KitchenNote(title="Knife skills", body="洋蔥 and more"),
            KitchenNote(title="煎牛排"),
        ]
    )
    db.flush()
    # The title match ranks above the body-only one.
    assert names(client, "洋蔥", "notes") == ["切洋蔥", "Knife skills"]
    assert names(client, "KNIFE", "notes") == ["Knife skills"]
    assert search(client, "切洋蔥")["results"]["notes"][0]["detail"] == "參考"


def test_authors_match_either_name(client, db):
    db.add_all([Author(name_cn="詹姆士", name_en="James"), Author(name_cn="阿基師")])
    db.flush()
    assert names(client, "詹姆", "authors") == ["詹姆士"]
    assert names(client, "james", "authors") == ["詹姆士"]
    [row] = search(client, "james")["results"]["authors"]
    assert row["detail"] == "James"


def test_heating_matches_the_name_then_the_body(client, db):
    db.add_all(
        [
            HeatingNote(name="冷凍吐司", body="烤箱 180 度\n5 分鐘", sort_order=0),
            HeatingNote(name="Sausage", body="微波 1 分鐘", sort_order=1),
            HeatingNote(name="便當", body="電鍋", sort_order=2),
        ]
    )
    db.flush()
    assert names(client, "吐司", "heating") == ["冷凍吐司"]
    assert names(client, "sausage", "heating") == ["Sausage"]
    assert names(client, "分鐘", "heating") == ["Sausage", "冷凍吐司"]
    # The secondary line is the body's first line.
    assert search(client, "吐司")["results"]["heating"][0]["detail"] == "烤箱 180 度"
    assert search(client, "吐司")["results"]["heating"][0]["cover"] is None


def test_tbd_matches_the_name_and_link_labels(client, db):
    named = TbdEntry(name="氣炸鍋", sort_order=0)
    unnamed = TbdEntry(name=None, sort_order=1)
    other = TbdEntry(name="Something", sort_order=2)
    db.add_all([named, unnamed, other])
    db.flush()
    db.add_all(
        [
            TbdLink(entry_id=named.id, position=0, url="https://a.example/x"),
            TbdLink(entry_id=unnamed.id, position=0, url="https://b.example/y", label="Air fryer"),
            TbdLink(entry_id=unnamed.id, position=1, url="https://c.example/z"),
            TbdLink(entry_id=other.id, position=0, url="https://air.example/"),
        ]
    )
    db.flush()
    assert names(client, "氣炸", "tbd") == ["氣炸鍋"]
    # An entry with no name is shown by its first link's label, and the URL
    # itself is not matched - "air.example" stays out.
    assert names(client, "AIR", "tbd") == ["Air fryer"]
    rows = {row["id"]: row for row in search(client, "氣炸")["results"]["tbd"]}
    assert rows[named.id]["detail"] == "1 個連結"


def test_an_unnamed_tbd_entry_without_labels_is_shown_by_its_url(client, db):
    entry = TbdEntry(name=None, sort_order=0)
    labelled = TbdEntry(name=None, sort_order=1)
    db.add_all([entry, labelled])
    db.flush()
    db.add_all(
        [
            TbdLink(entry_id=entry.id, position=0, url="https://a.example/x", label=None),
            TbdLink(entry_id=labelled.id, position=0, url="https://b.example/", label="x-ray"),
        ]
    )
    db.flush()
    # Only the labelled one answers "x"; the bare-URL entry is not findable.
    assert names(client, "x", "tbd") == ["x-ray"]


# --- ordering and limits ------------------------------------------------------


def test_a_bucket_ranks_exact_then_prefix_then_contains_then_name(client, db):
    _dish(db, "炒雞")  # contains
    _dish(db, "雞湯")  # prefix
    _dish(db, "白斬雞肉")  # contains
    _dish(db, "雞")  # exact
    _dish(db, "雞肉飯")  # prefix
    assert names(client, "雞", "dishes") == ["雞", "雞湯", "雞肉飯", "炒雞", "白斬雞肉"]


def test_an_alias_ranks_like_a_name(client, db):
    _dish(db, "Fried rice with curry")
    _dish(db, "咖哩", aliases=["curry"])
    assert names(client, "curry", "dishes") == ["咖哩", "Fried rice with curry"]


def test_the_limit_applies_per_bucket_after_ranking(client, db, fallback_category):
    for name in ["雞翅", "雞腿", "烤雞", "雞"]:
        _dish(db, name)
        _ingredient(db, fallback_category, name)
    body = search(client, "雞", limit=2)["results"]
    assert [row["display_name"] for row in body["dishes"]] == ["雞", "雞翅"]
    assert [row["display_name"] for row in body["ingredients"]] == ["雞", "雞翅"]


def test_the_default_limit_is_ten(client, db):
    for i in range(12):
        _dish(db, f"湯{i:02d}")
    assert len(names(client, "湯", "dishes")) == 10


@pytest.mark.parametrize("limit", [0, 51])
def test_a_limit_out_of_range_is_refused(client, limit):
    response = client.get(URL, params={"q": "x", "limit": limit})
    assert response.status_code == 422


def test_the_number_of_queries_does_not_grow_with_the_rows(
    client, db, test_engine, recipe_statuses, fallback_category
):
    """One query per bucket plus a fixed number of eager loads - never one
    per row. Counted at two sizes, which must agree."""

    def count_for(n):
        for i in range(n):
            dish = _dish(db, f"豆{n}{i}", aliases=[f"bean{n}{i}"])
            _recipe(db, recipe_statuses, dish, name=f"豆{n}{i}做法")
            _ingredient(db, fallback_category, f"豆{n}{i}")
        statements = []

        def record(*args):
            statements.append(args[2])

        event.listen(test_engine, "before_cursor_execute", record)
        try:
            search(client, "豆")
        finally:
            event.remove(test_engine, "before_cursor_execute", record)
        return len(statements)

    small = count_for(1)
    large = count_for(4)
    assert small > 0, "nothing was counted, so the comparison proves nothing"
    assert small == large
