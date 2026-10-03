"""加熱: a standalone page of heating notes - a name and an optional body each.

Nothing in it relates to the rest of the app. The refusals each set up the
thing they refuse and have a mirror that commits: the blank-name PATCH is
refused on a note that exists and the same PATCH with a name succeeds, and the
reorder 422s with three real notes, so an empty table cannot make them pass
vacuously.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import HeatingNote

URL = "/api/heating"
EDIT_URL = "/api/edit/heating"


def create(client, **body):
    response = client.post(EDIT_URL, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def listed(client):
    response = client.get(URL)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def three(client):
    """Three notes, in creation order - what the order tests reorder."""
    return [
        create(client, name="冷凍吐司", body="烤箱 180 度 5 分鐘")["id"],
        create(client, name="香腸")["id"],
        create(client, name="便當", body="微波 2 分鐘\n蓋子打開一角")["id"],
    ]


# --- the model ---------------------------------------------------------------


def test_a_blank_name_is_refused_by_the_database(db):
    db.add(HeatingNote(name="   ", sort_order=0))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_heating_note_has_a_name" in str(excinfo.value)


# --- the round trip ----------------------------------------------------------


def test_the_page_starts_empty(client):
    assert listed(client) == []


def test_a_note_round_trips_with_its_line_breaks(client):
    created = create(client, name=" 冷凍水餃 ", body="水滾下鍋\n浮起再煮 3 分鐘")
    assert created["name"] == "冷凍水餃"
    assert created["body"] == "水滾下鍋\n浮起再煮 3 分鐘"
    assert listed(client) == [created]
    assert set(created) == {"id", "name", "body", "sort_order"}


def test_a_name_alone_is_a_note_and_a_blank_body_is_none(client):
    assert create(client, name="只有名字")["body"] is None
    assert create(client, name="空白內容", body="   ")["body"] is None


@pytest.mark.parametrize("body", [{}, {"name": "   "}, {"name": None}, {"body": "微波"}])
def test_a_note_without_a_name_is_422(client, body):
    response = client.post(EDIT_URL, json=body)
    assert response.status_code == 422, body
    assert listed(client) == []


def test_a_patch_that_blanks_the_name_is_422_and_changes_nothing(client):
    note = create(client, name="香腸", body="平底鍋")
    for body in ({"name": ""}, {"name": None}):
        response = client.patch(f"{EDIT_URL}/{note['id']}", json=body)
        assert response.status_code == 422, body
    assert listed(client)[0]["name"] == "香腸"

    # The mirror: the same PATCH with a name is fine.
    response = client.patch(f"{EDIT_URL}/{note['id']}", json={"name": "熱狗"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "熱狗"


def test_a_patch_applies_only_what_was_sent(client):
    note = create(client, name="香腸", body="平底鍋")
    response = client.patch(f"{EDIT_URL}/{note['id']}", json={"body": "氣炸鍋 200 度 8 分鐘"})
    assert response.json() == {**note, "body": "氣炸鍋 200 度 8 分鐘"}

    response = client.patch(f"{EDIT_URL}/{note['id']}", json={"body": ""})
    assert response.json()["body"] is None
    assert response.json()["name"] == "香腸"


def test_a_new_note_goes_last(client, three):
    created = create(client, name="四")
    assert [row["id"] for row in listed(client)] == [*three, created["id"]]


def test_the_body_refuses_extra_fields(client):
    response = client.post(EDIT_URL, json={"name": "x", "sort_order": 3})
    assert response.status_code == 422


def test_an_unknown_note_is_404(client):
    for method in ("patch", "delete"):
        kwargs = {"json": {"name": "x"}} if method == "patch" else {}
        response = getattr(client, method)(f"{EDIT_URL}/9999", **kwargs)
        assert response.status_code == 404, method
        assert isinstance(response.json()["detail"], str)


def test_delete_removes_only_that_note(client, three):
    response = client.delete(f"{EDIT_URL}/{three[1]}")
    assert response.status_code == 204
    assert [row["id"] for row in listed(client)] == [three[0], three[2]]


# --- the order -----------------------------------------------------------------


def put_order(client, ids):
    return client.put(f"{EDIT_URL}/order", json={"ids": ids})


def test_the_order_is_saved_as_sent(client, three):
    wanted = [three[2], three[0], three[1]]
    response = put_order(client, wanted)
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == wanted
    assert [row["id"] for row in listed(client)] == wanted


@pytest.mark.parametrize(
    "pick",
    [
        lambda ids: ids[:2],  # one missing
        lambda ids: [*ids, ids[0]],  # one twice
        lambda ids: [*ids, 9999],  # one unknown
        lambda ids: [],  # none
    ],
)
def test_an_order_that_is_not_exactly_the_current_ids_is_422(client, three, pick):
    response = put_order(client, pick(three))
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert [row["id"] for row in listed(client)] == three


def test_writes_are_behind_the_edit_prefix_only(client, three):
    assert client.post(URL, json={"name": "x"}).status_code == 405
    assert client.patch(f"{URL}/{three[0]}", json={"name": "x"}).status_code in (404, 405)
    assert client.delete(f"{URL}/{three[0]}").status_code in (404, 405)
