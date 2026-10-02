"""The constraints on the recipe family, and that they actually refuse.

The same discipline as `test_ingredient_model.py`: every refusal test makes the
refused thing possible - a row to collide with, a reference to protect - and a
mirror beside it proves the permitted version commits. Without the mirror a
constraint that refused everything would pass, and without the setup a gate
with nothing to refuse would.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    CookingMethod,
    Equipment,
    Image,
    Ingredient,
    Label,
    Recipe,
    RecipeAlias,
    RecipeCourse,
    RecipeImage,
    RecipeLine,
    RecipeSource,
    RecipeStep,
)


def make(db, **kwargs):
    kwargs.setdefault("name_cn", "番茄炒蛋")
    recipe = Recipe(**kwargs)
    db.add(recipe)
    db.flush()
    return recipe


# --- recipe ---------------------------------------------------------------


def test_a_recipe_with_no_name_at_all_is_refused(db):
    db.add(Recipe(name_cn=None, name_en=None, name_alt=None))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_recipe_has_a_name" in str(excinfo.value)


def test_a_recipe_named_only_in_the_alt_slot_is_allowed(db):
    make(db, name_cn=None, name_alt="tomato egg")


def test_two_recipes_may_share_a_name(db):
    """Versions share names, so recipe names are deliberately not unique -
    unlike every other named table in this app."""
    make(db, name_cn="咖哩")
    make(db, name_cn="咖哩")
    assert db.query(Recipe).filter_by(name_cn="咖哩").count() == 2


def test_a_new_recipe_defaults_to_a_dish_nobody_has_tried(db):
    recipe = make(db)
    db.refresh(recipe)
    assert recipe.kind == "dish"
    assert recipe.status == "want_to_try"


def test_a_recipe_may_not_be_a_version_of_itself(db):
    recipe = make(db)
    recipe.variant_of_id = recipe.id
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_recipe_not_its_own_version" in str(excinfo.value)


def test_a_recipe_may_be_a_version_of_another(db):
    original = make(db, name_cn="咖哩")
    version = make(db, name_cn="咖哩", variant_of_id=original.id)
    assert version.variant_of is original
    assert original.variants == [version]


def test_deleting_the_original_leaves_its_versions_standing(db):
    """SET NULL, not CASCADE and not RESTRICT: a version is a complete recipe
    in its own right. Expired before the delete so the database, not the ORM,
    is what clears the column."""
    original = make(db, name_cn="咖哩")
    version = make(db, name_cn="咖哩", variant_of_id=original.id)
    version_id = version.id
    db.expire_all()
    db.delete(db.get(Recipe, original.id))
    db.flush()
    db.expire_all()
    survivor = db.get(Recipe, version_id)
    assert survivor is not None
    assert survivor.variant_of_id is None


def test_a_course_with_recipes_filed_in_it_cannot_be_deleted(db):
    course = RecipeCourse(name_cn="主食")
    db.add(course)
    db.flush()
    make(db, course_id=course.id)
    db.delete(course)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "recipe_course_id_fkey" in str(excinfo.value)


def test_a_course_that_a_recipe_only_serves_as_can_be_deleted(db):
    """The mirror, and the asymmetry: serves-as links CASCADE."""
    course = RecipeCourse(name_cn="配菜")
    db.add(course)
    db.flush()
    recipe = make(db)
    recipe.serves_as.append(course)
    db.flush()
    db.delete(course)
    db.flush()
    db.expire_all()
    assert db.get(Recipe, recipe.id).serves_as == []


# --- children -------------------------------------------------------------


def test_a_recipe_may_not_carry_the_same_alias_twice(db):
    recipe = make(db)
    db.add(RecipeAlias(recipe_id=recipe.id, value="tomato egg"))
    db.flush()
    db.add(RecipeAlias(recipe_id=recipe.id, value="tomato egg"))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_recipe_alias" in str(excinfo.value)


def test_two_recipes_may_share_an_alias(db):
    one = make(db, name_cn="番茄炒蛋")
    two = make(db, name_cn="番茄蛋花湯")
    db.add(RecipeAlias(recipe_id=one.id, value="tomato"))
    db.add(RecipeAlias(recipe_id=two.id, value="tomato"))
    db.flush()


def test_a_source_with_nothing_but_a_platform_is_refused(db):
    recipe = make(db)
    db.add(RecipeSource(recipe_id=recipe.id, platform="youtube"))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_recipe_source_has_content" in str(excinfo.value)


def test_a_source_with_only_a_creator_is_allowed(db):
    """The mirror: a book has no URL, and a remembered channel no title."""
    recipe = make(db)
    db.add(RecipeSource(recipe_id=recipe.id, platform="book", creator="阿基師"))
    db.flush()


def test_a_line_naming_nothing_is_refused(db):
    recipe = make(db)
    db.add(RecipeLine(recipe_id=recipe.id, position=0))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_recipe_line_one_target" in str(excinfo.value)


def test_a_line_naming_both_an_ingredient_and_a_recipe_is_refused(db, ingredient):
    base = make(db, name_cn="番茄醬汁", kind="base")
    recipe = make(db)
    db.add(
        RecipeLine(
            recipe_id=recipe.id, position=0, ingredient_id=ingredient.id, sub_recipe_id=base.id
        )
    )
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_recipe_line_one_target" in str(excinfo.value)


def test_a_line_naming_exactly_one_thing_is_allowed(db, ingredient):
    base = make(db, name_cn="番茄醬汁", kind="base")
    recipe = make(db)
    db.add(RecipeLine(recipe_id=recipe.id, position=0, ingredient_id=ingredient.id))
    db.add(RecipeLine(recipe_id=recipe.id, position=1, sub_recipe_id=base.id))
    db.flush()
    db.refresh(recipe)
    assert [line.position for line in recipe.lines] == [0, 1]
    assert recipe.lines[0].ingredient is ingredient
    assert recipe.lines[1].sub_recipe is base
    assert recipe.lines[0].is_optional is False


def test_a_line_may_not_name_its_own_recipe(db):
    recipe = make(db)
    db.add(RecipeLine(recipe_id=recipe.id, position=0, sub_recipe_id=recipe.id))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_recipe_line_not_itself" in str(excinfo.value)


def test_two_lines_may_not_share_a_position(db, ingredient):
    recipe = make(db)
    db.add(RecipeLine(recipe_id=recipe.id, position=0, ingredient_id=ingredient.id))
    db.flush()
    db.add(RecipeLine(recipe_id=recipe.id, position=0, ingredient_id=ingredient.id))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_recipe_line_position" in str(excinfo.value)


def test_the_same_ingredient_may_appear_on_two_lines(db, ingredient):
    """The mirror: once for the meat, once for the sauce. Nothing is unique on
    the ingredient, only on the position."""
    recipe = make(db)
    db.add(RecipeLine(recipe_id=recipe.id, position=0, ingredient_id=ingredient.id))
    db.add(RecipeLine(recipe_id=recipe.id, position=1, ingredient_id=ingredient.id))
    db.flush()


def test_two_steps_may_not_share_a_position(db):
    recipe = make(db)
    db.add(RecipeStep(recipe_id=recipe.id, position=0, body="切番茄"))
    db.flush()
    db.add(RecipeStep(recipe_id=recipe.id, position=0, body="打蛋"))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_recipe_step_position" in str(excinfo.value)


def test_steps_at_different_positions_are_allowed(db):
    recipe = make(db)
    db.add(RecipeStep(recipe_id=recipe.id, position=0, body="切番茄"))
    db.add(RecipeStep(recipe_id=recipe.id, position=1, body="打蛋"))
    db.flush()


def _image(db, checksum="a" * 64):
    image = Image(
        checksum=checksum,
        storage_key=f"library/{checksum}.jpg",
        thumb_key=f"library/thumbs/{checksum}.jpg",
        byte_size=1,
        width=1,
        height=1,
    )
    db.add(image)
    db.flush()
    return image


def test_an_image_may_appear_once_in_a_recipe_gallery(db):
    recipe = make(db)
    image = _image(db)
    db.add(RecipeImage(recipe_id=recipe.id, image_id=image.id, position=0))
    db.flush()
    db.add(RecipeImage(recipe_id=recipe.id, image_id=image.id, position=1))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_recipe_image_once" in str(excinfo.value)


def test_two_images_may_not_share_a_recipe_gallery_position(db):
    recipe = make(db)
    one, two = _image(db, "a" * 64), _image(db, "b" * 64)
    db.add(RecipeImage(recipe_id=recipe.id, image_id=one.id, position=0))
    db.flush()
    db.add(RecipeImage(recipe_id=recipe.id, image_id=two.id, position=0))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_recipe_image_position" in str(excinfo.value)


def test_deleting_a_recipe_takes_every_child_with_it(db, ingredient):
    """CASCADE from the recipe down to everything it owns - and no further:
    the ingredient, the vocabulary rows and the picture all survive."""
    course = RecipeCourse(name_cn="主食")
    method = CookingMethod(name_cn="炒")
    pan = Equipment(name_cn="平底鍋")
    label = Label(name_cn="蛋")
    db.add_all([course, method, pan, label])
    db.flush()
    recipe = make(db)
    recipe.serves_as.append(course)
    recipe.methods.append(method)
    recipe.equipment.append(pan)
    recipe.labels.append(label)
    image = _image(db)
    db.add_all(
        [
            RecipeAlias(recipe_id=recipe.id, value="tomato egg"),
            RecipeSource(recipe_id=recipe.id, platform="website", url="https://x.example"),
            RecipeLine(recipe_id=recipe.id, position=0, ingredient_id=ingredient.id),
            RecipeStep(recipe_id=recipe.id, position=0, body="炒"),
            RecipeImage(recipe_id=recipe.id, image_id=image.id, position=0),
        ]
    )
    db.flush()
    recipe_id = recipe.id
    db.expire_all()

    db.delete(db.get(Recipe, recipe_id))
    db.flush()

    for child in (RecipeAlias, RecipeSource, RecipeLine, RecipeStep, RecipeImage):
        assert db.query(child).count() == 0, child.__name__
    from app.models import RecipeEquipment, RecipeLabel, RecipeMethod, RecipeServesAs

    for link in (RecipeServesAs, RecipeLabel, RecipeMethod, RecipeEquipment):
        assert db.query(link).count() == 0, link.__name__
    assert db.get(Ingredient, ingredient.id) is not None
    assert db.get(Image, image.id) is not None
    assert db.query(CookingMethod).count() == 1


# --- RESTRICT -------------------------------------------------------------


def test_an_ingredient_named_by_a_line_cannot_be_deleted(db, ingredient):
    """RESTRICT, and RESTRICT is what refuses: `RecipeLine.ingredient` carries
    `passive_deletes="all"` so the ORM cannot null the column first."""
    recipe = make(db)
    db.add(RecipeLine(recipe_id=recipe.id, position=0, ingredient_id=ingredient.id))
    db.flush()
    db.delete(ingredient)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "recipe_line_ingredient_id_fkey" in str(excinfo.value)


def test_an_ingredient_no_line_names_can_be_deleted(db, ingredient):
    make(db)
    db.delete(ingredient)
    db.flush()


def test_a_base_recipe_named_by_a_line_cannot_be_deleted(db):
    base = make(db, name_cn="番茄醬汁", kind="base")
    dish = make(db, name_cn="義大利麵")
    db.add(RecipeLine(recipe_id=dish.id, position=0, sub_recipe_id=base.id))
    db.flush()
    db.delete(base)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "recipe_line_sub_recipe_id_fkey" in str(excinfo.value)


def test_a_dish_using_a_base_recipe_can_be_deleted(db):
    """The mirror, and the direction that matters: the OUTER recipe's lines
    cascade with it, and the base it named is untouched."""
    base = make(db, name_cn="番茄醬汁", kind="base")
    dish = make(db, name_cn="義大利麵")
    db.add(RecipeLine(recipe_id=dish.id, position=0, sub_recipe_id=base.id))
    db.flush()
    db.delete(dish)
    db.flush()
    assert db.get(Recipe, base.id) is not None


def test_a_cooking_method_a_recipe_uses_cannot_be_deleted_through_the_database(db):
    method = CookingMethod(name_cn="蒸")
    db.add(method)
    db.flush()
    recipe = make(db)
    recipe.methods.append(method)
    db.flush()
    db.delete(method)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "recipe_method_method_id_fkey" in str(excinfo.value)


def test_equipment_a_recipe_uses_cannot_be_deleted_through_the_database(db):
    pan = Equipment(name_cn="電鍋")
    db.add(pan)
    db.flush()
    recipe = make(db)
    recipe.equipment.append(pan)
    db.flush()
    db.delete(pan)
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "recipe_equipment_equipment_id_fkey" in str(excinfo.value)


def test_a_label_on_a_recipe_can_be_deleted(db):
    """Labels CASCADE on both owners - module 1's behaviour, kept uniform."""
    label = Label(name_cn="辣")
    db.add(label)
    db.flush()
    recipe = make(db)
    recipe.labels.append(label)
    db.flush()
    db.delete(label)
    db.flush()
    db.expire_all()
    assert db.get(Recipe, recipe.id).labels == []
