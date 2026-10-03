"""A recipe's ingredient lines and steps sit in real groups: per-recipe rows
that name a 設定 value (材料分組 / 步驟分組) or carry a one-off name.

The load-bearing fixtures are the seeded group vocabularies: a one-off name
can only be "stored as the 設定 value" when there is a value to match, and a
delete can only be refused when a recipe group names the value.
"""

import pytest

from app.models import RecipeLine, RecipeLineGroup, RecipeStep

pytestmark = pytest.mark.usefixtures("recipe_statuses")


def create(client, **body):
    body.setdefault("name_cn", "麻婆豆腐")
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_lines_and_steps_save_into_groups_in_order(client, ingredient, line_groups, step_groups):
    main = line_groups["主料"]
    prep = step_groups["備料"]
    body = create(
        client,
        lines=[{"ingredient_id": ingredient.id, "amount": "1 片"}],
        line_groups=[
            {"line_group_id": main.id, "lines": [{"ingredient_id": ingredient.id, "amount": "2"}]},
            {"name": "醃料", "lines": [{"ingredient_id": ingredient.id, "note": "切絲"}]},
        ],
        steps=[{"body": "先看一遍"}],
        step_groups=[
            {"step_group_id": prep.id, "steps": [{"body": "切"}, {"body": "醃"}]},
            {"name": "收尾", "steps": [{"body": "盛盤"}]},
        ],
    )

    assert [line["amount"] for line in body["lines"]] == ["1 片"]
    assert [g["display_name"] for g in body["line_groups"]] == ["主料", "醃料"]
    first, second = body["line_groups"]
    assert first["group"] == {"id": main.id, "display_name": "主料"}
    assert first["name"] is None
    assert first["position"] == 0
    assert [line["amount"] for line in first["lines"]] == ["2"]
    assert second["group"] is None
    assert second["name"] == "醃料"
    assert second["position"] == 1
    assert [line["note"] for line in second["lines"]] == ["切絲"]
    # Positions run through the whole recipe in the order the page shows it:
    # ungrouped first, then group by group.
    every = body["lines"] + first["lines"] + second["lines"]
    assert [line["position"] for line in every] == [0, 1, 2]

    assert [s["body"] for s in body["steps"]] == ["先看一遍"]
    assert [g["display_name"] for g in body["step_groups"]] == ["備料", "收尾"]
    assert body["step_groups"][0]["group"] == {"id": prep.id, "display_name": "備料"}
    assert [s["body"] for s in body["step_groups"][0]["steps"]] == ["切", "醃"]
    steps = body["steps"] + body["step_groups"][0]["steps"] + body["step_groups"][1]["steps"]
    assert [s["position"] for s in steps] == [0, 1, 2, 3]
    assert body["written_up"] is True


def test_a_recipe_with_only_grouped_rows_is_written_up(client, ingredient):
    body = create(client, line_groups=[{"name": "醬汁", "lines": [{"ingredient_id": ingredient.id}]}])
    assert body["lines"] == []
    assert body["written_up"] is True
    listed = client.get("/api/recipes", params={"written_up": "true"}).json()
    assert [r["id"] for r in listed] == [body["id"]]


def test_a_one_off_name_matching_a_setting_value_is_stored_as_that_value(
    client, line_groups, step_groups
):
    body = create(
        client,
        line_groups=[{"name": " 配料 "}],
        step_groups=[{"name": "醬汁"}],
    )
    group = body["line_groups"][0]
    assert group["group"] == {"id": line_groups["配料"].id, "display_name": "配料"}
    assert group["name"] is None
    assert body["step_groups"][0]["group"]["id"] == step_groups["醬汁"].id
    # It counts as a use of the value.
    listed = {row["name_cn"]: row for row in client.get("/api/line-groups").json()}
    assert listed["配料"]["usage_count"] == 1
    assert listed["主料"]["usage_count"] == 0


def test_a_name_matches_case_insensitively_and_by_english_name(client, db):
    from app.models import StepGroup

    sauce = StepGroup(name_cn="醬汁", name_en="Sauce")
    db.add(sauce)
    db.flush()
    body = create(client, step_groups=[{"name": "SAUCE"}])
    assert body["step_groups"][0]["group"]["id"] == sauce.id


def test_an_empty_group_is_kept(client):
    body = create(client, line_groups=[{"name": "裝飾"}], step_groups=[{"name": "擺盤"}])
    assert [(g["display_name"], g["lines"]) for g in body["line_groups"]] == [("裝飾", [])]
    assert [(g["display_name"], g["steps"]) for g in body["step_groups"]] == [("擺盤", [])]
    assert body["written_up"] is False


