"""A recipe line's alternatives - 雞腿 或 雞胸肉 - end to end.

An alternative names an ingredient or a dish exactly as a line does, by id or
by a new name the save resolves, and every rule a line's target obeys holds
for it: an id naming nothing is 422, a recipe may not use its own dish, and
the dish-nesting graph may not cycle through one. What names a row through an
alternative uses it - "used in", the recipe filter, the delete refusal - and
an ingredient merge carries alternatives along, dropping the ones the merge
makes redundant.

Load-bearing setup, per the platform rule on negative tests: the 422 test has
a real ingredient and a real dish in the database; the delete refusals have an
alternative actually naming the row, and their mirrors remove it and delete;
the cycle test builds a real would-be cycle that runs only through an
alternative, and its mirror shows the same save accepted without it.
"""

import pytest

from app.models import Dish, Ingredient, RecipeLineAlternative

pytestmark = pytest.mark.usefixtures("recipe_statuses")

ZERO = {"aliases": 0, "preservation": 0, "heating": 0, "links": 0}


def create(client, dish="照燒雞", **body):
    if "dish_id" not in body:
        body["new_dish"] = {"name_cn": dish}
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def set_lines(client, recipe_id, lines):
    return client.patch(
        f"/api/edit/recipes/{recipe_id}", json={"line_groups": [], "lines": lines}
    )


@pytest.fixture
def chicken(db, fallback_category):
    """雞腿, 雞胸肉 and 米酒 - a line's target and two things to swap in."""
    rows = {
        name: Ingredient(name_cn=name, category_id=fallback_category.id)
        for name in ("雞腿", "雞胸肉", "米酒")
    }
    db.add_all(rows.values())
    db.flush()
    return {name: row.id for name, row in rows.items()}


def alt_targets(line):
    return [
        (a["ingredient"] or {}).get("display_name") or a["sub_dish"]["display_name"]
        for a in line["alternatives"]
    ]


# --- writing and reading -------------------------------------------------------


def test_a_line_carries_its_alternatives_in_order_with_amount_and_note(client, chicken):
    sauce = create(client, dish="照燒醬")["dish"]
    recipe = create(
        client,
        lines=[
            {
                "ingredient_id": chicken["雞腿"],
                "amount": "300g",
                "alternatives": [
                    {"ingredient_id": chicken["雞胸肉"], "amount": "250g", "note": "較柴"},
                    {"sub_dish_id": sauce["id"]},
                ],
            },
            {"ingredient_id": chicken["米酒"]},
        ],
    )
    first, second = recipe["lines"]
    assert first["alternatives"][0]["ingredient"] == {
        "id": chicken["雞胸肉"],
        "display_name": "雞胸肉",
        "needs_detail": False,
    }
    assert first["alternatives"][0]["sub_dish"] is None
    assert (first["alternatives"][0]["amount"], first["alternatives"][0]["note"]) == ("250g", "較柴")
    assert first["alternatives"][1]["ingredient"] is None
    assert first["alternatives"][1]["sub_dish"] == {
        "id": sauce["id"],
        "display_name": "照燒醬",
        "kind": "dish",
    }
    # Blank means "the same as the line".
    assert first["alternatives"][1]["amount"] is None
    assert [a["position"] for a in first["alternatives"]] == [0, 1]
    assert second["alternatives"] == []
    # Read back the same as the write answered.
    assert client.get(f"/api/recipes/{recipe['id']}").json()["lines"] == recipe["lines"]


def test_an_alternative_inside_a_group_round_trips(client, chicken):
    recipe = create(
        client,
        line_groups=[
            {
                "name": "醃料",
                "lines": [
                    {"ingredient_id": chicken["米酒"], "alternatives": [{"new_ingredient": {"name_cn": "清酒"}}]}
                ],
            }
        ],
    )
    line = recipe["line_groups"][0]["lines"][0]
    assert alt_targets(line) == ["清酒"]
    assert line["alternatives"][0]["ingredient"]["needs_detail"] is True


