"""An author's links and remark (備註).

An author is one of the nine factory vocabularies, and the parametrised suite
in test_vocabularies.py covers what it shares with the other eight. What only
an author has is here: `notes`, and `links` in `author_link`, whose rules are
`tbd_link`'s.

The refusals each set up what they refuse and have a mirror that commits: the
url refusals are made on an author that would otherwise save, and the
read-back proves nothing was written; the cascade deletes an author that
really has links; the "only authors" refusal has an author accepting the same
body.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Author, AuthorLink

URL = "/api/authors"
EDIT_URL = "/api/edit/authors"


def create(client, **body):
    response = client.post(EDIT_URL, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def listed(client):
    response = client.get(URL)
    assert response.status_code == 200, response.text
    return response.json()


# --- the model ---------------------------------------------------------------


def test_a_blank_link_url_is_refused_by_the_database(db):
    author = Author(name_cn="阿基師")
    db.add(author)
    db.flush()
    db.add(AuthorLink(author_id=author.id, position=0, url="   "))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_author_link_has_a_url" in str(excinfo.value)


def test_deleting_an_author_cascades_to_its_links(db):
    author = Author(name_cn="阿基師")
    author.links = [
        AuthorLink(position=0, url="https://a.example"),
        AuthorLink(position=1, url="https://b.example"),
    ]
    db.add(author)
    db.flush()
    author_id = author.id
    db.expire_all()
    # The links are there: without them the count below proves nothing.
    assert db.query(AuthorLink).filter_by(author_id=author_id).count() == 2

    db.delete(db.get(Author, author_id))
    db.flush()
    assert db.query(AuthorLink).count() == 0


# --- the round trip ----------------------------------------------------------


def test_an_author_round_trips_its_notes_and_links_in_order(client):
    created = create(
        client,
        name_cn="阿基師",
        notes="台菜。\n\n影片比食譜詳細。",
        links=[
            {"url": "https://youtube.com/@a", "label": "YouTube"},
            {"url": "blog.example/a"},
        ],
    )
    assert created["notes"] == "台菜。\n\n影片比食譜詳細。"
    assert created["links"] == [
        {"label": "YouTube", "url": "https://youtube.com/@a"},
        {"label": None, "url": "https://blog.example/a"},
    ]
    (row,) = listed(client)
    assert row["notes"] == created["notes"]
    assert row["links"] == created["links"]


def test_an_author_with_neither_reads_as_null_and_empty(client):
    created = create(client, name_cn="阿基師")
    assert created["notes"] is None
    assert created["links"] == []


def test_a_blank_remark_is_stored_as_none_and_outer_space_trimmed(client):
    assert create(client, name_cn="甲", notes="  \n ")["notes"] is None
    assert create(client, name_cn="乙", notes="  一\n二  ")["notes"] == "一\n二"


@pytest.mark.parametrize(
    "typed, stored",
    [
        ("example.com/x", "https://example.com/x"),
        ("  www.example.com  ", "https://www.example.com"),
        ("http://example.com", "http://example.com"),
    ],
)
def test_a_link_without_a_scheme_is_stored_as_https(client, typed, stored):
    author = create(client, name_cn="甲", links=[{"url": typed}])
    assert author["links"][0]["url"] == stored


@pytest.mark.parametrize("url", ["", "   ", "javascript:alert(1)", "ftp://example.com", "https://"])
def test_a_blank_or_non_web_link_is_422_and_nothing_is_written(client, url):
    response = client.post(EDIT_URL, json={"name_cn": "甲", "links": [{"url": url}]})
    assert response.status_code == 422, url
    # The mirror: the same body with a web link saves, so the 422 above was
    # the url and not the name.
    assert listed(client) == []
    create(client, name_cn="甲", links=[{"url": "example.com"}])


def test_a_patch_refuses_a_javascript_link_and_keeps_the_stored_ones(client):
    author = create(client, name_cn="甲", links=[{"url": "a.example"}])
    response = client.patch(
        f"{EDIT_URL}/{author['id']}", json={"links": [{"url": "javascript:alert(1)"}]}
    )
    assert response.status_code == 422
    assert [link["url"] for link in listed(client)[0]["links"]] == ["https://a.example"]


def test_a_blank_label_is_stored_as_none(client):
    author = create(client, name_cn="甲", links=[{"url": "example.com", "label": "  "}])
    assert author["links"][0]["label"] is None


def test_a_patch_replaces_the_links_wholesale_and_keeps_the_order_sent(client, db):
    author = create(client, name_cn="甲", links=[{"url": "a.example"}, {"url": "b.example"}])
    response = client.patch(
        f"{EDIT_URL}/{author['id']}",
        json={"links": [{"url": "c.example", "label": "丙"}, {"url": "a.example"}]},
    )
    assert response.status_code == 200, response.text
    assert [link["url"] for link in response.json()["links"]] == [
        "https://c.example",
        "https://a.example",
    ]
    assert db.query(AuthorLink).count() == 2
    assert response.json()["name_cn"] == "甲"


def test_a_patch_without_links_or_notes_leaves_them_alone(client):
    author = create(client, name_cn="甲", notes="備註", links=[{"url": "a.example"}])
    response = client.patch(f"{EDIT_URL}/{author['id']}", json={"name_cn": "乙"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "乙"
    assert body["notes"] == "備註"
    assert [link["url"] for link in body["links"]] == ["https://a.example"]


def test_a_patch_clears_the_links_with_an_empty_list_and_refuses_null(client, db):
    author = create(client, name_cn="甲", links=[{"url": "a.example"}])
    refused = client.patch(f"{EDIT_URL}/{author['id']}", json={"links": None})
    assert refused.status_code == 422
    assert db.query(AuthorLink).count() == 1

    cleared = client.patch(f"{EDIT_URL}/{author['id']}", json={"links": []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["links"] == []
    assert db.query(AuthorLink).count() == 0


def test_a_patch_clears_the_remark_with_null_or_blank(client):
    author = create(client, name_cn="甲", notes="備註")
    response = client.patch(f"{EDIT_URL}/{author['id']}", json={"notes": " "})
    assert response.status_code == 200, response.text
    assert response.json()["notes"] is None


def test_a_link_refuses_extra_fields(client):
    response = client.post(
        EDIT_URL, json={"name_cn": "甲", "links": [{"url": "a.example", "position": 3}]}
    )
    assert response.status_code == 422


def test_deleting_an_unused_author_takes_its_links(client, db):
    author = create(client, name_cn="甲", links=[{"url": "a.example"}, {"url": "b.example"}])
    assert db.query(AuthorLink).count() == 2
    assert client.delete(f"{EDIT_URL}/{author['id']}").status_code == 204
    assert db.query(AuthorLink).count() == 0


# --- only authors ------------------------------------------------------------


@pytest.mark.parametrize("field, value", [("notes", "x"), ("links", [])])
def test_the_other_vocabularies_do_not_take_notes_or_links(client, field, value):
    """The other eight keep their own shape. The author is the mirror: the
    same field on the same factory's route is accepted there."""
    assert client.post("/api/edit/equipment", json={"name_cn": "鍋", field: value}).status_code == 422
    assert client.post(EDIT_URL, json={"name_cn": "鍋", field: value}).status_code == 201


def test_the_other_vocabularies_do_not_answer_with_notes_or_links(client):
    client.post("/api/edit/equipment", json={"name_cn": "鍋"})
    (row,) = client.get("/api/equipment").json()
    assert "notes" not in row and "links" not in row
