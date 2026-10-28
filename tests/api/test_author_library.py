"""An author's page: the detail read, its recipes, its gallery, and the delete.

The author's names, remark and links are covered in test_author_details.py,
and what an author shares with the other nine vocabularies in
test_vocabularies.py. What is here is what the library added: the detail at
`GET /api/authors/{id}`, the list's `recipe_count` and `cover`, the gallery
PUT, the delete preview, and the author as an image owner.

The refusals each set up what they refuse: the delete is refused while a
source really names the author (the `sourced` fixture is what makes the 409
bite) and the mirror deletes an author no source names; the image delete is
refused while an author's gallery really holds the picture.
"""

import io

import pytest
from PIL import Image as PILImage

from app import config
from app.models import Author, AuthorImage, Dish, Recipe, RecipeSource

URL = "/api/authors"
EDIT_URL = "/api/edit/authors"


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "image_dir", str(tmp_path))
    return tmp_path


def _upload(client, colour=(200, 120, 40)):
    buffer = io.BytesIO()
    PILImage.new("RGB", (64, 48), colour).save(buffer, format="PNG")
    response = client.post(
        "/api/edit/images", files={"file": ("a.png", buffer.getvalue(), "image/png")}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _recipe(db, statuses, dish_name, name=None):
    dish = Dish(name_cn=dish_name, kind="dish")
    db.add(dish)
    db.flush()
    recipe = Recipe(dish_id=dish.id, name=name, status_id=statuses["想試"].id)
    db.add(recipe)
    db.flush()
    return recipe


@pytest.fixture
def sourced(db, recipe_statuses, source_platforms):
    """An author two recipes' sources name - one of them twice - and an
    author no source names. Load-bearing: without the sources the delete
    refusal below has nothing to refuse."""
    youtube = source_platforms["YouTube"]
    author = Author(name_cn="阿基師")
    unused = Author(name_cn="詹姆士")
    db.add_all([author, unused])
    db.flush()
    first = _recipe(db, recipe_statuses, "滷肉飯")
    second = _recipe(db, recipe_statuses, "三杯雞", name="快速版")
    db.add_all(
        [
            RecipeSource(recipe_id=first.id, platform_id=youtube.id, author_id=author.id),
            RecipeSource(
                recipe_id=first.id, platform_id=youtube.id, author_id=author.id, sort_order=1
            ),
            RecipeSource(recipe_id=second.id, platform_id=youtube.id, author_id=author.id),
        ]
    )
    db.flush()
    return {"author": author, "unused": unused, "recipes": [first, second]}


# --- the detail --------------------------------------------------------------


def test_the_detail_carries_names_notes_links_and_an_empty_gallery(client):
    created = client.post(
        EDIT_URL,
        json={
            "name_cn": "阿基師",
            "name_en": "Chef Ah-Chi",
            "notes": "台菜。\n影片比食譜詳細。",
            "links": [{"url": "youtube.com/@a", "label": "YouTube"}],
        },
    ).json()
    response = client.get(f"{URL}/{created['id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["display_name"] == "阿基師"
    assert body["name_en"] == "Chef Ah-Chi"
    assert body["notes"] == "台菜。\n影片比食譜詳細。"
    assert body["links"] == [{"label": "YouTube", "url": "https://youtube.com/@a"}]
    assert body["images"] == []
    assert body["recipes"] == []
    assert body["recipe_count"] == 0


def test_an_unknown_author_is_404(client):
    assert client.get(f"{URL}/999999").status_code == 404


def test_the_detail_lists_each_recipe_its_sources_name_once(client, sourced):
    """Two sources of one recipe name the author; the recipe is listed once,
    with what a cover card needs. The unused author lists none."""
    body = client.get(f"{URL}/{sourced['author'].id}").json()
    rows = {row["id"]: row for row in body["recipes"]}
    first, second = sourced["recipes"]
    assert set(rows) == {first.id, second.id}
    assert rows[second.id]["display_name"] == "快速版"
    assert rows[second.id]["dish"]["display_name"] == "三杯雞"
    assert rows[first.id]["status"]["display_name"] == "想試"
    assert "cover" in rows[first.id]
    assert body["recipe_count"] == 2
    # Sources, not recipes: what would stop the delete.
    assert body["usage_count"] == 3

    assert client.get(f"{URL}/{sourced['unused'].id}").json()["recipes"] == []


def test_the_list_carries_the_recipe_count_and_the_cover(client, sourced):
    image = _upload(client)
    put = client.put(
        f"{EDIT_URL}/{sourced['author'].id}/images",
        json=[{"image_id": image["id"], "focus": "20% 30%"}],
    )
    assert put.status_code == 200, put.text
    listed = {row["display_name"]: row for row in client.get(URL).json()}
    assert listed["阿基師"]["recipe_count"] == 2
    assert listed["阿基師"]["usage_count"] == 3
    assert listed["阿基師"]["cover"] == {"thumb_url": image["thumb_url"], "focus": "20% 30%"}
    assert listed["詹姆士"]["recipe_count"] == 0
    assert listed["詹姆士"]["cover"] is None


def test_the_other_vocabularies_do_not_answer_with_a_cover_or_a_recipe_count(client):
    client.post("/api/edit/equipment", json={"name_cn": "鍋"})
    (row,) = client.get("/api/equipment").json()
    assert "cover" not in row and "recipe_count" not in row


# --- the gallery -------------------------------------------------------------


def test_a_gallery_round_trips_in_order_with_focus_and_caption(client):
    author = client.post(EDIT_URL, json={"name_cn": "阿基師"}).json()
    first, second = _upload(client), _upload(client, colour=(10, 200, 90))
    response = client.put(
        f"{EDIT_URL}/{author['id']}/images",
        json=[
            {"image_id": second["id"], "caption": "  頻道封面\n2024  "},
            {"image_id": first["id"], "focus": "10% 90%", "caption": " "},
        ],
    )
    assert response.status_code == 200, response.text
    gallery = response.json()["images"]
    assert [(g["image_id"], g["focus"], g["caption"]) for g in gallery] == [
        (second["id"], None, "頻道封面\n2024"),
        (first["id"], "10% 90%", None),
    ]
    assert client.get(f"{URL}/{author['id']}").json()["images"] == gallery


def test_putting_the_same_gallery_twice_and_clearing_it_succeed(client, db):
    author = client.post(EDIT_URL, json={"name_cn": "阿基師"}).json()
    image = _upload(client)
    body = [{"image_id": image["id"]}]
    for _ in range(2):
        assert client.put(f"{EDIT_URL}/{author['id']}/images", json=body).status_code == 200
    assert db.query(AuthorImage).count() == 1
    cleared = client.put(f"{EDIT_URL}/{author['id']}/images", json=[])
    assert cleared.status_code == 200
    assert cleared.json()["images"] == []


def test_a_gallery_refuses_an_unknown_image_and_an_unknown_author(client):
    author = client.post(EDIT_URL, json={"name_cn": "阿基師"}).json()
    assert (
        client.put(f"{EDIT_URL}/{author['id']}/images", json=[{"image_id": 999999}])
    ).status_code == 422
    image = _upload(client)
    assert (
        client.put(f"{EDIT_URL}/999999/images", json=[{"image_id": image["id"]}])
    ).status_code == 404


def test_deleting_an_author_keeps_its_pictures_in_the_library(client):
    author = client.post(EDIT_URL, json={"name_cn": "阿基師"}).json()
    image = _upload(client)
    client.put(f"{EDIT_URL}/{author['id']}/images", json=[{"image_id": image["id"]}])
    assert client.delete(f"{EDIT_URL}/{author['id']}").status_code == 204
    detail = client.get(f"/api/images/{image['id']}")
    assert detail.status_code == 200
    assert detail.json()["owners"] == []


# --- the delete --------------------------------------------------------------


def test_the_cascade_counts_the_sources_that_refuse_the_delete(client, sourced):
    response = client.get(f"{URL}/{sourced['author'].id}/cascade")
    assert response.status_code == 200, response.text
    assert response.json() == {"sources": 3, "recipes": 2}
    # The mirror: an author no source names has nothing to refuse it.
    assert client.get(f"{URL}/{sourced['unused'].id}/cascade").json() == {
        "sources": 0,
        "recipes": 0,
    }
    assert client.get(f"{URL}/999999/cascade").status_code == 404


def test_an_author_a_source_names_is_refused_and_an_unused_one_deletes(client, db, sourced):
    author_id, unused_id = sourced["author"].id, sourced["unused"].id
    refused = client.delete(f"{EDIT_URL}/{author_id}")
    assert refused.status_code == 409
    assert refused.json()["usage_count"] == 3
    assert client.get(f"{URL}/{author_id}").status_code == 200

    assert client.delete(f"{EDIT_URL}/{unused_id}").status_code == 204
    assert db.get(Author, unused_id) is None


# --- the author as an image owner ---------------------------------------------


def test_an_image_an_author_attaches_names_the_author_and_refuses_its_delete(client, image_dir):
    author = client.post(EDIT_URL, json={"name_cn": "阿基師"}).json()
    image = _upload(client)
    client.put(f"{EDIT_URL}/{author['id']}/images", json=[{"image_id": image["id"]}])

    owner = {"type": "author", "id": author["id"], "display_name": "阿基師"}
    assert client.get(f"/api/images/{image['id']}").json()["owners"] == [owner]
    listed = {row["id"]: row for row in client.get("/api/images").json()}
    assert listed[image["id"]]["attachment_count"] == 1

    response = client.delete(f"/api/edit/images/{image['id']}")
    assert response.status_code == 409
    assert response.json()["owners"] == [owner]
    assert (image_dir / image["url"].removeprefix("/images/")).is_file()

    # The mirror: once the author lets go, the same delete goes through.
    client.put(f"{EDIT_URL}/{author['id']}/images", json=[])
    assert client.delete(f"/api/edit/images/{image['id']}").status_code == 204
