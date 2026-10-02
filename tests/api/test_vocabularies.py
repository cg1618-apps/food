"""The three managed vocabularies share one router factory, so one parametrised
suite covers all three. The fixtures that make refusals bite are the in-use
rows: a vocabulary value nothing uses deletes freely, and that is the mirror."""

import pytest

RESOURCES = ["recipe-courses", "cooking-methods", "equipment"]


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_vocabulary_value_can_be_created_listed_renamed_and_deleted(client, resource):
    created = client.post(f"/api/edit/{resource}", json={"name_cn": "測試", "sort_order": 5})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["display_name"] == "測試"
    assert body["usage_count"] == 0

    listed = client.get(f"/api/{resource}").json()
    assert [row["name_cn"] for row in listed] == ["測試"]

    renamed = client.patch(
        f"/api/edit/{resource}/{body['id']}", json={"name_cn": "改名", "name_en": "renamed"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["display_name"] == "改名"

    deleted = client.delete(f"/api/edit/{resource}/{body['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/{resource}").json() == []


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_vocabulary_value_needs_a_name(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "  "}).status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_two_values_may_not_share_an_english_name_case_insensitively(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_en": "Pan"}).status_code == 201
    assert client.post(f"/api/edit/{resource}", json={"name_en": "pan"}).status_code == 409


@pytest.mark.parametrize("resource", RESOURCES)
def test_any_number_of_values_may_leave_the_english_name_empty(client, resource):
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "甲"}).status_code == 201
    assert client.post(f"/api/edit/{resource}", json={"name_cn": "乙"}).status_code == 201


@pytest.mark.parametrize("resource", RESOURCES)
def test_renaming_away_every_name_is_refused(client, resource):
    row = client.post(f"/api/edit/{resource}", json={"name_cn": "甲"}).json()
    response = client.patch(f"/api/edit/{resource}/{row['id']}", json={"name_cn": None})
    assert response.status_code == 422


@pytest.mark.parametrize("resource", RESOURCES)
def test_an_unknown_id_is_404(client, resource):
    assert client.patch(f"/api/edit/{resource}/999999", json={"name_cn": "x"}).status_code == 404
    assert client.delete(f"/api/edit/{resource}/999999").status_code == 404


def test_values_list_in_sort_order_then_name(client):
    client.post("/api/edit/equipment", json={"name_cn": "乙", "sort_order": 1})
    client.post("/api/edit/equipment", json={"name_cn": "甲", "sort_order": 2})
    client.post("/api/edit/equipment", json={"name_cn": "丙", "sort_order": 1})
    names = [row["name_cn"] for row in client.get("/api/equipment").json()]
    assert names == ["丙", "乙", "甲"]