@pytest.mark.parametrize(
    "groups",
    [
        "same value twice",
        "value and its name",
        "one-off name twice in another case",
    ],
)
def test_a_group_named_twice_in_one_recipe_is_422(client, db, line_groups, groups):
    main = line_groups["主料"].id
    payload = {
        "same value twice": [{"line_group_id": main}, {"line_group_id": main}],
        "value and its name": [{"line_group_id": main}, {"name": "主料"}],
        "one-off name twice in another case": [{"name": "Sauce"}, {"name": "sauce "}],
    }[groups]
    before = db.query(RecipeLineGroup).count()
    response = client.post("/api/edit/recipes", json={"name_cn": "x", "line_groups": payload})
    assert response.status_code == 422, response.text
    assert db.query(RecipeLineGroup).count() == before
    # Mirror: two different groups are fine.
    create(client, line_groups=[{"line_group_id": main}, {"name": "Sauce"}])


@pytest.mark.parametrize(
    "group",
    [{}, {"name": "  "}, {"name": "醬汁", "line_group_id": 1}],
)
def test_a_group_names_exactly_one_of_a_value_or_a_name(client, group):
    response = client.post("/api/edit/recipes", json={"name_cn": "x", "line_groups": [group]})
    assert response.status_code == 422


def test_a_group_naming_a_missing_value_is_422(client, line_groups):
    response = client.post(
        "/api/edit/recipes", json={"name_cn": "x", "step_groups": [{"step_group_id": 999999}]}
    )
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]


def test_a_grouped_line_naming_a_missing_ingredient_is_422(client, ingredient):
    response = client.post(
        "/api/edit/recipes",
        json={"name_cn": "x", "line_groups": [{"name": "a", "lines": [{"ingredient_id": 999999}]}]},
    )
    assert response.status_code == 422


def test_a_new_ingredient_inside_a_group_becomes_a_stub(client, fallback_category):
    body = create(
        client,
        lines=[{"new_ingredient": {"name_cn": "香茅"}}],
        line_groups=[{"name": "湯", "lines": [{"new_ingredient": {"name_cn": "香茅"}}]}],
    )
    grouped = body["line_groups"][0]["lines"][0]
    assert grouped["ingredient"]["needs_detail"] is True
    assert grouped["ingredient"]["id"] == body["lines"][0]["ingredient"]["id"]


def test_a_sub_recipe_inside_a_group_counts_as_used_in(client):
    base = create(client, name_cn="辣油", kind="base")
    dish = create(client, line_groups=[{"name": "醬汁", "lines": [{"sub_recipe_id": base["id"]}]}])
    read = client.get(f"/api/recipes/{base['id']}").json()
    assert [r["id"] for r in read["used_in"]] == [dish["id"]]
    assert client.get(f"/api/recipes/{base['id']}/cascade").json()["used_in"] == 1


def test_patch_replaces_lines_and_their_groups_together(client, ingredient, line_groups):
    created = create(
        client,
        lines=[{"ingredient_id": ingredient.id}],
        line_groups=[{"name": "醬汁", "lines": [{"ingredient_id": ingredient.id}]}],
        steps=[{"body": "one"}],
    )
    body = client.patch(
        f"/api/edit/recipes/{created['id']}",
        json={
            "lines": [],
            "line_groups": [
                {"line_group_id": line_groups["主料"].id, "lines": [{"ingredient_id": ingredient.id}]}
            ],
        },
    ).json()
    assert body["lines"] == []
    assert [g["display_name"] for g in body["line_groups"]] == ["主料"]
    assert len(body["line_groups"][0]["lines"]) == 1
    # Steps were not sent, so they are untouched.
    assert [s["body"] for s in body["steps"]] == ["one"]


@pytest.mark.parametrize(
    "patch",
    [
        {"lines": []},
        {"line_groups": []},
        {"steps": []},
        {"step_groups": []},
        {"lines": [], "line_groups": None},
        {"steps": None, "step_groups": []},
    ],
)
def test_patch_sending_one_of_a_pair_without_the_other_is_422(client, ingredient, patch):
    """A grouped recipe is the fixture: replacing `lines` alone would leave
    the groups' rows behind or drop them, and either is a guess."""
    created = create(
        client,
        line_groups=[{"name": "醬汁", "lines": [{"ingredient_id": ingredient.id}]}],
        step_groups=[{"name": "備料", "steps": [{"body": "切"}]}],
    )
    response = client.patch(f"/api/edit/recipes/{created['id']}", json=patch)
    assert response.status_code == 422, response.text
    read = client.get(f"/api/recipes/{created['id']}").json()
    assert len(read["line_groups"][0]["lines"]) == 1
    assert len(read["step_groups"][0]["steps"]) == 1


