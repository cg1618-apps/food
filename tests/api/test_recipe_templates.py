"""Recipe templates: a named skeleton of a recipe, kept to start new ones from.

A template's body is the recipe payload's shapes - lines with their groups,
steps with their groups and kinds, methods, equipment, servings, time - stored
as one JSON document. These tests are the API: create, read, rename, replace,
delete, reorder, the refusals, a template made from a recipe, how a reference
that no longer exists is dropped on the way out, and an ingredient merge
rewriting what the templates name.

Load-bearing fixtures: `body_refs` names one of everything a template can
point at - an ingredient, a dish, a 材料分組 value, a method, a piece of
equipment - so the "dropped" test has something to drop, and asserts zero
dropped on the same template first, so the count is not vacuously right.
"""

import pytest

from app.models import (
    CookingMethod,
    Dish,
    Equipment,
    Ingredient,
    LineGroup,
    RecipeTemplate,
)

pytestmark = pytest.mark.usefixtures("recipe_statuses")

LIST = "/api/recipe-templates"
EDIT = "/api/edit/recipe-templates"


def create(client, name="基本炒菜", **body):
    response = client.post(EDIT, json={"name": name, "body": body})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def body_refs(db, ingredient, line_groups, step_groups):
    """One of every kind of row a template body can name."""
    sauce = Dish(name_cn="蒜蓉醬", kind="sauce")
    method = CookingMethod(name_cn="炒")
    pan = Equipment(name_cn="炒鍋")
    db.add_all([sauce, method, pan])
    db.flush()
    return {
        "ingredient": ingredient,
        "sauce": sauce,
        "method": method,
        "pan": pan,
        "main": line_groups["主料"],
        "prep": step_groups["備料"],
    }


def full_body(refs):
    return {
        "servings": "2 人份",
        "time": "20 分鐘",
        "lines": [{"ingredient_id": refs["ingredient"].id, "amount": "1 片"}],
        "line_groups": [
            {
                "line_group_id": refs["main"].id,
                "lines": [{"sub_dish_id": refs["sauce"].id, "note": "先調好", "is_optional": True}],
            },
            {"name": "醃料", "lines": []},
        ],
        "steps": [{"body": "熱鍋"}],
        "step_groups": [
            {
                "step_group_id": refs["prep"].id,
                "steps": [{"body": "切", "kind": "step"}, {"body": "火別太大", "kind": "note"}],
            }
        ],
        "method_ids": [refs["method"].id],
        "equipment_ids": [refs["pan"].id],
    }


# --- create and read ---------------------------------------------------------


def test_a_template_round_trips_with_every_reference_resolved(client, body_refs):
    refs = body_refs
    made = create(client, **full_body(refs))
    assert made["name"] == "基本炒菜"
    assert made["dropped"] == 0

    got = client.get(f"{LIST}/{made['id']}")
    assert got.status_code == 200, got.text
    template = got.json()
    assert template == made
    body = template["body"]
    assert body["servings"] == "2 人份"
    assert body["time"] == "20 分鐘"
    [line] = body["lines"]
    assert line["ingredient"] == {
        "id": refs["ingredient"].id,
        "display_name": "生薑",
        "needs_detail": False,
    }
    assert line["sub_dish"] is None
    assert line["amount"] == "1 片"

    main, marinade = body["line_groups"]
    assert main["group"] == {"id": refs["main"].id, "display_name": "主料"}
    assert main["name"] is None
    assert main["display_name"] == "主料"
    [sauce_line] = main["lines"]
    assert sauce_line["sub_dish"] == {"id": refs["sauce"].id, "display_name": "蒜蓉醬", "kind": "sauce"}
    assert sauce_line["is_optional"] is True
    assert sauce_line["note"] == "先調好"
    assert marinade["group"] is None
    assert marinade["name"] == "醃料"
    assert marinade["display_name"] == "醃料"
    assert marinade["lines"] == []

    assert body["steps"] == [{"body": "熱鍋", "kind": "step"}]
    [prep] = body["step_groups"]
    assert prep["group"] == {"id": refs["prep"].id, "display_name": "備料"}
    assert [(s["body"], s["kind"]) for s in prep["steps"]] == [("切", "step"), ("火別太大", "note")]
    assert body["methods"] == [{"id": refs["method"].id, "display_name": "炒"}]
    assert body["equipment"] == [{"id": refs["pan"].id, "display_name": "炒鍋"}]


