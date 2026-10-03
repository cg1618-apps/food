"""A step has a kind: an ordinary numbered step, an optional one, or a note
among the steps. The kind is a fixed list, validated by the schema."""

import pytest

pytestmark = pytest.mark.usefixtures("recipe_statuses")


def create(client, **body):
    body.setdefault("name_cn", "麻婆豆腐")
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_step_without_a_kind_is_an_ordinary_step(client):
    body = create(client, steps=[{"body": "煮"}])
    assert body["steps"][0]["kind"] == "step"


def test_kinds_round_trip_through_create_read_and_patch(client):
    created = create(
        client,
        steps=[{"body": "切", "kind": "step"}, {"body": "可加蔥", "kind": "optional"}],
        step_groups=[{"name": "烹飪", "steps": [{"body": "火別太大", "kind": "note"}]}],
    )
    read = client.get(f"/api/recipes/{created['id']}").json()
    assert [s["kind"] for s in read["steps"]] == ["step", "optional"]
    assert [s["kind"] for s in read["step_groups"][0]["steps"]] == ["note"]

    patched = client.patch(
        f"/api/edit/recipes/{created['id']}",
        json={"steps": [{"body": "切", "kind": "note"}, {"body": "煮"}], "step_groups": []},
    )
    assert patched.status_code == 200, patched.text
    assert [s["kind"] for s in patched.json()["steps"]] == ["note", "step"]


@pytest.mark.parametrize("kind", ["tip", "", None, "STEP"])
def test_an_unknown_kind_is_refused(client, kind):
    response = client.post(
        "/api/edit/recipes", json={"name_cn": "x", "steps": [{"body": "煮", "kind": kind}]}
    )
    assert response.status_code == 422


def test_the_step_kinds_are_served_as_a_fixed_vocabulary(client):
    body = client.get("/api/vocabularies/fixed").json()
    assert body["step_kinds"] == [
        {"value": "step", "label": "步驟"},
        {"value": "optional", "label": "可省略"},
        {"value": "note", "label": "備註"},
    ]
