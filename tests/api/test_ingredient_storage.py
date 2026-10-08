"""Storage with a state and a range, the heating guide, links and rating.

The refusal tests each carry the data that lets them bite: a duplicate
(state, method) needs two rows, an in-use cooking method needs a heating row
pointing at it. Each refusal is paired with the case that must still pass."""

import pytest

from app.models import CookingMethod


@pytest.fixture
def air_fryer(db):
    row = CookingMethod(name_cn="氣炸", sort_order=10)
    db.add(row)
    db.flush()
    return row


def _create(client, category_id, **fields):
    payload = {"name_cn": "香腸", "category_id": category_id, **fields}
    response = client.post("/api/edit/ingredients", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_preservation_row_carries_a_state_and_a_range(client, fallback_category):
    body = _create(
        client,
        fallback_category.id,
        preservation=[
            {"state": "unused", "method": "冷藏", "duration_min_days": 3, "duration_max_days": 5},
            {"state": "opened", "method": "冷藏", "duration_max_days": 2, "notes": "密封"},
        ],
    )
    rows = {(r["state"], r["method"]): r for r in body["preservation"]}
    assert rows[("unused", "冷藏")]["duration_min_days"] == 3
    assert rows[("opened", "冷藏")]["duration_min_days"] is None
    assert rows[("opened", "冷藏")]["duration_max_days"] == 2


def test_state_defaults_to_unused(client, fallback_category):
    body = _create(client, fallback_category.id, preservation=[{"method": "冷凍"}])
    assert body["preservation"][0]["state"] == "unused"


def test_the_same_method_twice_in_one_state_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"method": "冷藏"}, {"method": "冷藏"}],
        },
    )
    assert response.status_code == 422


def test_the_same_method_in_two_states_is_allowed(client, fallback_category):
    body = _create(
        client,
        fallback_category.id,
        preservation=[{"method": "冷藏"}, {"state": "cooked", "method": "冷藏"}],
    )
    assert len(body["preservation"]) == 2


def test_a_minimum_above_the_maximum_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"method": "冷藏", "duration_min_days": 5, "duration_max_days": 3}],
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["duration_min_days", "duration_max_days"])
def test_a_duration_must_be_positive(client, fallback_category, field):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"method": "冷藏", field: 0}],
        },
    )
    assert response.status_code == 422


def test_an_unknown_state_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "豆腐",
            "category_id": fallback_category.id,
            "preservation": [{"state": "frozen-ish", "method": "冷藏"}],
        },
    )
    assert response.status_code == 422


def test_a_heating_row_names_a_method_and_shows_fahrenheit(client, fallback_category, air_fryer):
    body = _create(
        client,
        fallback_category.id,
        heating=[
            {
                "method_id": air_fryer.id,
                "temperature_c": 180,
                "duration": "7 分",
                "preheat": True,
                "flip": True,
            }
        ],
    )
    row = body["heating"][0]
    assert row["method"] == {"id": air_fryer.id, "display_name": "氣炸"}
    assert row["temperature_f"] == 356
    assert row["preheat"] is True and row["flip"] is True


def test_a_heating_row_naming_no_method_is_refused(client, fallback_category):
    response = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "香腸", "category_id": fallback_category.id, "heating": [{"method_id": 999999}]},
    )
    assert response.status_code == 422


def test_the_same_method_may_appear_in_two_heating_rows(client, fallback_category, air_fryer):
    body = _create(
        client,
        fallback_category.id,
        heating=[
            {"method_id": air_fryer.id, "temperature_c": 180},
            {"method_id": air_fryer.id, "temperature_c": 200},
        ],
    )
    assert len(body["heating"]) == 2


def test_a_cooking_method_in_use_by_a_heating_row_cannot_be_deleted(
    client, fallback_category, air_fryer
):
    _create(client, fallback_category.id, heating=[{"method_id": air_fryer.id}])
    response = client.delete(f"/api/edit/cooking-methods/{air_fryer.id}")
    assert response.status_code == 409
    assert response.json()["usage_count"] == 1
    listed = {row["id"]: row for row in client.get("/api/cooking-methods").json()}
    assert listed[air_fryer.id]["usage_count"] == 1


def test_a_link_must_be_http_or_https(client, fallback_category):
    for url in ["javascript:alert(1)", "ftp://x.example/a", "not a url"]:
        response = client.post(
            "/api/edit/ingredients",
            json={"name_cn": "檸檬", "category_id": fallback_category.id, "links": [{"url": url}]},
        )
        assert response.status_code == 422, url


def test_links_keep_their_order(client, fallback_category):
    body = _create(
        client,
        fallback_category.id,
        links=[
            {"url": "https://b.example/", "title": "B"},
            {"url": "https://a.example/", "title": "A"},
        ],
    )
    assert [link["title"] for link in body["links"]] == ["B", "A"]