def test_a_template_may_be_empty(client):
    made = create(client, name="空的")
    assert made["body"] == {
        "servings": None,
        "time": None,
        "lines": [],
        "line_groups": [],
        "steps": [],
        "step_groups": [],
        "methods": [],
        "equipment": [],
    }
    # And the body may be left out altogether.
    response = client.post(EDIT, json={"name": "更空的"})
    assert response.status_code == 201, response.text


def test_a_one_off_group_name_matching_a_value_is_stored_as_that_value(client, line_groups):
    made = create(client, line_groups=[{"name": " 主料 ", "lines": []}])
    [group] = made["body"]["line_groups"]
    assert group["group"] == {"id": line_groups["主料"].id, "display_name": "主料"}
    assert group["name"] is None


def test_the_list_is_in_order_with_line_and_step_counts(client, body_refs):
    b = create(client, name="b", **full_body(body_refs))
    a = create(client, name="a")
    response = client.get(LIST)
    assert response.status_code == 200
    # A new template goes last, whatever its name.
    assert response.json() == [
        {"id": b["id"], "name": "b", "sort_order": 0, "line_count": 2, "step_count": 3},
        {"id": a["id"], "name": "a", "sort_order": 1, "line_count": 0, "step_count": 0},
    ]


def test_a_missing_template_is_404(client):
    assert client.get(f"{LIST}/999999").status_code == 404
    assert client.patch(f"{EDIT}/999999", json={"name": "x"}).status_code == 404
    assert client.delete(f"{EDIT}/999999").status_code == 404


# --- refusals ----------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        {"new_ingredient": {"name_cn": "紫蘇"}},
        {"new_dish": {"name_cn": "照燒醬"}},
    ],
)
def test_a_template_never_creates_an_ingredient_or_a_dish(client, db, line):
    for body in ({"lines": [line]}, {"line_groups": [{"name": "醬", "lines": [line]}]}):
        response = client.post(EDIT, json={"name": "會建東西", "body": body})
        assert response.status_code == 422, response.text
        assert "existing" in response.json()["detail"]
    assert db.query(RecipeTemplate).count() == 0
    assert db.query(Ingredient).count() == 0
    assert db.query(Dish).count() == 0


def test_a_line_naming_an_existing_ingredient_is_accepted(client, ingredient):
    # The mirror of the refusal above, through the same field position.
    made = create(client, lines=[{"ingredient_id": ingredient.id}])
    assert made["body"]["lines"][0]["ingredient"]["id"] == ingredient.id


def test_a_reference_that_does_not_exist_is_refused_on_write(client, ingredient):
    for body in (
        {"lines": [{"ingredient_id": 999999}]},
        {"lines": [{"sub_dish_id": 999999}]},
        {"method_ids": [999999]},
        {"equipment_ids": [999999]},
        {"line_groups": [{"line_group_id": 999999}]},
        {"step_groups": [{"step_group_id": 999999}]},
    ):
        response = client.post(EDIT, json={"name": "壞的", "body": body})
        assert response.status_code == 422, (body, response.text)


def test_a_line_names_exactly_one_target(client, ingredient):
    response = client.post(EDIT, json={"name": "兩個", "body": {"lines": [{"amount": "1"}]}})
    assert response.status_code == 422