def test_re_sending_the_same_groups_does_not_collide_with_itself(client, ingredient, line_groups):
    payload = {
        "lines": [{"ingredient_id": ingredient.id}],
        "line_groups": [
            {"line_group_id": line_groups["主料"].id, "lines": [{"ingredient_id": ingredient.id}]},
            {"name": "醬汁", "lines": [{"ingredient_id": ingredient.id}]},
        ],
        "steps": [{"body": "a"}],
        "step_groups": [{"name": "備料", "steps": [{"body": "b"}]}, {"name": "烹飪"}],
    }
    created = create(client, **payload)
    for _ in range(2):
        response = client.patch(f"/api/edit/recipes/{created['id']}", json=payload)
        assert response.status_code == 200, response.text
    body = response.json()
    assert [g["display_name"] for g in body["line_groups"]] == ["主料", "醬汁"]
    assert [g["display_name"] for g in body["step_groups"]] == ["備料", "烹飪"]


def test_the_delete_dialog_counts_grouped_rows_and_the_delete_takes_the_groups(
    client, db, ingredient
):
    created = create(
        client,
        lines=[{"ingredient_id": ingredient.id}],
        line_groups=[{"name": "醬汁", "lines": [{"ingredient_id": ingredient.id}] * 2}],
        step_groups=[{"name": "備料", "steps": [{"body": "a"}, {"body": "b"}]}],
    )
    counts = client.get(f"/api/recipes/{created['id']}/cascade").json()
    assert counts == {"aliases": 0, "sources": 0, "lines": 3, "steps": 2, "used_in": 0}

    stale = {"aliases": 0, "sources": 0, "lines": 1, "steps": 2}
    response = client.delete(f"/api/edit/recipes/{created['id']}", params=stale)
    assert response.status_code == 409
    assert response.json()["field"] == "lines"

    params = {k: counts[k] for k in ("aliases", "sources", "lines", "steps")}
    assert client.delete(f"/api/edit/recipes/{created['id']}", params=params).status_code == 204
    assert db.query(RecipeLineGroup).filter_by(recipe_id=created["id"]).count() == 0
    assert db.query(RecipeLine).filter_by(recipe_id=created["id"]).count() == 0
    assert db.query(RecipeStep).filter_by(recipe_id=created["id"]).count() == 0


def test_a_group_value_a_recipe_uses_cannot_be_deleted(client, line_groups, step_groups):
    """The recipe group naming 主料 / 備料 is the fixture that makes the 409
    bite; 配料 / 烹飪, which nothing uses, are the mirror and delete."""
    create(
        client,
        line_groups=[{"line_group_id": line_groups["主料"].id}],
        step_groups=[{"step_group_id": step_groups["備料"].id}],
    )
    for resource, used, unused in [
        ("line-groups", line_groups["主料"], line_groups["配料"]),
        ("step-groups", step_groups["備料"], step_groups["烹飪"]),
    ]:
        listed = {row["id"]: row for row in client.get(f"/api/{resource}").json()}
        assert listed[used.id]["usage_count"] == 1
        response = client.delete(f"/api/edit/{resource}/{used.id}")
        assert response.status_code == 409
        assert response.json()["usage_count"] == 1
        assert client.delete(f"/api/edit/{resource}/{unused.id}").status_code == 204


def test_renaming_a_value_renames_every_group_using_it(client, line_groups):
    created = create(client, line_groups=[{"line_group_id": line_groups["主料"].id}])
    client.patch(f"/api/edit/line-groups/{line_groups['主料'].id}", json={"name_cn": "主材料"})
    read = client.get(f"/api/recipes/{created['id']}").json()
    assert read["line_groups"][0]["display_name"] == "主材料"


def test_group_values_list_in_their_seeded_order(client, line_groups, step_groups):
    assert [r["display_name"] for r in client.get("/api/line-groups").json()] == [
        "主料",
        "配料",
        "調味料",
    ]
    assert [r["display_name"] for r in client.get("/api/step-groups").json()] == [
        "備料",
        "烹飪",
        "醬汁",
    ]


def test_a_cycle_through_a_grouped_line_is_refused(client):
    a = create(client, name_cn="A")
    b = create(client, name_cn="B", line_groups=[{"name": "底", "lines": [{"sub_recipe_id": a["id"]}]}])
    response = client.patch(
        f"/api/edit/recipes/{a['id']}",
        json={"lines": [], "line_groups": [{"name": "x", "lines": [{"sub_recipe_id": b["id"]}]}]},
    )
    assert response.status_code == 422
    assert client.get(f"/api/recipes/{a['id']}").json()["line_groups"] == []


def test_deleting_a_recipe_group_leaves_its_rows_ungrouped(client, db, ingredient):
    """`group_id` is SET NULL: the database says what the form's 移除分組 says -
    a group's rows outlive it, in the ungrouped area."""
    created = create(client, line_groups=[{"name": "醬汁", "lines": [{"ingredient_id": ingredient.id}]}])
    group = db.query(RecipeLineGroup).filter_by(recipe_id=created["id"]).one()
    db.delete(group)
    db.flush()
    db.expire_all()
    read = client.get(f"/api/recipes/{created['id']}").json()
    assert read["line_groups"] == []
    assert [line["ingredient"]["id"] for line in read["lines"]] == [ingredient.id]
