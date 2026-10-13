"""A name is a category or an ingredient, never both.

Saving an ingredient under a category's name is refused with 409 and a
preview of converting that category; the same save sent with
`convert_category` does it. Saving a category under an ingredient's name is
refused outright. A recipe save never makes a stub under a category's name.

Load-bearing fixture: `chicken_tree` gives the clashing category every kind
of row the conversion touches - a top-level member, a member that is already
a variety of something outside the category, a child category with its own
ingredient, and notes - so the conversion test proves each outcome rather
than passing on an empty category. Every refusal here has a mirror with the
same rows and a different name, so a green refusal is the clash refusing and
not something incidental.

The "nothing changed" tests commit their rows first and roll the session
back after the refused request, as closing the real request session does:
anything the code had committed before refusing would survive that, and
those tests would fail.
"""

import pytest

from app.models import Ingredient, IngredientCategory

pytestmark = pytest.mark.usefixtures("recipe_statuses")

INGREDIENTS = "/api/edit/ingredients"
CATEGORIES = "/api/edit/ingredient-categories"


def _category(db, name_cn, parent=None, **columns):
    row = IngredientCategory(
        name_cn=name_cn, parent_id=parent.id if parent else None, **columns
    )
    db.add(row)
    db.flush()
    return row


def _ingredient(db, name_cn, category, parent=None, **columns):
    row = Ingredient(
        name_cn=name_cn,
        category_id=category.id,
        parent_id=parent.id if parent else None,
        **columns,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def chicken_tree(db, fallback_category):
    """肉類 › 雞肉 (notes, English name Chicken) holding 雞腿 (top-level),
    雞胸肉 (a variety of 禽肉, filed elsewhere), and the child category 土雞
    with 土雞腿 of its own."""
    meat = _category(db, "肉類")
    chicken = _category(db, "雞肉", meat, name_en="Chicken", description="挑選：肉色粉紅")
    free_range = _category(db, "土雞", chicken)
    poultry = _ingredient(db, "禽肉", fallback_category)
    return {
        "meat": meat,
        "chicken": chicken,
        "free_range": free_range,
        "poultry": poultry,
        "leg": _ingredient(db, "雞腿", chicken),
        "breast": _ingredient(db, "雞胸肉", chicken, poultry),
        "free_range_leg": _ingredient(db, "土雞腿", free_range),
    }


def _refused_with_preview(response):
    assert response.status_code == 409, response.text
    preview = response.json()["category_clash"]
    assert preview["fingerprint"]
    return preview


def _convert(preview, target=None):
    return {
        "category_id": preview["category"]["id"],
        "target_category_id": target,
        "fingerprint": preview["fingerprint"],
    }


def _ids(refs):
    return [ref["id"] for ref in refs]


# --- saving an ingredient under a category's name ----------------------------


def test_an_ingredient_named_as_a_category_is_refused_with_a_conversion_preview(
    client, db, chicken_tree
):
    tree = chicken_tree
    body = {"name_cn": "雞肉", "category_id": tree["chicken"].id}
    before = db.query(Ingredient).count()

    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert preview["category"]["id"] == tree["chicken"].id
    assert preview["target"]["id"] == tree["meat"].id
    assert preview["choose_target"] is False
    assert preview["takes_target"] is True
    assert _ids(preview["adopted"]) == [tree["leg"].id]
    assert _ids(preview["varieties"]) == [tree["breast"].id]
    assert preview["kept_top_level"] == []
    assert _ids(preview["child_categories"]) == [tree["free_range"].id]
    assert preview["child_parent"]["id"] == tree["meat"].id
    assert preview["blocked_by"] == []
    assert preview["description"] == "moved"
    assert db.query(Ingredient).count() == before

    # Mirror: the same save under a name no category has goes through.
    body["name_cn"] = "雞翅"
    assert client.post(INGREDIENTS, json=body).status_code == 201


def test_the_english_name_clashes_too_ignoring_case(client, chicken_tree):
    tree = chicken_tree
    body = {"name_cn": "雞", "name_en": " CHICKEN ", "category_id": tree["meat"].id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert preview["category"]["id"] == tree["chicken"].id


def test_an_alias_or_name_alt_matching_a_category_is_not_a_clash(client, chicken_tree):
    """Names only: an alias is something typed to find the row, and
    `name_alt` is a catch-all two ingredients may share."""
    meat = chicken_tree["meat"].id
    assert (
        client.post(
            INGREDIENTS, json={"name_cn": "雞", "name_alt": "雞肉", "category_id": meat}
        ).status_code
        == 201
    )
    assert (
        client.post(
            INGREDIENTS, json={"name_cn": "雞丁", "aliases": ["Chicken"], "category_id": meat}
        ).status_code
        == 201
    )


def test_converting_a_category_files_and_attaches_everything_it_held(
    client, db, chicken_tree
):
    tree = chicken_tree
    body = {"name_cn": "雞肉", "category_id": tree["chicken"].id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))

    saved = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)})
    assert saved.status_code == 201, saved.text
    saved = saved.json()
    db.expire_all()

    # The ingredient was filed in the category that went, so it takes the
    # target - the category's parent - and the category's notes.
    assert saved["category"]["id"] == tree["meat"].id
    assert saved["description"] == "挑選：肉色粉紅"
    # A top-level member becomes its variety; one already a variety keeps
    # its parent. Both are re-filed in the target.
    leg, breast = db.get(Ingredient, tree["leg"].id), db.get(Ingredient, tree["breast"].id)
    assert (leg.parent_id, leg.category_id) == (saved["id"], tree["meat"].id)
    assert (breast.parent_id, breast.category_id) == (tree["poultry"].id, tree["meat"].id)
    # The child category moves up, keeping its own ingredient.
    free_range = db.get(IngredientCategory, tree["free_range"].id)
    assert free_range.parent_id == tree["meat"].id
    assert db.get(Ingredient, tree["free_range_leg"].id).category_id == free_range.id
    # And the category is gone.
    assert db.get(IngredientCategory, tree["chicken"].id) is None
    assert _ids(saved["children"]) == [tree["leg"].id]


