"""An ingredient's homemade version (自製版): the dish that makes it.

Caramel, 雞高湯 and 油蔥酥 can be bought or made. The bought thing is an
ingredient and the made one is a dish, linked by `ingredient.homemade_dish_id`;
the dish lists the ingredients naming it as `bought_as`.

Every refusal here has something real to refuse: the 422 for an id naming no
dish runs with a real dish in the database, so "names no row" cannot pass
because the table is empty; the SET NULL test deletes a dish that really is
linked, and asserts the ingredient survives.
"""

import pytest
from sqlalchemy import text

from app.models import Dish, Ingredient

pytestmark = pytest.mark.usefixtures("recipe_statuses", "source_platforms")


def create_dish(client, **body):
    response = client.post("/api/edit/dishes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def create_ingredient(client, category, **body):
    body.setdefault("category_id", category.id)
    response = client.post("/api/edit/ingredients", json=body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def shallot_crisps(client):
    """油蔥酥 the sauce - what making it yields is also 紅蔥油."""
    return create_dish(client, name_cn="油蔥酥", kind="sauce")


def test_an_ingredient_names_its_homemade_version(client, fallback_category, shallot_crisps):
    bought = create_ingredient(
        client, fallback_category, name_cn="油蔥酥", homemade_dish_id=shallot_crisps["id"]
    )
    assert bought["homemade_dish"] == {
        "id": shallot_crisps["id"],
        "display_name": "油蔥酥",
        "kind": "sauce",
    }
    assert client.get(f"/api/ingredients/{bought['id']}").json()["homemade_dish"] == bought["homemade_dish"]


def test_an_ingredient_without_one_says_null(client, fallback_category):
    plain = create_ingredient(client, fallback_category, name_cn="鹽")
    assert plain["homemade_dish"] is None


def test_one_dish_may_be_the_homemade_version_of_several_ingredients(
    client, fallback_category, shallot_crisps
):
    """Not unique: making 油蔥酥 also yields 紅蔥油. `bought_as` on the dish
    lists both, by display name."""
    oil = create_ingredient(
        client, fallback_category, name_cn="紅蔥油", homemade_dish_id=shallot_crisps["id"]
    )
    crisps = create_ingredient(
        client, fallback_category, name_cn="油蔥酥", homemade_dish_id=shallot_crisps["id"]
    )
    create_ingredient(client, fallback_category, name_cn="紅蔥頭")  # not linked

    dish = client.get(f"/api/dishes/{shallot_crisps['id']}").json()
    assert dish["bought_as"] == [
        {"id": crisps["id"], "display_name": "油蔥酥", "needs_detail": False},
        {"id": oil["id"], "display_name": "紅蔥油", "needs_detail": False},
    ]


def test_a_dish_nothing_names_has_no_bought_as(client, shallot_crisps):
    assert client.get(f"/api/dishes/{shallot_crisps['id']}").json()["bought_as"] == []


def test_any_dish_kind_is_accepted(client, fallback_category):
    """`kind` is how the library files a dish, not a permission - the rule a
    recipe line follows too."""
    stock = create_dish(client, name_cn="雞高湯", kind="dish")
    bought = create_ingredient(client, fallback_category, name_cn="雞高湯", homemade_dish_id=stock["id"])
    assert bought["homemade_dish"]["kind"] == "dish"


def test_a_patch_sets_changes_and_clears_the_link(client, fallback_category, shallot_crisps):
    caramel_sauce = create_dish(client, name_cn="焦糖醬", kind="sauce")
    caramel = create_ingredient(client, fallback_category, name_cn="焦糖")
    url = f"/api/edit/ingredients/{caramel['id']}"

    linked = client.patch(url, json={"homemade_dish_id": caramel_sauce["id"]})
    assert linked.status_code == 200, linked.text
    assert linked.json()["homemade_dish"]["id"] == caramel_sauce["id"]

    # A PATCH not naming it leaves it alone.
    renamed = client.patch(url, json={"name_en": "caramel"}).json()
    assert renamed["homemade_dish"]["id"] == caramel_sauce["id"]

    moved = client.patch(url, json={"homemade_dish_id": shallot_crisps["id"]}).json()
    assert moved["homemade_dish"]["id"] == shallot_crisps["id"]

    cleared = client.patch(url, json={"homemade_dish_id": None}).json()
    assert cleared["homemade_dish"] is None


def test_an_id_naming_no_dish_is_422_and_writes_nothing(client, db, fallback_category, shallot_crisps):
    """A real dish exists, so "no such dish" is about the id and not an empty
    table. The mirror is every other test here linking `shallot_crisps`."""
    missing = shallot_crisps["id"] + 1000
    before = db.query(Ingredient).count()

    created = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "焦糖", "category_id": fallback_category.id, "homemade_dish_id": missing},
    )
    assert created.status_code == 422
    assert created.json()["detail"] == f"No such dish: {missing}."
    assert db.query(Ingredient).count() == before

    caramel = create_ingredient(client, fallback_category, name_cn="焦糖")
    patched = client.patch(f"/api/edit/ingredients/{caramel['id']}", json={"homemade_dish_id": missing})
    assert patched.status_code == 422
    assert patched.json()["detail"] == f"No such dish: {missing}."
    assert client.get(f"/api/ingredients/{caramel['id']}").json()["homemade_dish"] is None


