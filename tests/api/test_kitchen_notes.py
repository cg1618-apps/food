"""Kitchen notes: the model's constraints, the round trip, the list, the gallery.

A note is a bookmark - a title, a kind, a link, a body, labels and pictures.
Every refusal test sets up the thing it refuses and has a mirror that commits,
and the two refusals a database backstop would ALSO answer (an unknown label
is a foreign-key 422; an attached picture is a RESTRICT 409) assert on what
only the service says - the id in the detail, the owner on the body - so a
green proves the service refused rather than the constraint behind it.
"""

import io

import pytest
from PIL import Image as PILImage
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from app import config
from app.models import Image, KitchenNote, KitchenNoteImage, KitchenNoteLabel, Label


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "image_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def labels(db):
    """Two labels, so a label list has something real to name beside the
    unknown id - the set the 422 refuses from is not empty."""
    rows = [Label(name_cn="影片"), Label(name_cn="刀工")]
    db.add_all(rows)
    db.flush()
    return rows


def create(client, **body):
    body.setdefault("title", "十種切洋蔥的方法")
    response = client.post("/api/edit/kitchen-notes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def titles(client, **params):
    response = client.get("/api/kitchen-notes", params=params)
    assert response.status_code == 200, response.text
    return [row["title"] for row in response.json()]


def _png(colour=(200, 120, 40, 255)) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGBA", (64, 48), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(client, colour=(200, 120, 40, 255)):
    response = client.post(
        "/api/edit/images", files={"file": ("note.png", _png(colour), "image/png")}
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def _image_row(db, checksum="a" * 64):
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


# --- the model ---------------------------------------------------------------


def test_a_note_with_a_blank_title_is_refused_by_the_database(db):
    db.add(KitchenNote(title="   "))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "ck_kitchen_note_has_a_title" in str(excinfo.value)


def test_a_note_with_a_title_commits_and_defaults_to_a_reference(db):
    note = KitchenNote(title="醬油比較")
    db.add(note)
    db.flush()
    db.refresh(note)
    assert note.kind == "reference"
    assert note.display_name == "醬油比較"


def test_two_notes_may_share_a_title(db):
    db.add_all([KitchenNote(title="合輯"), KitchenNote(title="合輯")])
    db.flush()
    assert db.query(KitchenNote).filter_by(title="合輯").count() == 2


def test_an_image_may_appear_once_in_a_note_gallery(db):
    note = KitchenNote(title="擺盤")
    db.add(note)
    image = _image_row(db)
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=image.id, position=0))
    db.flush()
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=image.id, position=1))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_kitchen_note_image_once" in str(excinfo.value)


def test_two_images_may_not_share_a_note_gallery_position(db):
    note = KitchenNote(title="擺盤")
    db.add(note)
    one, two = _image_row(db, "a" * 64), _image_row(db, "b" * 64)
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=one.id, position=0))
    db.flush()
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=two.id, position=0))
    with pytest.raises(IntegrityError) as excinfo:
        db.flush()
    assert "uq_kitchen_note_image_position" in str(excinfo.value)


def test_two_images_at_different_positions_share_a_note_gallery(db):
    """The mirror of both gallery refusals: distinct images, distinct positions."""
    note = KitchenNote(title="擺盤")
    db.add(note)
    one, two = _image_row(db, "a" * 64), _image_row(db, "b" * 64)
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=one.id, position=0))
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=two.id, position=1))
    db.flush()


def test_deleting_a_note_takes_its_links_and_leaves_labels_and_pictures(db, labels):
    note = KitchenNote(title="擺盤")
    note.labels.append(labels[0])
    db.add(note)
    db.flush()
    image = _image_row(db)
    db.add(KitchenNoteImage(kitchen_note_id=note.id, image_id=image.id, position=0))
    db.flush()
    note_id = note.id
    db.expire_all()

    db.delete(db.get(KitchenNote, note_id))
    db.flush()

    assert db.query(KitchenNoteLabel).count() == 0
    assert db.query(KitchenNoteImage).count() == 0
    assert db.get(Label, labels[0].id) is not None
    assert db.get(Image, image.id) is not None


def test_a_label_on_a_note_can_be_deleted(db, labels):
    note = KitchenNote(title="擺盤")
    note.labels.append(labels[0])
    db.add(note)
    db.flush()
    db.delete(labels[0])
    db.flush()
    db.expire_all()
    assert db.get(KitchenNote, note.id).labels == []


# --- the round trip -------------------------------------------------------------


