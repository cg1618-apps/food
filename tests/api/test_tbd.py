"""TBD: a standalone page of notes - an optional name and any number of links.

Nothing in it relates to the rest of the app. The refusals each set up the
thing they refuse and have a mirror that commits: the name-or-link rule is
asserted with an entry that HAS a link and loses it, and the reorder 422s with
three real entries, so an empty table cannot make them pass vacuously.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import TbdEntry, TbdLink

URL = "/api/tbd"
EDIT_URL = "/api/edit/tbd"


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
    """Three entries, in creation order - what the order tests reorder."""
    return [
        create(client, name="一")["id"],
        create(client, name="二")["id"],
        create(client, links=[{"url": "https://example.com/3"}])["id"],
    ]


# --- the model ---------------------------------------------------------------


def test_a_blank_link_url_is_refused_by_the_database(db):
    entry = TbdEntry(name="x", sort_order=0)
    db.add(entry)
    db.flush()
    db.add(TbdLink(entry_id=entry.id, position=0, url="   "))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_tbd_link_has_a_url" in str(excinfo.value)


def test_deleting_an_entry_cascades_to_its_links(db):
    entry = TbdEntry(name="x", sort_order=0)
    entry.links = [TbdLink(position=0, url="https://a.example"), TbdLink(position=1, url="https://b.example")]
    db.add(entry)
    db.flush()
    entry_id = entry.id
    db.expire_all()
    assert db.query(TbdLink).filter_by(entry_id=entry_id).count() == 2

    db.delete(db.get(TbdEntry, entry_id))
    db.flush()
    assert db.query(TbdLink).count() == 0


# --- the round trip ----------------------------------------------------------


def test_the_page_starts_empty(client):
    assert listed(client) == []


def test_an_entry_round_trips(client):
    created = create(
        client,
        name="想試的店",
        links=[
            {"url": "https://example.com/a", "label": "甲"},
            {"url": "https://example.com/b"},
        ],
    )
    assert created["name"] == "想試的店"
    assert [(link["url"], link["label"]) for link in created["links"]] == [
        ("https://example.com/a", "甲"),
        ("https://example.com/b", None),
    ]
    assert all(isinstance(link["id"], int) for link in created["links"])
    assert listed(client) == [created]
    assert set(created) == {"id", "name", "links", "sort_order"}


def test_a_name_alone_is_an_entry(client):
    assert create(client, name="只有名字")["links"] == []


def test_links_alone_are_an_entry(client):
    assert create(client, links=[{"url": "https://example.com"}])["name"] is None


def test_an_entry_with_neither_is_422_in_the_app_error_shape(client):
    for body in ({}, {"name": "   ", "links": []}, {"name": None}):
        response = client.post(EDIT_URL, json=body)
        assert response.status_code == 422, body
        assert isinstance(response.json()["detail"], str)
    assert listed(client) == []


def test_a_patch_that_would_leave_neither_is_422_and_changes_nothing(client):
    entry = create(client, links=[{"url": "https://example.com"}])
    response = client.patch(f"{EDIT_URL}/{entry['id']}", json={"links": []})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert listed(client)[0]["links"][0]["url"] == "https://example.com"

    # The mirror: the same PATCH with a name kept is fine.
    response = client.patch(f"{EDIT_URL}/{entry['id']}", json={"name": "留著", "links": []})
    assert response.status_code == 200, response.text
    assert response.json()["links"] == []


def test_a_new_entry_goes_last(client, three):
    created = create(client, name="四")
    assert [row["id"] for row in listed(client)] == [*three, created["id"]]
    assert created["sort_order"] > max(row["sort_order"] for row in listed(client)[:3])


# --- links ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed, stored",
    [
        ("example.com/x", "https://example.com/x"),
        ("  www.example.com  ", "https://www.example.com"),
        ("localhost:8000/a", "https://localhost:8000/a"),
        ("http://example.com", "http://example.com"),
        ("https://example.com/y?z=1", "https://example.com/y?z=1"),
    ],
)
def test_a_link_without_a_scheme_is_stored_as_https(client, typed, stored):
    entry = create(client, links=[{"url": typed}])
    assert entry["links"][0]["url"] == stored


@pytest.mark.parametrize("url", ["", "   ", "javascript:alert(1)", "ftp://example.com", "https://"])
def test_a_blank_or_non_web_link_is_422(client, url):
    response = client.post(EDIT_URL, json={"name": "x", "links": [{"url": url}]})
    assert response.status_code == 422, url
    assert listed(client) == []


def test_a_blank_label_is_stored_as_none(client):
    entry = create(client, links=[{"url": "example.com", "label": "  "}])
    assert entry["links"][0]["label"] is None


def test_a_patch_replaces_the_links_wholesale_and_keeps_the_order_sent(client, db):
    entry = create(client, name="店", links=[{"url": "a.example"}, {"url": "b.example"}])
    response = client.patch(
        f"{EDIT_URL}/{entry['id']}",
        json={"links": [{"url": "c.example", "label": "丙"}, {"url": "a.example"}]},
    )
    assert response.status_code == 200, response.text
    assert [link["url"] for link in response.json()["links"]] == [
        "https://c.example",
        "https://a.example",
    ]
    assert db.query(TbdLink).count() == 2
    assert response.json()["name"] == "店"


def test_a_patch_without_links_leaves_them_alone(client):
    entry = create(client, name="店", links=[{"url": "a.example"}])
    response = client.patch(f"{EDIT_URL}/{entry['id']}", json={"name": "新店名"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "新店名"
    assert [link["url"] for link in response.json()["links"]] == ["https://a.example"]


def test_a_patch_may_clear_the_name_when_links_remain(client):
    entry = create(client, name="店", links=[{"url": "a.example"}])
    response = client.patch(f"{EDIT_URL}/{entry['id']}", json={"name": None})
    assert response.status_code == 200, response.text
    assert response.json()["name"] is None


def test_the_body_refuses_extra_fields(client):
    assert client.post(EDIT_URL, json={"name": "x", "notes": "y"}).status_code == 422
    assert (
        client.post(EDIT_URL, json={"name": "x", "links": [{"url": "a.example", "x": 1}]}).status_code
        == 422
    )


def test_an_unknown_entry_is_404(client):
    assert client.patch(f"{EDIT_URL}/999999", json={"name": "x"}).status_code == 404
    assert client.delete(f"{EDIT_URL}/999999").status_code == 404


# --- delete ----------------------------------------------------------------------


def test_delete_removes_the_entry_and_its_links(client, db, three):
    entry = create(client, name="刪", links=[{"url": "a.example"}, {"url": "b.example"}])
    assert db.query(TbdLink).count() == 3
    response = client.delete(f"{EDIT_URL}/{entry['id']}")
    assert response.status_code == 204
    assert [row["id"] for row in listed(client)] == three
    # The other entry's link survives; only the deleted entry's went.
    assert db.query(TbdLink).count() == 1


# --- order -----------------------------------------------------------------------


def put_order(client, ids):
    return client.put(f"{EDIT_URL}/order", json={"ids": ids})


def test_the_order_is_saved_as_sent(client, three):
    one, two, three_ = three
    response = put_order(client, [three_, one, two])
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [three_, one, two]
    assert [row["id"] for row in listed(client)] == [three_, one, two]
    assert [row["sort_order"] for row in listed(client)] == [0, 1, 2]


def test_ties_in_sort_order_fall_back_to_id(client, db, three):
    for row in db.query(TbdEntry):
        row.sort_order = 5
    db.flush()
    assert [row["id"] for row in listed(client)] == sorted(three)


@pytest.mark.parametrize(
    "ids",
    [
        lambda ids: ids[:2],  # one missing
        lambda ids: [*ids, 999999],  # one unknown
        lambda ids: [ids[0], ids[0], ids[1]],  # a repeat
        lambda ids: [ids[0], ids[1], 999999],  # right length, wrong id
    ],
)
def test_an_order_that_is_not_exactly_the_current_ids_is_422(client, three, ids):
    response = put_order(client, ids(three))
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert [row["id"] for row in listed(client)] == three


def test_writes_are_behind_the_edit_prefix_only(client, three):
    assert client.post(URL, json={"name": "x"}).status_code == 405
    assert client.put(f"{URL}/order", json={"ids": three}).status_code in (404, 405)