def test_a_new_name_on_an_alternative_reuses_the_line_code_path(client, db, chicken):
    """The same new name typed on a line and on an alternative is one stub; a
    new dish on an alternative is a sauce unless told, as on a line."""
    before = db.query(Ingredient).count()
    recipe = create(
        client,
        lines=[
            {"new_ingredient": {"name_cn": "清酒"}},
            {
                "ingredient_id": chicken["米酒"],
                "alternatives": [
                    {"new_ingredient": {"name_cn": "清酒"}},
                    {"new_dish": {"name_cn": "自製照燒醬"}},
                ],
            },
        ],
    )
    assert db.query(Ingredient).count() == before + 1
    stub = recipe["lines"][0]["ingredient"]["id"]
    alternatives = recipe["lines"][1]["alternatives"]
    assert alternatives[0]["ingredient"]["id"] == stub
    assert alternatives[1]["sub_dish"]["kind"] == "sauce"
    assert db.query(Dish).filter_by(name_cn="自製照燒醬").count() == 1


def test_an_alternative_naming_a_missing_id_is_422_and_writes_nothing(client, db, chicken):
    sauce = create(client, dish="照燒醬")["dish"]  # the dish table is not empty
    for alternative, what in (
        ({"ingredient_id": 999999}, "ingredient"),
        ({"sub_dish_id": 999999}, "dish"),
        ({"ingredient_id": 0}, "ingredient"),
    ):
        lines = [
            {
                "ingredient_id": chicken["雞腿"],
                "alternatives": [alternative, {"new_ingredient": {"name_cn": "不該建立"}}],
            }
        ]
        response = client.post(
            "/api/edit/recipes", json={"new_dish": {"name_cn": "x"}, "lines": lines}
        )
        assert response.status_code == 422, alternative
        assert response.json()["detail"] == f"No such {what}: {alternative[next(iter(alternative))]}."
    assert db.query(Ingredient).filter_by(name_cn="不該建立").count() == 0
    # Mirror: the rows that exist are accepted.
    line = create(
        client,
        lines=[
            {
                "ingredient_id": chicken["雞腿"],
                "alternatives": [{"ingredient_id": chicken["雞胸肉"]}, {"sub_dish_id": sauce["id"]}],
            }
        ],
    )["lines"][0]
    assert alt_targets(line) == ["雞胸肉", "照燒醬"]


def test_an_alternative_names_exactly_one_target(client, chicken):
    for alternative in (
        {},
        {"amount": "1"},
        {"ingredient_id": chicken["雞胸肉"], "new_ingredient": {"name_cn": "蔥"}},
        {"ingredient_id": chicken["雞胸肉"], "is_optional": True},  # a line's, not an alternative's
        {"ingredient_id": chicken["雞胸肉"], "alternatives": []},
    ):
        lines = [{"ingredient_id": chicken["雞腿"], "alternatives": [alternative]}]
        body = {"new_dish": {"name_cn": "x"}, "lines": lines}
        assert client.post("/api/edit/recipes", json=body).status_code == 422, alternative


def test_an_alternative_repeating_its_line_or_a_sibling_is_dropped(client, chicken):
    """A line naming 雞腿 already accepts 雞腿; listing it again says nothing."""
    line = create(
        client,
        lines=[
            {
                "ingredient_id": chicken["雞腿"],
                "alternatives": [
                    {"ingredient_id": chicken["雞腿"], "amount": "same"},
                    {"ingredient_id": chicken["雞胸肉"], "amount": "first"},
                    {"ingredient_id": chicken["雞胸肉"], "amount": "second"},
                    {"new_ingredient": {"name_cn": "雞胸肉"}},  # resolves to the same row
                ],
            }
        ],
    )["lines"][0]
    assert [(a["ingredient"]["id"], a["amount"]) for a in line["alternatives"]] == [
        (chicken["雞胸肉"], "first")
    ]
    assert [a["position"] for a in line["alternatives"]] == [0]


def test_resaving_the_same_lines_replaces_the_alternatives(client, chicken):
    lines = [
        {
            "ingredient_id": chicken["雞腿"],
            "alternatives": [{"ingredient_id": chicken["雞胸肉"]}],
        }
    ]
    recipe = create(client, lines=lines)
    response = set_lines(client, recipe["id"], lines)
    assert response.status_code == 200, response.text
    assert alt_targets(response.json()["lines"][0]) == ["雞胸肉"]
    response = set_lines(client, recipe["id"], [{"ingredient_id": chicken["雞腿"]}])
    assert response.json()["lines"][0]["alternatives"] == []


# --- the dish graph ----------------------------------------------------------------