def test_a_note_round_trips_through_create_read_update_delete(client, labels):
    created = create(
        client,
        title="十種切洋蔥的方法",
        kind="technique",
        url="https://example.com/onion",
        body="第三種最快",
        label_ids=[labels[0].id, labels[1].id],
    )
    read = client.get(f"/api/kitchen-notes/{created['id']}").json()
    assert read["title"] == "十種切洋蔥的方法"
    assert read["kind"] == "technique"
    assert read["url"] == "https://example.com/onion"
    assert read["body"] == "第三種最快"
    assert sorted(x["display_name"] for x in read["labels"]) == ["刀工", "影片"]
    assert read["images"] == []
    assert read["created_at"] is not None

    updated = client.patch(
        f"/api/edit/kitchen-notes/{created['id']}",
        json={"body": None, "label_ids": [labels[1].id]},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["body"] is None
    assert [x["display_name"] for x in body["labels"]] == ["刀工"]
    assert body["url"] == "https://example.com/onion"  # not sent, untouched

    # A PATCH that does not send label_ids leaves them alone.
    kept = client.patch(f"/api/edit/kitchen-notes/{created['id']}", json={"kind": "compilation"})
    assert [x["display_name"] for x in kept.json()["labels"]] == ["刀工"]
    assert kept.json()["kind"] == "compilation"

    assert client.delete(f"/api/edit/kitchen-notes/{created['id']}").status_code == 204
    assert client.get(f"/api/kitchen-notes/{created['id']}").status_code == 404


def test_a_bare_note_is_a_reference_with_nothing_else(client):
    created = create(client, title="  醬油比較  ")
    assert created["title"] == "醬油比較"
    assert created["kind"] == "reference"
    assert created["url"] is None
    assert created["labels"] == []


def test_a_missing_note_is_404_on_every_route(client):
    assert client.get("/api/kitchen-notes/999999").status_code == 404
    assert client.patch("/api/edit/kitchen-notes/999999", json={}).status_code == 404
    assert client.delete("/api/edit/kitchen-notes/999999").status_code == 404
    assert client.put("/api/edit/kitchen-notes/999999/images", json=[]).status_code == 404


# --- refusals ---------------------------------------------------------------


@pytest.mark.parametrize("title", ["", "   ", None])
def test_a_blank_title_is_refused(client, title):
    response = client.post("/api/edit/kitchen-notes", json={"title": title})
    assert response.status_code == 422, response.text


def test_a_patch_blanking_the_title_is_refused_and_a_new_title_is_not(client):
    note = create(client)
    url = f"/api/edit/kitchen-notes/{note['id']}"
    assert client.patch(url, json={"title": "  "}).status_code == 422
    assert client.patch(url, json={"title": None}).status_code == 422
    renamed = client.patch(url, json={"title": "洋蔥"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "洋蔥"


def test_an_unknown_kind_is_refused_and_a_known_one_is_not(client):
    assert client.post(
        "/api/edit/kitchen-notes", json={"title": "x", "kind": "recipe"}
    ).status_code == 422
    note = create(client, kind="compilation")
    url = f"/api/edit/kitchen-notes/{note['id']}"
    assert client.patch(url, json={"kind": None}).status_code == 422
    assert client.patch(url, json={"kind": "recipe"}).status_code == 422
    assert client.patch(url, json={"kind": "technique"}).status_code == 200


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com/x", "example.com"])
def test_a_link_that_is_not_http_is_refused(client, url):
    response = client.post("/api/edit/kitchen-notes", json={"title": "x", "url": url})
    assert response.status_code == 422, response.text


def test_an_https_link_is_accepted_and_a_blank_one_is_absent(client):
    assert create(client, url="https://example.com/a")["url"] == "https://example.com/a"
    assert create(client, url="http://example.com/b")["url"] == "http://example.com/b"
    assert create(client, url="  ")["url"] is None


def test_an_unknown_label_id_is_422_naming_it(client, labels):
    """The foreign key would refuse too, as a bare 422; the id in the detail is
    what proves the service refused it before anything was written."""
    response = client.post(
        "/api/edit/kitchen-notes",
        json={"title": "x", "label_ids": [labels[0].id, 999999]},
    )
    assert response.status_code == 422
    assert "999999" in response.json()["detail"]
    assert titles(client) == []  # nothing half-written

    note = create(client, label_ids=[labels[0].id])  # the mirror
    patched = client.patch(
        f"/api/edit/kitchen-notes/{note['id']}", json={"label_ids": [999999]}
    )
    assert patched.status_code == 422
    assert "999999" in patched.json()["detail"]
    after = client.get(f"/api/kitchen-notes/{note['id']}").json()
    assert [x["display_name"] for x in after["labels"]] == ["影片"]


def test_an_unknown_field_is_refused(client):
    response = client.post("/api/edit/kitchen-notes", json={"title": "x", "name_cn": "x"})
    assert response.status_code == 422


# --- the list ---------------------------------------------------------------


@pytest.fixture
def three(client, labels, db):
    """Three notes, one per kind, each with its own label (the third label is
    made here), created oldest first."""
    third = Label(name_cn="參考書")
    db.add(third)
    db.flush()
    label_ids = [labels[0].id, labels[1].id, third.id]
    kinds = ["compilation", "technique", "reference"]
    for i in range(3):
        create(client, title=f"筆記{i}", kind=kinds[i], label_ids=[label_ids[i]])
    return {"label": label_ids, "kind": kinds}


def test_the_list_is_newest_first_and_a_row_is_a_summary(client, three):
    rows = client.get("/api/kitchen-notes").json()
    assert [r["title"] for r in rows] == ["筆記2", "筆記1", "筆記0"]
    assert set(rows[0]) == {"id", "title", "kind", "url", "labels", "cover"}
    assert [x["display_name"] for x in rows[0]["labels"]] == ["參考書"]
    assert rows[0]["cover"] is None


@pytest.mark.parametrize("param", ["kind", "label_id"])
def test_a_multi_valued_filter_means_any_of(client, three, param):
    key = "kind" if param == "kind" else "label"
    values = three[key]
    assert titles(client, **{param: [values[0], values[2]]}) == ["筆記2", "筆記0"]
    assert titles(client, **{param: [values[1]]}) == ["筆記1"]


def test_q_matches_the_title_or_the_body(client):
    create(client, title="洋蔥", body="切絲")
    create(client, title="雞蛋", body="切洋蔥的時候不流淚")
    create(client, title="米飯", body="洗三次")
    assert titles(client, q="洋蔥") == ["雞蛋", "洋蔥"]
    assert titles(client, q="洗") == ["米飯"]
    assert titles(client, q="nothing") == []


def test_q_treats_like_wildcards_as_literal_characters(client):
    create(client, title="100% 純米", body="a_b")
    create(client, title="普通")
    assert titles(client, q="%") == ["100% 純米"]
    assert titles(client, q="_") == ["100% 純米"]
    assert titles(client, q="普") == ["普通"]


def test_the_list_issues_the_same_number_of_queries_for_one_note_or_many(
    client, three, test_engine
):
    statements = []

    def count(*_):
        statements.append(1)

    def run(**params):
        statements.clear()
        event.listen(test_engine, "before_cursor_execute", count)
        try:
            client.get("/api/kitchen-notes", params=params)
        finally:
            event.remove(test_engine, "before_cursor_execute", count)
        return len(statements)

    assert run(q="筆記0") == run()


# --- the gallery ---------------------------------------------------------------


def test_a_note_gallery_is_set_in_order_and_its_first_image_is_the_cover(client):
    first = _upload(client, (1, 2, 3, 255))
    second = _upload(client, (9, 8, 7, 255))
    note = create(client)
    url = f"/api/edit/kitchen-notes/{note['id']}/images"
    response = client.put(
        url, json=[{"image_id": second["id"], "focus": "50% 30%"}, {"image_id": first["id"]}]
    )
    assert response.status_code == 200, response.text
    assert [i["image_id"] for i in response.json()["images"]] == [second["id"], first["id"]]
    [summary] = client.get("/api/kitchen-notes").json()
    assert summary["cover"] == {"thumb_url": second["thumb_url"], "focus": "50% 30%"}
    swapped = client.put(url, json=[{"image_id": first["id"]}, {"image_id": second["id"]}])
    assert [i["image_id"] for i in swapped.json()["images"]] == [first["id"], second["id"]]


def test_an_attached_image_cannot_be_deleted_until_the_note_lets_go(client, image_dir):
    """The RESTRICT would refuse the delete too, but only the service names
    the note on the body - which is what the owners assertion pins."""
    image = _upload(client)
    note = create(client, title="擺盤")
    gallery = f"/api/edit/kitchen-notes/{note['id']}/images"
    client.put(gallery, json=[{"image_id": image["id"]}])

    owners = client.get(f"/api/images/{image['id']}").json()["owners"]
    assert owners == [{"type": "kitchen_note", "id": note["id"], "display_name": "擺盤"}]

    refused = client.delete(f"/api/edit/images/{image['id']}")
    assert refused.status_code == 409
    assert refused.json()["owners"] == owners
    assert (image_dir / image["url"].removeprefix("/images/")).is_file()

    assert client.put(gallery, json=[]).json()["images"] == []
    assert client.delete(f"/api/edit/images/{image['id']}").status_code == 204


def test_deleting_a_note_keeps_its_picture_in_the_library(client):
    image = _upload(client)
    note = create(client)
    client.put(f"/api/edit/kitchen-notes/{note['id']}/images", json=[{"image_id": image["id"]}])
    assert client.delete(f"/api/edit/kitchen-notes/{note['id']}").status_code == 204
    assert client.get(f"/api/images/{image['id']}").json()["owners"] == []


def test_a_note_gallery_refuses_an_unknown_image(client):
    image = _upload(client)
    note = create(client)
    url = f"/api/edit/kitchen-notes/{note['id']}/images"
    unknown = client.put(url, json=[{"image_id": image["id"]}, {"image_id": 999999}])
    assert unknown.status_code == 422
    assert "999999" in unknown.json()["detail"]
    assert client.put(url, json=[{"image_id": image["id"]}]).status_code == 200


def test_the_kitchen_note_kinds_are_served_with_labels(client):
    body = client.get("/api/vocabularies/fixed").json()
    assert body["kitchen_note_kinds"] == [
        {"value": "compilation", "label": "合輯"},
        {"value": "technique", "label": "技巧"},
        {"value": "reference", "label": "參考"},
    ]