def test_a_rating_is_one_of_the_fixed_grades(client, fallback_category):
    assert _create(client, fallback_category.id, rating="S")["rating"] == "S"
    response = client.post(
        "/api/edit/ingredients",
        json={"name_cn": "芒果", "category_id": fallback_category.id, "rating": "A+"},
    )
    assert response.status_code == 422


def test_the_library_filters_by_rating_and_by_having_a_parent(client, fallback_category):
    mango = _create(client, fallback_category.id, name_cn="芒果")
    _create(client, fallback_category.id, name_cn="愛文芒果", parent_id=mango["id"], rating="S")
    _create(client, fallback_category.id, name_cn="金煌芒果", parent_id=mango["id"], rating="A")

    graded = client.get("/api/ingredients", params={"rating": "S"}).json()
    assert [row["name_cn"] for row in graded] == ["愛文芒果"]

    varieties = client.get("/api/ingredients", params={"has_parent": "true"}).json()
    assert {row["name_cn"] for row in varieties} == {"愛文芒果", "金煌芒果"}

    roots = client.get("/api/ingredients", params={"has_parent": "false"}).json()
    assert [row["name_cn"] for row in roots] == ["芒果"]


def test_the_library_filters_by_group_at_any_depth(client, fallback_category):
    # 牛肉 and its variety are outside the group: without them the filter
    # would have nothing to leave out, and a group_id ignored outright would
    # still pass.
    chicken = _create(client, fallback_category.id, name_cn="雞肉")
    thigh = _create(client, fallback_category.id, name_cn="雞腿", parent_id=chicken["id"])
    _create(client, fallback_category.id, name_cn="去骨雞腿", parent_id=thigh["id"])
    beef = _create(client, fallback_category.id, name_cn="牛肉")
    _create(client, fallback_category.id, name_cn="牛腱", parent_id=beef["id"])

    group = client.get("/api/ingredients", params={"group_id": chicken["id"]}).json()
    assert {row["name_cn"] for row in group} == {"雞肉", "雞腿", "去骨雞腿"}

    inner = client.get("/api/ingredients", params={"group_id": thigh["id"]}).json()
    assert {row["name_cn"] for row in inner} == {"雞腿", "去骨雞腿"}


def test_the_summary_carries_the_unused_fridge_range(client, fallback_category):
    _create(
        client,
        fallback_category.id,
        preservation=[
            {"state": "opened", "method": "冷藏", "duration_max_days": 1},
            {"state": "unused", "method": "冷藏", "duration_min_days": 5, "duration_max_days": 7},
        ],
    )
    row = client.get("/api/ingredients").json()[0]
    assert row["fridge"] == {"min": 5, "max": 7}


def test_delete_echoes_every_cascaded_count(client, fallback_category, air_fryer):
    body = _create(
        client,
        fallback_category.id,
        heating=[{"method_id": air_fryer.id}],
        links=[{"url": "https://a.example/"}],
    )
    stale = client.delete(
        f"/api/edit/ingredients/{body['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["actual"] == 1

    ok = client.delete(
        f"/api/edit/ingredients/{body['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 1, "links": 1},
    )
    assert ok.status_code == 204


def test_the_fixed_vocabularies_are_served_with_labels(client):
    body = client.get("/api/vocabularies/fixed").json()
    assert {"value": "unused", "label": "未使用"} in body["preservation_states"]
    assert {"value": "冷藏", "label": "冷藏"} in body["preservation_methods"]
    assert [entry["value"] for entry in body["ratings"]] == ["S", "A", "B", "C", "D"]


def test_a_stale_delete_names_which_count_moved(client, fallback_category, air_fryer):
    """Every count is 0 in the dialog and only heating has moved, so matching
    on the number alone could not tell which one to correct."""
    body = _create(client, fallback_category.id, heating=[{"method_id": air_fryer.id}])
    stale = client.delete(
        f"/api/edit/ingredients/{body['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    assert stale.status_code == 409
    assert stale.json()["field"] == "heating"
    assert (stale.json()["expected"], stale.json()["actual"]) == (0, 1)


def test_a_current_delete_with_every_count_matching_succeeds(client, fallback_category, air_fryer):
    body = _create(client, fallback_category.id, heating=[{"method_id": air_fryer.id}])
    ok = client.delete(
        f"/api/edit/ingredients/{body['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 1, "links": 0},
    )
    assert ok.status_code == 204


def test_sort_order_is_not_accepted_on_a_heating_row_or_a_link(
    client, fallback_category, air_fryer
):
    """Order is the list order; a field that is accepted and then overwritten is a lie."""
    heating = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "雞翅",
            "category_id": fallback_category.id,
            "heating": [{"method_id": air_fryer.id, "sort_order": 5}],
        },
    )
    assert heating.status_code == 422
    link = client.post(
        "/api/edit/ingredients",
        json={
            "name_cn": "雞翅",
            "category_id": fallback_category.id,
            "links": [{"url": "https://example.com", "sort_order": 5}],
        },
    )
    assert link.status_code == 422