def test_the_ingredient_keeps_its_own_category_and_description(client, db, chicken_tree):
    tree = chicken_tree
    body = {"name_cn": "雞肉", "category_id": tree["free_range"].id, "description": "自己的"}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert preview["takes_target"] is False
    assert preview["description"] == "dropped"

    saved = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)}).json()
    assert saved["category"]["id"] == tree["free_range"].id
    assert saved["description"] == "自己的"


def test_an_ancestor_of_the_ingredient_is_not_made_its_variety(client, db, chicken_tree):
    """雞腿 is top-level in 雞肉, and the new 雞肉 is saved as a variety of
    雞腿: adopting 雞腿 would be a cycle, so it stays top-level and is said."""
    tree = chicken_tree
    body = {"name_cn": "雞肉", "category_id": tree["meat"].id, "parent_id": tree["leg"].id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert preview["adopted"] == []
    assert _ids(preview["kept_top_level"]) == [tree["leg"].id]

    saved = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)})
    assert saved.status_code == 201, saved.text
    db.expire_all()
    leg = db.get(Ingredient, tree["leg"].id)
    assert (leg.parent_id, leg.category_id) == (None, tree["meat"].id)
    assert saved.json()["parent"]["id"] == tree["leg"].id


def test_renaming_an_ingredient_to_a_category_name_converts_on_update(
    client, db, chicken_tree
):
    tree = chicken_tree
    own = _ingredient(db, "雞", tree["chicken"])
    db.commit()
    url = f"{INGREDIENTS}/{own.id}"
    preview = _refused_with_preview(client.patch(url, json={"name_cn": "雞肉"}))
    # The ingredient being saved is never its own variety.
    assert own.id not in _ids(preview["adopted"])
    # The refused rename is discarded, as closing the request session does;
    # left in this shared session it would make the resend change no name.
    db.rollback()
    assert db.get(Ingredient, own.id).name_cn == "雞"

    saved = client.patch(url, json={"name_cn": "雞肉", "convert_category": _convert(preview)})
    assert saved.status_code == 200, saved.text
    assert saved.json()["category"]["id"] == tree["meat"].id
    db.expire_all()
    assert db.get(IngredientCategory, tree["chicken"].id) is None
    assert db.get(Ingredient, tree["leg"].id).parent_id == own.id


def test_an_update_not_changing_a_name_is_not_checked(client, db, chicken_tree):
    """A clash older than the rule does not block editing anything else."""
    tree = chicken_tree
    old = _ingredient(db, "雞肉", tree["meat"])
    response = client.patch(f"{INGREDIENTS}/{old.id}", json={"description": "改說明"})
    assert response.status_code == 200, response.text
    # Mirror: changing its name re-checks it, and the clash surfaces.
    _refused_with_preview(client.patch(f"{INGREDIENTS}/{old.id}", json={"name_en": "Hen"}))