def test_deleting_the_dish_unlinks_the_ingredient_and_keeps_it(client, db, fallback_category, shallot_crisps):
    """SET NULL: the link is a cross-reference, not a usage, so it never
    refuses the delete. The dish has the link and no recipes, and goes; the
    ingredient stays, its link null. The cascade preview says how many
    ingredients lose it."""
    bought = create_ingredient(
        client, fallback_category, name_cn="油蔥酥", homemade_dish_id=shallot_crisps["id"]
    )
    cascade = client.get(f"/api/dishes/{shallot_crisps['id']}/cascade").json()
    assert cascade["bought_as"] == 1

    deleted = client.delete(f"/api/edit/dishes/{shallot_crisps['id']}", params={"aliases": 0})
    assert deleted.status_code == 204, deleted.text

    db.expire_all()
    assert db.get(Dish, shallot_crisps["id"]) is None
    survivor = client.get(f"/api/ingredients/{bought['id']}")
    assert survivor.status_code == 200
    assert survivor.json()["homemade_dish"] is None
    assert db.get(Ingredient, bought["id"]).homemade_dish_id is None


def test_the_database_itself_nulls_the_link(db, fallback_category):
    """The FK is SET NULL in the schema, not something the ORM does on the
    way out: a DELETE in raw SQL leaves the ingredient with a null link."""
    dish = Dish(name_cn="雞高湯")
    db.add(dish)
    db.flush()
    ingredient = Ingredient(name_cn="雞高湯", category_id=fallback_category.id, homemade_dish_id=dish.id)
    db.add(ingredient)
    db.flush()

    db.execute(text("DELETE FROM dish WHERE id = :id"), {"id": dish.id})
    db.expire_all()
    assert db.get(Ingredient, ingredient.id).homemade_dish_id is None


# --- merge --------------------------------------------------------------------


def _merge(client, source, target):
    preview = client.get(f"/api/ingredients/{source}/merge-preview", params={"into": target})
    assert preview.status_code == 200, preview.text
    merged = client.post(
        f"/api/edit/ingredients/{source}/merge",
        json={"into": target, "fingerprint": preview.json()["fingerprint"]},
    )
    assert merged.status_code == 200, merged.text
    return preview.json(), merged.json()


def test_a_merge_target_without_a_homemade_version_takes_the_sources(
    client, fallback_category, shallot_crisps
):
    source = create_ingredient(
        client, fallback_category, name_cn="紅蔥酥", homemade_dish_id=shallot_crisps["id"]
    )
    target = create_ingredient(client, fallback_category, name_cn="油蔥酥")

    preview, merged = _merge(client, source["id"], target["id"])
    assert preview["homemade_dish"] == "moved"
    assert merged["homemade_dish"]["id"] == shallot_crisps["id"]


def test_a_merge_target_keeps_its_own_homemade_version(client, fallback_category, shallot_crisps):
    other = create_dish(client, name_cn="自炸油蔥", kind="sauce")
    source = create_ingredient(client, fallback_category, name_cn="紅蔥酥", homemade_dish_id=other["id"])
    target = create_ingredient(
        client, fallback_category, name_cn="油蔥酥", homemade_dish_id=shallot_crisps["id"]
    )

    preview, merged = _merge(client, source["id"], target["id"])
    assert preview["homemade_dish"] == "dropped"
    assert merged["homemade_dish"]["id"] == shallot_crisps["id"]


def test_a_merge_with_no_homemade_version_on_the_source_says_nothing(client, fallback_category, shallot_crisps):
    source = create_ingredient(client, fallback_category, name_cn="紅蔥酥")
    target = create_ingredient(
        client, fallback_category, name_cn="油蔥酥", homemade_dish_id=shallot_crisps["id"]
    )

    preview, merged = _merge(client, source["id"], target["id"])
    assert preview["homemade_dish"] is None
    assert merged["homemade_dish"]["id"] == shallot_crisps["id"]


def test_a_source_relinked_after_the_preview_is_409(client, fallback_category, shallot_crisps):
    """The link is in the fingerprint: changing what would move after the
    preview was read is the stale-tab 409, as for any other row the plan
    touches."""
    other = create_dish(client, name_cn="自炸油蔥", kind="sauce")
    source = create_ingredient(
        client, fallback_category, name_cn="紅蔥酥", homemade_dish_id=shallot_crisps["id"]
    )
    target = create_ingredient(client, fallback_category, name_cn="油蔥酥")
    shown = client.get(f"/api/ingredients/{source['id']}/merge-preview", params={"into": target["id"]}).json()

    client.patch(f"/api/edit/ingredients/{source['id']}", json={"homemade_dish_id": other["id"]})
    response = client.post(
        f"/api/edit/ingredients/{source['id']}/merge",
        json={"into": target["id"], "fingerprint": shown["fingerprint"]},
    )
    assert response.status_code == 409