def test_an_alternative_may_not_name_its_own_recipes_dish(client, chicken):
    recipe = create(client, dish="咖哩")
    own = recipe["dish"]["id"]
    lines = [{"ingredient_id": chicken["雞腿"], "alternatives": [{"sub_dish_id": own}]}]
    response = set_lines(client, recipe["id"], lines)
    assert response.status_code == 422
    assert "own dish" in response.json()["detail"]
    # Mirror: another dish is accepted.
    other = create(client, dish="白飯")["dish"]["id"]
    lines[0]["alternatives"] = [{"sub_dish_id": other}]
    assert set_lines(client, recipe["id"], lines).status_code == 200


def test_a_new_dish_on_an_alternative_with_the_recipes_own_new_name_is_refused(client, db, chicken):
    lines = [{"ingredient_id": chicken["雞腿"], "alternatives": [{"new_dish": {"name_cn": "咖哩"}}]}]
    response = client.post(
        "/api/edit/recipes", json={"new_dish": {"name_cn": "咖哩"}, "lines": lines}
    )
    assert response.status_code == 422
    assert db.query(Dish).count() == 0


def test_a_cycle_through_an_alternative_is_refused(client, chicken):
    """A's recipe offers B as an alternative; B's recipe naming A would loop.

    The cycle runs ONLY through the alternative, so it is the alternative the
    guard has to see. The mirror: with that alternative removed, the same
    save of B is accepted.
    """
    a = create(client, dish="A醬")
    b = create(client, dish="B醬")
    a_lines = [
        {"ingredient_id": chicken["米酒"], "alternatives": [{"sub_dish_id": b["dish"]["id"]}]}
    ]
    assert set_lines(client, a["id"], a_lines).status_code == 200

    b_lines = [{"sub_dish_id": a["dish"]["id"]}]
    response = set_lines(client, b["id"], b_lines)
    assert response.status_code == 422
    assert "loop" in response.json()["detail"]

    # And the other way round: B names A on an alternative of its own.
    response = set_lines(
        client,
        b["id"],
        [{"ingredient_id": chicken["米酒"], "alternatives": [{"sub_dish_id": a["dish"]["id"]}]}],
    )
    assert response.status_code == 422

    # Mirror: without A's alternative there is no path back, and B saves.
    assert set_lines(client, a["id"], [{"ingredient_id": chicken["米酒"]}]).status_code == 200
    assert set_lines(client, b["id"], b_lines).status_code == 200


def test_moving_a_recipe_to_a_dish_its_alternative_names_is_refused(client, chicken):
    target = create(client, dish="目標")["dish"]["id"]
    recipe = create(
        client,
        lines=[{"ingredient_id": chicken["雞腿"], "alternatives": [{"sub_dish_id": target}]}],
    )
    response = client.patch(f"/api/edit/recipes/{recipe['id']}", json={"dish_id": target})
    assert response.status_code == 422
    assert "own dish" in response.json()["detail"]
    # Mirror: another dish is fine.
    elsewhere = create(client, dish="別處")["dish"]["id"]
    response = client.patch(f"/api/edit/recipes/{recipe['id']}", json={"dish_id": elsewhere})
    assert response.status_code == 200, response.text


# --- used in -------------------------------------------------------------------------