def test_a_top_level_category_needs_a_target_outside_itself(client, db, fallback_category):
    seafood = _category(db, "海鮮")
    fish = _category(db, "魚類", seafood)
    shrimp = _ingredient(db, "蝦", seafood)
    body = {"name_cn": "海鮮", "category_id": seafood.id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert preview["choose_target"] is True
    assert preview["target"] is None
    assert preview["child_parent"] is None

    for target in (None, seafood.id, fish.id, 999999):
        refused = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview, target)})
        assert refused.status_code == 422, (target, refused.text)

    saved = client.post(
        INGREDIENTS, json={**body, "convert_category": _convert(preview, fallback_category.id)}
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["category"]["id"] == fallback_category.id
    db.expire_all()
    shrimp = db.get(Ingredient, shrimp.id)
    assert (shrimp.parent_id, shrimp.category_id) == (saved.json()["id"], fallback_category.id)
    assert db.get(IngredientCategory, fish.id).parent_id is None


def test_a_category_with_a_parent_refuses_another_target(client, chicken_tree, fallback_category):
    tree = chicken_tree
    body = {"name_cn": "雞肉", "category_id": tree["meat"].id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    refused = client.post(
        INGREDIENTS, json={**body, "convert_category": _convert(preview, fallback_category.id)}
    )
    assert refused.status_code == 422
    # Mirror: naming its own parent is the same as naming none.
    saved = client.post(
        INGREDIENTS, json={**body, "convert_category": _convert(preview, tree["meat"].id)}
    )
    assert saved.status_code == 201, saved.text


def test_a_child_whose_name_is_taken_one_level_up_blocks_the_conversion(
    client, db, chicken_tree
):
    """肉類 › 雞肉 › 內臟 cannot move up beside 肉類 › 內臟. Refused, and
    nothing changed: no ingredient, every category where it was."""
    tree = chicken_tree
    offal = _category(db, "內臟", tree["chicken"])
    taken = _category(db, "內臟", tree["meat"])
    db.commit()
    body = {"name_cn": "雞肉", "category_id": tree["meat"].id}

    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert [(p["category"]["id"], p["sibling"]["id"]) for p in preview["blocked_by"]] == [
        (offal.id, taken.id)
    ]
    refused = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)})
    assert refused.status_code == 422
    assert "內臟" in refused.json()["detail"]

    db.rollback()
    db.expire_all()
    assert db.query(Ingredient).filter_by(name_cn="雞肉").count() == 0
    assert db.get(IngredientCategory, tree["chicken"].id) is not None
    assert db.get(IngredientCategory, offal.id).parent_id == tree["chicken"].id
    assert db.get(IngredientCategory, tree["free_range"].id).parent_id == tree["chicken"].id
    assert db.get(Ingredient, tree["leg"].id).parent_id is None
    assert db.get(Ingredient, tree["leg"].id).category_id == tree["chicken"].id

    # Mirror: with the name freed, the same conversion runs.
    db.get(IngredientCategory, taken.id).name_cn = "下水"
    db.flush()
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    saved = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)})
    assert saved.status_code == 201, saved.text


def test_a_child_sharing_the_category_name_moves_up_when_english_matched(
    client, db, chicken_tree
):
    """雞肉 (Chicken) › 雞肉: an ingredient named Chicken converts the parent,
    and the child moves up beside the category being removed."""
    tree = chicken_tree
    namesake = _category(db, "雞肉", tree["chicken"])
    body = {"name_cn": "雞", "name_en": "Chicken", "category_id": tree["meat"].id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))
    assert preview["blocked_by"] == []
    saved = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)})
    assert saved.status_code == 201, saved.text
    db.expire_all()
    assert db.get(IngredientCategory, namesake.id).parent_id == tree["meat"].id


def test_a_stale_preview_is_refused_with_the_fresh_one_and_changes_nothing(
    client, db, chicken_tree
):
    tree = chicken_tree
    body = {"name_cn": "雞肉", "category_id": tree["meat"].id}
    preview = _refused_with_preview(client.post(INGREDIENTS, json=body))

    wing = _ingredient(db, "雞翅", tree["chicken"])  # filed after the preview
    db.commit()
    refused = client.post(INGREDIENTS, json={**body, "convert_category": _convert(preview)})
    fresh = _refused_with_preview(refused)
    assert fresh["fingerprint"] != preview["fingerprint"]
    assert wing.id in _ids(fresh["adopted"])

    db.rollback()
    db.expire_all()
    assert db.query(Ingredient).filter_by(name_cn="雞肉").count() == 0
    assert db.get(IngredientCategory, tree["chicken"].id) is not None
    assert db.get(Ingredient, wing.id).parent_id is None

    # Mirror: the fresh fingerprint goes through.
    saved = client.post(INGREDIENTS, json={**body, "convert_category": _convert(fresh)})
    assert saved.status_code == 201, saved.text


