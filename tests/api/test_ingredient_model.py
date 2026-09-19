"""The constraints on the ingredient family, and that they actually refuse.

Every test here is a refusal test, which is the kind that passes for the wrong
reason. A constraint over a set is vacuously satisfied by an empty set, and a
uniqueness constraint over nullable columns is vacuously satisfied by nulls -
so each test below makes the thing it is refusing actually possible, and the
mirror case asserts the permitted version still commits. A green that only
proves "nothing was there to refuse" is worth nothing.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Ingredient,
    IngredientAlias,
    IngredientCategory,
    IngredientPreservation,
    Label,
)


def make(db, category, **kwargs):
    kwargs.setdefault("name_cn", "生薑")
    ingredient = Ingredient(category_id=category.id, **kwargs)
    db.add(ingredient)
    return ingredient


def test_an_ingredient_with_no_name_at_all_is_refused(db, fallback_category):
    make(db, fallback_category, name_cn=None, name_en=None, name_alt=None)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_ingredient_has_a_name" in str(excinfo.value)


def test_an_ingredient_named_only_in_the_alt_slot_is_allowed(db, fallback_category):
    """The mirror. Without it the test above could pass because the row was
    rejected for some other reason entirely."""
    make(db, fallback_category, name_cn=None, name_en=None, name_alt="shoga")
    db.flush()


def test_two_ingredients_may_not_share_a_name_differing_only_in_case(db, fallback_category):
    make(db, fallback_category, name_cn=None, name_en="Ginger")
    db.flush()
    make(db, fallback_category, name_cn=None, name_en="ginger")
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_ingredient_name_en" in str(excinfo.value)


def test_duplicate_names_are_refused_when_the_other_slots_are_null(db, fallback_category):
    """A real collision still collides when the other slots are empty.

    Both rows leave name_en and name_alt null and share name_cn, which is the
    ordinary case: most ingredients here carry a Chinese name and nothing else.
    The mirror is the next test, which proves the empty slots themselves do not
    collide.
    """
    make(db, fallback_category, name_cn="生薑")
    db.flush()
    make(db, fallback_category, name_cn="生薑")
    with pytest.raises(IntegrityError):
        db.flush()


def test_any_number_of_ingredients_may_leave_a_name_slot_empty(db, fallback_category):
    """The unique name indexes use Postgres's DEFAULT null handling, and this
    is what that buys.

    Two rows with no name_cn and distinct name_en values, and two more with no
    name_en. All four must commit: an empty slot is the normal state, not a
    value to be unique on.

    The tempting mistake is `postgresql_nulls_not_distinct=True`, because a
    multi-column name constraint genuinely needs it - media's `uq_person_name`
    is inert without it, and shipped duplicates three times. On a SINGLE-column
    index it does the opposite: NULL equals NULL, and food may then hold
    exactly one ingredient with no English name. This test is what refuses that
    change, and it fails loudly rather than subtly.
    """
    make(db, fallback_category, name_cn=None, name_en="ginger")
    make(db, fallback_category, name_cn=None, name_en="galangal")
    make(db, fallback_category, name_cn="醬油", name_en=None)
    make(db, fallback_category, name_cn="米酒", name_en=None)
    db.flush()
    assert db.query(Ingredient).count() == 4


def test_name_alt_is_not_unique(db, fallback_category):
    """The mirror of the two above: name_alt is a catch-all, not a key, and two
    ingredients may legitimately share a romanisation."""
    make(db, fallback_category, name_cn="生薑", name_alt="shoga")
    db.flush()
    make(db, fallback_category, name_cn="薑黃", name_alt="shoga")
    db.flush()


def test_an_ingredient_cannot_be_filed_in_a_category_that_does_not_exist(
    db, fallback_category
):
    db.add(Ingredient(name_cn="生薑", category_id=fallback_category.id + 9999))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_category_with_ingredients_in_it_cannot_be_deleted(db, fallback_category):
    """RESTRICT, and it must be RESTRICT that refuses.

    Without `passive_deletes="all"` on the relationship this passed for the
    wrong reason: SQLAlchemy set ingredient.category_id to NULL before the
    DELETE, and the NOT NULL on that column raised instead. Same exception
    type, same green test, different constraint doing the work - and the
    category tree's RESTRICT was never exercised at all.
    """
    make(db, fallback_category)
    db.flush()
    db.delete(fallback_category)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ingredient_category_id_fkey" in str(excinfo.value)


def test_an_ingredient_with_children_cannot_be_deleted(db, fallback_category):
    parent = make(db, fallback_category, name_cn="醬油")
    db.flush()
    make(db, fallback_category, name_cn="生抽", parent_id=parent.id)
    db.flush()
    db.delete(parent)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ingredient_parent_id_fkey" in str(excinfo.value)


def test_an_ingredient_with_no_children_can_be_deleted(db, fallback_category):
    """The mirror: RESTRICT must refuse a referenced row and only a referenced
    row. Without this, a constraint that refused every delete would pass."""
    ingredient = make(db, fallback_category, name_cn="老抽")
    db.flush()
    db.delete(ingredient)
    db.flush()


def test_a_second_fallback_category_is_refused(db, fallback_category):
    db.add(IngredientCategory(name_cn="其他", is_fallback=True))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_ingredient_category_one_fallback" in str(excinfo.value)


def test_any_number_of_categories_may_be_non_fallback(db, fallback_category):
    """The mirror. The index is partial, so it must constrain only the true
    rows - a plain unique index on is_fallback would refuse this."""
    db.add(IngredientCategory(name_cn="調味料"))
    db.add(IngredientCategory(name_cn="蔬菜"))
    db.flush()


def test_two_sibling_categories_may_not_share_a_name(db, fallback_category):
    db.add(IngredientCategory(name_cn="醬油", parent_id=None))
    db.flush()
    db.add(IngredientCategory(name_cn="醬油", parent_id=None))
    with pytest.raises(IntegrityError):
        db.flush()


def test_the_same_category_name_may_appear_under_different_parents(db, fallback_category):
    """The mirror: sibling uniqueness is scoped to the parent, so 其他 may sit
    under 調味料 and under 蔬菜 at once."""
    one = IngredientCategory(name_cn="調味料")
    two = IngredientCategory(name_cn="蔬菜")
    db.add_all([one, two])
    db.flush()
    db.add(IngredientCategory(name_cn="其他", parent_id=one.id))
    db.add(IngredientCategory(name_cn="其他", parent_id=two.id))
    db.flush()


def test_an_ingredient_may_not_carry_the_same_alias_twice(db, fallback_category):
    ingredient = make(db, fallback_category)
    db.flush()
    db.add(IngredientAlias(ingredient_id=ingredient.id, value="ginger"))
    db.flush()
    db.add(IngredientAlias(ingredient_id=ingredient.id, value="ginger"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_two_ingredients_may_share_an_alias(db, fallback_category):
    """Deliberate, and the mirror of the test above. Alias uniqueness is per
    ingredient, not global: two things may legitimately answer to one string,
    and a global constraint would refuse the second at the moment of typing it.
    Module 2 warns about a likely duplicate rather than refusing it."""
    one = make(db, fallback_category, name_cn="生薑")
    two = make(db, fallback_category, name_cn="薑黃")
    db.flush()
    db.add(IngredientAlias(ingredient_id=one.id, value="ginger"))
    db.add(IngredientAlias(ingredient_id=two.id, value="ginger"))
    db.flush()


def test_deleting_an_ingredient_takes_its_aliases_with_it(db, fallback_category):
    """CASCADE here, RESTRICT on the parent links. That asymmetry is the whole
    point: an alias has no life without its ingredient, a child does."""
    ingredient = make(db, fallback_category)
    db.flush()
    db.add(IngredientAlias(ingredient_id=ingredient.id, value="ginger"))
    db.flush()
    db.delete(ingredient)
    db.flush()
    assert db.query(IngredientAlias).count() == 0


def test_an_ingredient_may_not_list_one_preservation_method_twice(db, fallback_category):
    ingredient = make(db, fallback_category)
    db.flush()
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="冷藏", duration_days=5))
    db.flush()
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="冷藏"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_an_ingredient_may_keep_several_ways(db, fallback_category):
    """The mirror, and the reason preservation is a table at all: ginger keeps
    three ways with three different times."""
    ingredient = make(db, fallback_category)
    db.flush()
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="常溫", duration_days=7))
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="冷藏", duration_days=21))
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="冷凍", duration_days=90))
    db.flush()
    assert len(ingredient.preservation) == 3


def test_a_preservation_time_of_zero_days_is_refused(db, fallback_category):
    ingredient = make(db, fallback_category)
    db.flush()
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="冷藏", duration_days=0))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_preservation_row_may_leave_the_time_unknown(db, fallback_category):
    """The mirror: the duration is optional, and the CHECK must refuse zero
    without also refusing null."""
    ingredient = make(db, fallback_category)
    db.flush()
    db.add(IngredientPreservation(ingredient_id=ingredient.id, method="乾燥", notes="陰涼處"))
    db.flush()


def test_two_labels_may_not_share_a_name(db):
    db.add(Label(name_cn="常備"))
    db.flush()
    db.add(Label(name_cn="常備"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_label_with_no_name_is_refused(db):
    db.add(Label())
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_label_has_a_name" in str(excinfo.value)