def used_in(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return {r["display_name"]: r["alternative_only"] for r in response.json()["used_in"]}


def test_an_ingredient_named_only_as_an_alternative_is_used_in_that_recipe(client, chicken):
    create(client, dish="照燒雞", lines=[{"ingredient_id": chicken["雞腿"], "alternatives": [{"ingredient_id": chicken["雞胸肉"]}]}])
    create(client, dish="雞胸沙拉", lines=[{"ingredient_id": chicken["雞胸肉"]}])
    # Both a line and an alternative in one recipe: one recipe, not alternative-only.
    create(
        client,
        dish="雞肉飯",
        lines=[
            {"ingredient_id": chicken["雞胸肉"]},
            {"ingredient_id": chicken["米酒"], "alternatives": [{"ingredient_id": chicken["雞胸肉"]}]},
        ],
    )
    assert used_in(client, f"/api/ingredients/{chicken['雞胸肉']}") == {
        "照燒雞": True,
        "雞肉飯": False,
        "雞胸沙拉": False,
    }
    rows = {r["id"]: r["used_in_count"] for r in client.get("/api/ingredients").json()}
    assert rows[chicken["雞胸肉"]] == 3
    # Mirror: an ingredient used only on lines has no alternative-only recipe.
    assert used_in(client, f"/api/ingredients/{chicken['雞腿']}") == {"照燒雞": False}
    # The recipe filter reads the same definition.
    listed = client.get("/api/recipes", params={"ingredient_id": chicken["雞胸肉"]}).json()
    assert sorted(r["display_name"] for r in listed) == ["照燒雞", "雞肉飯", "雞胸沙拉"]


def test_an_alternative_naming_a_variety_counts_on_the_parent(client, db, fallback_category, chicken):
    parent = db.get(Ingredient, chicken["雞腿"])
    thigh = Ingredient(name_cn="去骨雞腿", category_id=fallback_category.id, parent_id=parent.id)
    db.add(thigh)
    db.flush()
    create(client, lines=[{"ingredient_id": chicken["米酒"], "alternatives": [{"ingredient_id": thigh.id}]}])
    assert used_in(client, f"/api/ingredients/{parent.id}") == {"照燒雞": True}


def test_a_dish_named_only_as_an_alternative_is_used_in_that_recipe(client, chicken):
    bought = create(client, dish="市售照燒醬")["dish"]["id"]
    create(client, dish="照燒雞", lines=[{"ingredient_id": chicken["米酒"], "alternatives": [{"sub_dish_id": bought}]}])
    create(client, dish="照燒豆腐", lines=[{"sub_dish_id": bought}])
    assert used_in(client, f"/api/dishes/{bought}") == {"照燒雞": True, "照燒豆腐": False}


# --- deleting what an alternative names ------------------------------------------------


def test_an_ingredient_an_alternative_names_cannot_be_deleted(client, db, chicken):
    recipe = create(
        client,
        lines=[{"ingredient_id": chicken["雞腿"], "alternatives": [{"ingredient_id": chicken["雞胸肉"]}]}],
    )
    preview = client.get(f"/api/ingredients/{chicken['雞胸肉']}/cascade").json()
    assert preview["recipes"] == 1
    response = client.delete(f"/api/edit/ingredients/{chicken['雞胸肉']}", params=ZERO)
    assert response.status_code == 409
    assert [r["id"] for r in response.json()["used_in"]] == [recipe["id"]]
    assert db.get(Ingredient, chicken["雞胸肉"]) is not None

    # Mirror: with the alternative gone, nothing names it and it deletes.
    assert set_lines(client, recipe["id"], [{"ingredient_id": chicken["雞腿"]}]).status_code == 200
    assert client.get(f"/api/ingredients/{chicken['雞胸肉']}/cascade").json()["recipes"] == 0
    response = client.delete(f"/api/edit/ingredients/{chicken['雞胸肉']}", params=ZERO)
    assert response.status_code == 204, response.text


def test_a_dish_an_alternative_names_cannot_be_deleted(client, chicken):
    sauce = client.post("/api/edit/dishes", json={"name_cn": "市售照燒醬", "kind": "sauce"}).json()
    recipe = create(
        client,
        lines=[{"ingredient_id": chicken["米酒"], "alternatives": [{"sub_dish_id": sauce["id"]}]}],
    )
    assert client.get(f"/api/dishes/{sauce['id']}/cascade").json()["used_in"] == 1
    response = client.delete(f"/api/edit/dishes/{sauce['id']}", params={"aliases": 0})
    assert response.status_code == 409
    assert [r["id"] for r in response.json()["used_in"]] == [recipe["id"]]

    # Mirror: the alternative removed, the dish deletes.
    assert set_lines(client, recipe["id"], [{"ingredient_id": chicken["米酒"]}]).status_code == 200
    response = client.delete(f"/api/edit/dishes/{sauce['id']}", params={"aliases": 0})
    assert response.status_code == 204, response.text


def test_the_database_refuses_deleting_what_an_alternative_names(client, db, chicken):
    """The RESTRICT itself, below the API's refusal."""
    from sqlalchemy.exc import IntegrityError

    create(
        client,
        lines=[{"ingredient_id": chicken["雞腿"], "alternatives": [{"ingredient_id": chicken["雞胸肉"]}]}],
    )
    nested = db.begin_nested()
    with pytest.raises(IntegrityError):
        db.delete(db.get(Ingredient, chicken["雞胸肉"]))
        db.flush()
    nested.rollback()


def test_an_alternative_goes_with_its_line_and_its_recipe(client, db, chicken):
    recipe = create(
        client,
        lines=[{"ingredient_id": chicken["雞腿"], "alternatives": [{"ingredient_id": chicken["雞胸肉"]}]}],
    )
    assert db.query(RecipeLineAlternative).count() == 1
    counts = client.get(f"/api/recipes/{recipe['id']}/cascade").json()
    response = client.delete(f"/api/edit/recipes/{recipe['id']}", params=counts)
    assert response.status_code == 204, response.text
    assert db.query(RecipeLineAlternative).count() == 0


# --- ingredient merge ----------------------------------------------------------------------


def preview(client, source, into):
    response = client.get(f"/api/ingredients/{source}/merge-preview", params={"into": into})
    assert response.status_code == 200, response.text
    return response.json()


def merge(client, source, into):
    fingerprint = preview(client, source, into)["fingerprint"]
    return client.post(
        f"/api/edit/ingredients/{source}/merge", json={"into": into, "fingerprint": fingerprint}
    )


def test_a_merge_moves_alternatives_and_drops_the_ones_it_makes_redundant(client, chicken, db, fallback_category):
    """青蔥 merges into 蔥. Four lines, each a case:

    - an alternative naming the source, on an unrelated line: moves;
    - an alternative naming the source, on a line naming the target: dropped,
      the line accepts the target already;
    - an alternative naming the target, on a line naming the source: dropped,
      for the same reason once the line moves;
    - the source and the target both as alternatives of one line: one kept.
    """
    source = Ingredient(name_cn="青蔥", category_id=fallback_category.id)
    target = Ingredient(name_cn="蔥", category_id=fallback_category.id)
    db.add_all([source, target])
    db.flush()
    other = chicken["米酒"]
    recipe = create(
        client,
        lines=[
            {"ingredient_id": other, "alternatives": [{"ingredient_id": source.id, "amount": "moves"}]},
            {"ingredient_id": target.id, "alternatives": [{"ingredient_id": source.id}]},
            {"ingredient_id": source.id, "alternatives": [{"ingredient_id": target.id}]},
            {
                "ingredient_id": other,
                "alternatives": [
                    {"ingredient_id": target.id, "amount": "kept"},
                    {"ingredient_id": source.id, "amount": "collapses"},
                ],
            },
        ],
    )
    plan = preview(client, source.id, target.id)
    assert plan["moves"]["lines"] == 1
    assert plan["moves"]["alternatives"] == 1
    assert plan["dropped_alternatives"] == 3

    response = merge(client, source.id, target.id)
    assert response.status_code == 200, response.text
    lines = client.get(f"/api/recipes/{recipe['id']}").json()["lines"]
    assert [[(a["ingredient"]["id"], a["amount"]) for a in line["alternatives"]] for line in lines] == [
        [(target.id, "moves")],
        [],
        [],
        [(target.id, "kept")],
    ]
    assert db.query(RecipeLineAlternative).count() == 2


def test_a_merge_with_no_alternative_involved_reports_none(client, chicken, db, fallback_category):
    source = Ingredient(name_cn="青蔥", category_id=fallback_category.id)
    target = Ingredient(name_cn="蔥", category_id=fallback_category.id)
    db.add_all([source, target])
    db.flush()
    create(client, lines=[{"ingredient_id": source.id, "alternatives": [{"ingredient_id": chicken["米酒"]}]}])
    plan = preview(client, source.id, target.id)
    assert (plan["moves"]["alternatives"], plan["dropped_alternatives"]) == (0, 0)


def test_an_alternative_added_after_the_preview_makes_the_merge_stale(client, chicken, db, fallback_category):
    source = Ingredient(name_cn="青蔥", category_id=fallback_category.id)
    target = Ingredient(name_cn="蔥", category_id=fallback_category.id)
    db.add_all([source, target])
    db.flush()
    recipe = create(client, lines=[{"ingredient_id": chicken["米酒"]}])
    fingerprint = preview(client, source.id, target.id)["fingerprint"]
    set_lines(
        client,
        recipe["id"],
        [{"ingredient_id": chicken["米酒"], "alternatives": [{"ingredient_id": source.id}]}],
    )
    response = client.post(
        f"/api/edit/ingredients/{source.id}/merge",
        json={"into": target.id, "fingerprint": fingerprint},
    )
    assert response.status_code == 409


# --- templates -------------------------------------------------------------------------------

LIST = "/api/recipe-templates"
EDIT = "/api/edit/recipe-templates"


def test_a_template_carries_alternatives_and_drops_a_deleted_one(client, db, chicken):
    sauce = Dish(name_cn="市售照燒醬", kind="sauce")
    db.add(sauce)
    db.flush()
    body = {
        "lines": [
            {
                "ingredient_id": chicken["雞腿"],
                "alternatives": [
                    {"ingredient_id": chicken["雞胸肉"], "amount": "250g", "note": "較柴"},
                    {"sub_dish_id": sauce.id},
                    {"ingredient_id": chicken["雞腿"]},  # repeats its line: dropped on save
                ],
            }
        ]
    }
    response = client.post(EDIT, json={"name": "雞", "body": body})
    assert response.status_code == 201, response.text
    made = response.json()
    assert made["dropped"] == 0
    alternatives = made["body"]["lines"][0]["alternatives"]
    assert alternatives == [
        {
            "ingredient": {"id": chicken["雞胸肉"], "display_name": "雞胸肉", "needs_detail": False},
            "sub_dish": None,
            "amount": "250g",
            "note": "較柴",
        },
        {
            "ingredient": None,
            "sub_dish": {"id": sauce.id, "display_name": "市售照燒醬", "kind": "sauce"},
            "amount": None,
            "note": None,
        },
    ]

    db.delete(sauce)
    db.flush()
    template = client.get(f"{LIST}/{made['id']}").json()
    assert template["dropped"] == 1
    assert [a["ingredient"]["id"] for a in template["body"]["lines"][0]["alternatives"]] == [
        chicken["雞胸肉"]
    ]


def test_a_template_alternative_never_creates_and_never_names_nothing(client, chicken):
    for alternative in ({"new_ingredient": {"name_cn": "清酒"}}, {"new_dish": {"name_cn": "醬"}}):
        body = {"lines": [{"ingredient_id": chicken["米酒"], "alternatives": [alternative]}]}
        response = client.post(EDIT, json={"name": "x", "body": body})
        assert response.status_code == 422, alternative
    body = {"lines": [{"ingredient_id": chicken["米酒"], "alternatives": [{"ingredient_id": 999999}]}]}
    response = client.post(EDIT, json={"name": "x", "body": body})
    assert response.status_code == 422
    assert response.json()["detail"] == "No such ingredient: 999999."


def test_a_template_made_from_a_recipe_carries_its_alternatives(client, chicken):
    recipe = create(
        client,
        lines=[{"ingredient_id": chicken["雞腿"], "alternatives": [{"ingredient_id": chicken["雞胸肉"], "note": "較柴"}]}],
    )
    response = client.post(f"{EDIT}/from-recipe/{recipe['id']}", json={"name": "雞"})
    assert response.status_code == 201, response.text
    alternative = response.json()["body"]["lines"][0]["alternatives"][0]
    assert (alternative["ingredient"]["id"], alternative["note"]) == (chicken["雞胸肉"], "較柴")


def test_a_template_stored_before_alternatives_reads_as_none(client, db, chicken):
    from app.models import RecipeTemplate

    row = RecipeTemplate(
        name="舊",
        sort_order=0,
        body={
            "servings": None,
            "time": None,
            "lines": [
                {"ingredient_id": chicken["雞腿"], "sub_dish_id": None, "amount": None, "note": None, "is_optional": False}
            ],
            "line_groups": [],
            "steps": [],
            "step_groups": [],
            "method_ids": [],
            "equipment_ids": [],
        },
    )
    db.add(row)
    db.flush()
    template = client.get(f"{LIST}/{row.id}").json()
    assert template["body"]["lines"][0]["alternatives"] == []


def test_a_merge_rewrites_template_alternatives_and_drops_the_redundant(client, db, chicken, fallback_category):
    source = Ingredient(name_cn="青蔥", category_id=fallback_category.id)
    target = Ingredient(name_cn="蔥", category_id=fallback_category.id)
    db.add_all([source, target])
    db.flush()
    body = {
        "lines": [
            {"ingredient_id": chicken["米酒"], "alternatives": [{"ingredient_id": source.id, "amount": "1"}]},
            {"ingredient_id": target.id, "alternatives": [{"ingredient_id": source.id}]},
            {"ingredient_id": chicken["米酒"], "alternatives": [{"ingredient_id": target.id}, {"ingredient_id": source.id}]},
        ]
    }
    made = client.post(EDIT, json={"name": "蔥", "body": body}).json()
    assert merge(client, source.id, target.id).status_code == 200
    template = client.get(f"{LIST}/{made['id']}").json()
    assert template["dropped"] == 0
    assert [[a["ingredient"]["id"] for a in line["alternatives"]] for line in template["body"]["lines"]] == [
        [target.id],
        [],
        [target.id],
    ]