def test_the_fallback_category_is_never_converted(client, db, fallback_category):
    for names in ({"name_cn": "未分類"}, {"name_cn": "x", "name_en": "uncategorised"}):
        response = client.post(INGREDIENTS, json={**names, "category_id": fallback_category.id})
        assert response.status_code == 422, response.text
        assert response.json()["category"]["id"] == fallback_category.id
        assert "category_clash" not in response.json()
    assert db.get(IngredientCategory, fallback_category.id) is not None


def test_a_name_two_categories_answer_to_is_refused_naming_both(client, db, chicken_tree):
    tree = chicken_tree
    other = _category(db, "雞", None, name_en="Fowl")
    body = {"name_cn": "雞肉", "name_en": "Fowl", "category_id": tree["meat"].id}
    response = client.post(INGREDIENTS, json=body)
    assert response.status_code == 409
    assert "category_clash" not in response.json()
    assert _ids(response.json()["categories"]) == [tree["chicken"].id, other.id]
    # A conversion of either one does not get past it.
    sent = {"category_id": other.id, "fingerprint": "x"}
    assert client.post(INGREDIENTS, json={**body, "convert_category": sent}).status_code == 409
    # Mirror: one clash alone is the ordinary offer.
    _refused_with_preview(client.post(INGREDIENTS, json={**body, "name_en": None}))


# --- saving a category under an ingredient's name ----------------------------


@pytest.fixture
def soy_sauce(db, fallback_category):
    return _ingredient(db, "醬油", fallback_category, name_en="Soy sauce", name_alt="Shoyu")


@pytest.mark.parametrize("names", [{"name_cn": "醬油"}, {"name_en": "SOY SAUCE"}])
def test_a_new_category_named_as_an_ingredient_is_refused(client, soy_sauce, names):
    response = client.post(CATEGORIES, json=names)
    assert response.status_code == 409, response.text
    assert "已是食材，分類不能同名" in response.json()["detail"]
    assert response.json()["ingredient"] == {"id": soy_sauce.id, "display_name": "醬油"}
    # Mirror: a name no ingredient has.
    assert client.post(CATEGORIES, json={"name_cn": "醬料"}).status_code == 201


def test_name_alt_does_not_block_a_category(client, soy_sauce):
    assert client.post(CATEGORIES, json={"name_en": "Shoyu"}).status_code == 201


def test_renaming_a_category_to_an_ingredient_name_is_refused(client, db, soy_sauce):
    sauces = _category(db, "醬類")
    url = f"{CATEGORIES}/{sauces.id}"
    response = client.patch(url, json={"name_cn": "醬油"})
    assert response.status_code == 409
    assert response.json()["detail"] == "「醬油」已是食材，分類不能同名。"
    # Mirror: another name, and a save not touching the names at all.
    assert client.patch(url, json={"name_cn": "醬汁類"}).status_code == 200


def test_a_category_save_not_changing_its_names_is_not_checked(client, db, soy_sauce):
    """A clash older than the rule does not block dragging the category."""
    old = _category(db, "醬油")
    url = f"{CATEGORIES}/{old.id}"
    assert client.patch(url, json={"sort_order": 5, "name_cn": "醬油"}).status_code == 200
    assert client.patch(url, json={"name_en": "Soy Sauce"}).status_code == 409


# --- a recipe save making a stub ---------------------------------------------


def test_a_recipe_line_typed_as_a_category_name_is_refused(client, db, chicken_tree):
    before = db.query(Ingredient).count()
    body = {"new_dish": {"name_cn": "三杯雞"}, "lines": [{"new_ingredient": {"name_cn": "雞肉"}}]}
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 422, response.text
    assert response.json()["category"]["id"] == chicken_tree["chicken"].id
    assert db.query(Ingredient).count() == before
    # Mirror: a name no category has becomes the stub.
    body["lines"] = [{"new_ingredient": {"name_cn": "雞翅"}}]
    assert client.post("/api/edit/recipes", json=body).status_code == 201