def test_names_are_unique_whatever_the_case(client):
    first = create(client, name="Basic Stir Fry")
    response = client.post(EDIT, json={"name": " basic stir fry "})
    assert response.status_code == 422, response.text
    assert "name" in response.json()["detail"]

    other = create(client, name="湯")
    assert client.patch(f"{EDIT}/{other['id']}", json={"name": "BASIC STIR FRY"}).status_code == 422
    # Renaming a template to its own name in another case is no clash.
    renamed = client.patch(f"{EDIT}/{first['id']}", json={"name": "basic stir fry"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "basic stir fry"


def test_a_blank_name_is_refused(client):
    assert client.post(EDIT, json={"name": "  "}).status_code == 422
    made = create(client, name="有名字")
    assert client.patch(f"{EDIT}/{made['id']}", json={"name": ""}).status_code == 422
    assert client.patch(f"{EDIT}/{made['id']}", json={"name": None}).status_code == 422
    assert client.patch(f"{EDIT}/{made['id']}", json={"body": None}).status_code == 422


def test_the_body_refuses_fields_a_template_does_not_carry(client):
    for field, value in (("sources", []), ("notes", "x"), ("dish_id", 1), ("status_id", 1)):
        response = client.post(EDIT, json={"name": "多的", "body": {field: value}})
        assert response.status_code == 422, field


# --- update, delete, order ---------------------------------------------------


def test_a_patch_replaces_only_what_it_sends(client, body_refs):
    made = create(client, **full_body(body_refs))
    renamed = client.patch(f"{EDIT}/{made['id']}", json={"name": "改名了"}).json()
    assert renamed["name"] == "改名了"
    assert renamed["body"] == made["body"]

    replaced = client.patch(f"{EDIT}/{made['id']}", json={"body": {"time": "5 分鐘"}})
    assert replaced.status_code == 200, replaced.text
    body = replaced.json()["body"]
    assert body["time"] == "5 分鐘"
    assert body["lines"] == []
    assert body["methods"] == []
    assert replaced.json()["name"] == "改名了"


def test_a_refused_patch_changes_nothing(client, body_refs):
    made = create(client, **full_body(body_refs))
    response = client.patch(
        f"{EDIT}/{made['id']}",
        json={"name": "新名字", "body": {"lines": [{"new_ingredient": {"name_cn": "紫蘇"}}]}},
    )
    assert response.status_code == 422
    assert client.get(f"{LIST}/{made['id']}").json() == made


def test_delete_removes_the_template(client):
    made = create(client)
    assert client.delete(f"{EDIT}/{made['id']}").status_code == 204
    assert client.get(f"{LIST}/{made['id']}").status_code == 404
    assert client.get(LIST).json() == []


def test_the_order_is_saved_from_the_exact_list(client):
    a, b, c = (create(client, name=n)["id"] for n in "abc")
    response = client.put(f"{EDIT}/order", json={"ids": [c, a, b]})
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [c, a, b]
    assert [row["id"] for row in client.get(LIST).json()] == [c, a, b]


@pytest.mark.parametrize("ids", [lambda a, b, c: [a, b], lambda a, b, c: [a, b, c, 999999], lambda a, b, c: [a, a, b, c]])
def test_an_order_that_is_not_the_current_set_is_refused(client, ids):
    a, b, c = (create(client, name=n)["id"] for n in "abc")
    response = client.put(f"{EDIT}/order", json={"ids": ids(a, b, c)})
    assert response.status_code == 422, response.text
    assert [row["id"] for row in client.get(LIST).json()] == [a, b, c]


# --- stale references --------------------------------------------------------


def test_references_that_no_longer_exist_are_dropped_and_counted(client, db, body_refs):
    refs = body_refs
    made = create(client, **full_body(refs))
    # The mirror first: on the same template, with everything still there,
    # nothing is dropped - so the count below is the deletions' doing.
    assert client.get(f"{LIST}/{made['id']}").json()["dropped"] == 0

    # Nothing in the database points from a template to these rows, so each
    # goes without a refusal.
    for row in (refs["ingredient"], refs["sauce"], refs["method"], refs["main"]):
        db.delete(row)
    db.flush()

    response = client.get(f"{LIST}/{made['id']}")
    assert response.status_code == 200, response.text
    template = response.json()
    # The ingredient line, the sauce line, the method, and the 主料 group.
    assert template["dropped"] == 4
    body = template["body"]
    assert body["lines"] == []
    # A group whose value is gone goes; its lines would have moved to the
    # ungrouped ones, but its only line named the deleted sauce.
    assert [g["display_name"] for g in body["line_groups"]] == ["醃料"]
    assert body["methods"] == []
    assert body["equipment"] == [{"id": refs["pan"].id, "display_name": "炒鍋"}]
    # What still exists is untouched.
    assert [s["body"] for s in body["step_groups"][0]["steps"]] == ["切", "火別太大"]


def test_a_dropped_group_keeps_its_lines_as_ungrouped(client, db, ingredient, line_groups):
    gone = LineGroup(name_cn="要刪的")
    db.add(gone)
    db.flush()
    made = create(
        client,
        lines=[{"ingredient_id": ingredient.id, "amount": "1"}],
        line_groups=[{"line_group_id": gone.id, "lines": [{"ingredient_id": ingredient.id, "amount": "2"}]}],
    )
    db.delete(gone)
    db.flush()
    template = client.get(f"{LIST}/{made['id']}").json()
    assert template["dropped"] == 1
    assert [line["amount"] for line in template["body"]["lines"]] == ["1", "2"]
    assert template["body"]["line_groups"] == []


# --- from a recipe -----------------------------------------------------------


def test_a_template_is_made_from_a_recipes_structure(client, body_refs, source_platforms):
    refs = body_refs
    recipe = client.post(
        "/api/edit/recipes",
        json={
            "new_dish": {"name_cn": "炒青菜"},
            "name": "阿嬤版",
            "servings": "3 人份",
            "time": "10 分鐘",
            "notes": "不帶走",
            "storage_notes": "不帶走",
            "sources": [{"platform_id": source_platforms["YouTube"].id, "title": "影片"}],
            "lines": [{"ingredient_id": refs["ingredient"].id, "amount": "2 片"}],
            "line_groups": [
                {"line_group_id": refs["main"].id, "lines": [{"sub_dish_id": refs["sauce"].id}]},
                {"name": "醃料", "lines": [{"ingredient_id": refs["ingredient"].id, "is_optional": True}]},
            ],
            "steps": [{"body": "洗菜", "kind": "optional"}],
            "step_groups": [
                {"step_group_id": refs["prep"].id, "steps": [{"body": "切"}, {"body": "小心", "kind": "note"}]},
                {"name": "收尾", "steps": [{"body": "盛盤"}]},
            ],
            "method_ids": [refs["method"].id],
            "equipment_ids": [refs["pan"].id],
        },
    ).json()

    response = client.post(f"{EDIT}/from-recipe/{recipe['id']}", json={"name": "炒青菜範本"})
    assert response.status_code == 201, response.text
    template = response.json()
    assert template["name"] == "炒青菜範本"
    assert template["dropped"] == 0
    body = template["body"]
    assert set(body) == {
        "servings", "time", "lines", "line_groups", "steps", "step_groups", "methods", "equipment",
    }
    assert (body["servings"], body["time"]) == ("3 人份", "10 分鐘")
    assert [(line["ingredient"]["id"], line["amount"]) for line in body["lines"]] == [
        (refs["ingredient"].id, "2 片")
    ]
    main, marinade = body["line_groups"]
    assert main["group"]["id"] == refs["main"].id
    assert main["lines"][0]["sub_dish"]["id"] == refs["sauce"].id
    assert (marinade["group"], marinade["name"]) == (None, "醃料")
    assert marinade["lines"][0]["is_optional"] is True
    assert body["steps"] == [{"body": "洗菜", "kind": "optional"}]
    prep, finish = body["step_groups"]
    assert prep["group"]["id"] == refs["prep"].id
    assert [(s["body"], s["kind"]) for s in prep["steps"]] == [("切", "step"), ("小心", "note")]
    assert (finish["name"], [s["body"] for s in finish["steps"]]) == ("收尾", ["盛盤"])
    assert [m["id"] for m in body["methods"]] == [refs["method"].id]
    assert [e["id"] for e in body["equipment"]] == [refs["pan"].id]

    # It is a template like any other: listed, and its name taken.
    assert [row["name"] for row in client.get(LIST).json()] == ["炒青菜範本"]
    again = client.post(f"{EDIT}/from-recipe/{recipe['id']}", json={"name": "炒青菜範本"})
    assert again.status_code == 422


def test_a_template_from_a_missing_recipe_is_404(client):
    response = client.post(f"{EDIT}/from-recipe/999999", json={"name": "x"})
    assert response.status_code == 404


# --- ingredient merge --------------------------------------------------------


def test_an_ingredient_merge_rewrites_the_templates_that_name_it(client, db, fallback_category):
    source = Ingredient(name_cn="青蔥", category_id=fallback_category.id)
    target = Ingredient(name_cn="蔥", category_id=fallback_category.id)
    bystander = Ingredient(name_cn="蒜", category_id=fallback_category.id)
    db.add_all([source, target, bystander])
    db.flush()
    made = create(
        client,
        lines=[{"ingredient_id": source.id, "amount": "1 根"}, {"ingredient_id": bystander.id}],
        line_groups=[{"name": "配料", "lines": [{"ingredient_id": source.id, "note": "切段"}]}],
    )

    preview = client.get(f"/api/ingredients/{source.id}/merge-preview", params={"into": target.id})
    assert preview.status_code == 200, preview.text
    merged = client.post(
        f"/api/edit/ingredients/{source.id}/merge",
        json={"into": target.id, "fingerprint": preview.json()["fingerprint"]},
    )
    assert merged.status_code == 200, merged.text

    template = client.get(f"{LIST}/{made['id']}").json()
    # Without the rewrite both source lines would be dropped as missing.
    assert template["dropped"] == 0
    body = template["body"]
    assert [(line["ingredient"]["id"], line["amount"]) for line in body["lines"]] == [
        (target.id, "1 根"),
        (bystander.id, None),
    ]
    assert [line["ingredient"]["id"] for line in body["line_groups"][0]["lines"]] == [target.id]
    stored = db.get(RecipeTemplate, made["id"])
    db.refresh(stored)
    assert source.id not in {line["ingredient_id"] for line in stored.body["lines"]}
