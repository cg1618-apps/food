"""Upload, deduplicate, attach, serve and delete images.

Every test points IMAGE_DIR at its own tmp_path (autouse), so nothing touches
the real data/images. The upload code reads the setting at call time; a test
that found a file in the real directory would mean that rule had broken.
"""

import io

import pytest
from PIL import Image as PILImage

from app import config

# Every recipe needs a status; the migration seeds them and create_all does not.
pytestmark = pytest.mark.usefixtures("recipe_statuses")


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "image_dir", str(tmp_path))
    return tmp_path


def _png(size=(64, 48), colour=(200, 120, 40, 255), mode="RGBA") -> bytes:
    buffer = io.BytesIO()
    PILImage.new(mode, size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(client, data: bytes, name="dish.png"):
    return client.post("/api/edit/images", files={"file": (name, data, "image/png")})


def test_an_upload_is_reencoded_to_jpeg_and_stored_under_its_hash(client, image_dir):
    response = _upload(client, _png())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["url"].startswith("/images/library/") and body["url"].endswith(".jpg")
    assert body["thumb_url"].startswith("/images/library/thumbs/")
    assert (body["width"], body["height"]) == (64, 48)
    stored = image_dir / body["url"].removeprefix("/images/")
    assert stored.is_file()
    assert PILImage.open(stored).format == "JPEG"


def test_the_same_picture_uploaded_twice_is_one_row(client, image_dir):
    first = _upload(client, _png()).json()
    second = _upload(client, _png(), name="again.png")
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]
    assert len(list((image_dir / "library").glob("*.jpg"))) == 1


def test_a_file_that_is_not_an_image_is_refused(client, image_dir):
    response = _upload(client, b"<svg onload=alert(1)>", name="x.png")
    assert response.status_code == 422
    assert not (image_dir / "library").exists() or not list((image_dir / "library").glob("*.jpg"))


def test_an_upload_over_the_size_cap_is_refused(client, monkeypatch):
    monkeypatch.setattr(config.settings, "max_image_upload_mb", 1)
    noise = PILImage.effect_noise((1400, 1400), 100).convert("RGB")
    buffer = io.BytesIO()
    noise.save(buffer, format="BMP")
    assert len(buffer.getvalue()) > 1024 * 1024
    response = _upload(client, buffer.getvalue(), name="big.bmp")
    assert response.status_code == 413


def test_an_upload_under_the_size_cap_is_accepted(client, monkeypatch):
    # The mirror of the refusal above, with the same cap: a green there proves
    # the cap did the refusing and not something incidental to the file type.
    monkeypatch.setattr(config.settings, "max_image_upload_mb", 1)
    assert _upload(client, _png()).status_code == 201


def test_a_decompression_bomb_is_refused(client):
    buffer = io.BytesIO()
    # 144 megapixels: over twice the 50 MP ceiling, so Pillow raises rather than warns.
    PILImage.new("1", (12000, 12000)).save(buffer, format="PNG")
    response = _upload(client, buffer.getvalue(), name="bomb.png")
    assert response.status_code == 422


def test_the_long_edge_is_capped_and_the_thumbnail_is_small(client, image_dir):
    body = _upload(client, _png(size=(3000, 1500))).json()
    assert (body["width"], body["height"]) == (2000, 1000)
    thumb = PILImage.open(image_dir / body["thumb_url"].removeprefix("/images/"))
    assert max(thumb.size) == 400


def test_exif_rotation_is_applied_before_the_metadata_is_stripped(client, image_dir):
    """A phone's portrait photo is stored landscape plus an Orientation tag.

    The re-encode drops EXIF, so unless the rotation is applied first the
    stored image is sideways. Orientation 6 means "rotate 90 degrees clockwise
    to display": a 60x40 stored image displays as 40x60.
    """
    buffer = io.BytesIO()
    exif = PILImage.Exif()
    exif[0x0112] = 6
    PILImage.new("RGB", (60, 40), (10, 200, 10)).save(buffer, format="JPEG", exif=exif)
    body = _upload(client, buffer.getvalue(), name="phone.jpg").json()
    assert (body["width"], body["height"]) == (40, 60)
    stored = PILImage.open(image_dir / body["url"].removeprefix("/images/"))
    assert not stored.getexif()


def test_an_attached_image_shows_on_the_ingredient_and_is_its_cover(client, fallback_category):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    response = client.put(
        f"/api/edit/ingredients/{ingredient['id']}/images",
        json=[{"image_id": image["id"], "focus": "50% 30%"}],
    )
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/ingredients/{ingredient['id']}").json()
    assert detail["images"][0]["image_id"] == image["id"]
    assert detail["images"][0]["focus"] == "50% 30%"
    summary = client.get("/api/ingredients").json()[0]
    assert summary["cover"] == {"thumb_url": image["thumb_url"], "focus": "50% 30%"}


def _ingredient_with_two_images(client, fallback_category):
    first = _upload(client, _png(colour=(1, 2, 3, 255))).json()
    second = _upload(client, _png(colour=(9, 8, 7, 255))).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    return ingredient, first, second


def test_putting_the_same_gallery_twice_in_a_row_succeeds(client, fallback_category):
    # The old rows hold position 0 when the new ones are inserted; unless the
    # old ones are deleted first, the unit of work INSERTs before it DELETEs
    # and uq_ingredient_image_position refuses the second PUT.
    ingredient, first, _ = _ingredient_with_two_images(client, fallback_category)
    url = f"/api/edit/ingredients/{ingredient['id']}/images"
    assert client.put(url, json=[{"image_id": first["id"]}]).status_code == 200
    again = client.put(url, json=[{"image_id": first["id"], "focus": "10% 10%"}])
    assert again.status_code == 200, again.text
    assert [i["focus"] for i in again.json()["images"]] == ["10% 10%"]


def test_swapping_two_images_in_a_gallery_reorders_them(client, fallback_category):
    ingredient, first, second = _ingredient_with_two_images(client, fallback_category)
    url = f"/api/edit/ingredients/{ingredient['id']}/images"
    client.put(url, json=[{"image_id": first["id"]}, {"image_id": second["id"]}])
    swapped = client.put(url, json=[{"image_id": second["id"]}, {"image_id": first["id"]}])
    assert swapped.status_code == 200, swapped.text
    assert [i["image_id"] for i in swapped.json()["images"]] == [second["id"], first["id"]]


def test_an_empty_put_clears_the_gallery_and_the_cover(client, fallback_category):
    ingredient, first, _ = _ingredient_with_two_images(client, fallback_category)
    url = f"/api/edit/ingredients/{ingredient['id']}/images"
    client.put(url, json=[{"image_id": first["id"]}])
    assert client.put(url, json=[]).json()["images"] == []
    assert client.get("/api/ingredients").json()[0]["cover"] is None


@pytest.mark.parametrize("focus", ["101% 0%", "50%", "a% b%", "50 50"])
def test_a_malformed_focus_is_refused(client, fallback_category, focus):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    response = client.put(
        f"/api/edit/ingredients/{ingredient['id']}/images",
        json=[{"image_id": image["id"], "focus": focus}],
    )
    assert response.status_code == 422


def test_attaching_an_unknown_image_is_422_and_a_repeat_is_422(client, fallback_category):
    # An id inside the body naming no row is 422, as everywhere else: the URL
    # resolved, the payload was wrong. The library holds an image, so the
    # lookup had something to find.
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    url = f"/api/edit/ingredients/{ingredient['id']}/images"
    unknown = client.put(url, json=[{"image_id": 999999}])
    assert unknown.status_code == 422
    assert "999999" in unknown.json()["detail"]
    assert (
        client.put(url, json=[{"image_id": image["id"]}, {"image_id": image["id"]}]).status_code
        == 422
    )
    # Mirror: the image that exists attaches.
    assert client.put(url, json=[{"image_id": image["id"]}]).status_code == 200


def _recipe(client, name="番茄炒蛋"):
    response = client.post("/api/edit/recipes", json={"name_cn": name})
    assert response.status_code == 201, response.text
    return response.json()


def test_a_recipe_gallery_is_set_in_order_and_its_first_image_is_the_cover(client):
    first = _upload(client, _png(colour=(1, 2, 3, 255))).json()
    second = _upload(client, _png(colour=(9, 8, 7, 255))).json()
    recipe = _recipe(client)
    url = f"/api/edit/recipes/{recipe['id']}/images"
    response = client.put(
        url, json=[{"image_id": second["id"], "focus": "50% 30%"}, {"image_id": first["id"]}]
    )
    assert response.status_code == 200, response.text
    assert [i["image_id"] for i in response.json()["images"]] == [second["id"], first["id"]]
    [summary] = client.get("/api/recipes").json()
    assert summary["cover"] == {"thumb_url": second["thumb_url"], "focus": "50% 30%"}
    # Reusing the positions in a reorder must not collide with the old rows.
    swapped = client.put(url, json=[{"image_id": first["id"]}, {"image_id": second["id"]}])
    assert swapped.status_code == 200, swapped.text
    assert [i["image_id"] for i in swapped.json()["images"]] == [first["id"], second["id"]]
    assert client.put(url, json=[]).json()["images"] == []


def test_a_recipe_gallery_refuses_an_unknown_image_and_an_unknown_recipe(client):
    image = _upload(client, _png()).json()
    recipe = _recipe(client)
    url = f"/api/edit/recipes/{recipe['id']}/images"
    # The foreign key would answer 422 as well; the id in the detail is what
    # proves the service refused it. The real image is the mirror.
    unknown = client.put(url, json=[{"image_id": image["id"]}, {"image_id": 999999}])
    assert unknown.status_code == 422
    assert "999999" in unknown.json()["detail"]
    assert client.put(url, json=[{"image_id": image["id"]}]).status_code == 200
    assert (
        client.put("/api/edit/recipes/999999/images", json=[{"image_id": image["id"]}])
    ).status_code == 404


def test_an_image_lists_the_recipes_that_attach_it(client, fallback_category):
    image = _upload(client, _png()).json()
    recipe = _recipe(client, "芒果布丁")
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/recipes/{recipe['id']}/images", json=[{"image_id": image["id"]}])
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": image["id"]}])
    owners = client.get(f"/api/images/{image['id']}").json()["owners"]
    assert sorted((o["type"], o["id"], o["display_name"]) for o in owners) == [
        ("ingredient", ingredient["id"], "芒果"),
        ("recipe", recipe["id"], "芒果布丁"),
    ]


def test_an_attached_image_cannot_be_deleted_and_its_file_survives(
    client, fallback_category, image_dir
):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": image["id"]}])

    response = client.delete(f"/api/edit/images/{image['id']}")
    assert response.status_code == 409
    assert response.json()["owners"] == [
        {"type": "ingredient", "id": ingredient["id"], "display_name": "芒果"}
    ]
    assert (image_dir / image["url"].removeprefix("/images/")).is_file()


def test_an_unattached_image_deletes_with_its_files(client, image_dir):
    image = _upload(client, _png()).json()
    assert client.delete(f"/api/edit/images/{image['id']}").status_code == 204
    assert not (image_dir / image["url"].removeprefix("/images/")).exists()
    assert not (image_dir / image["thumb_url"].removeprefix("/images/")).exists()


def test_deleting_an_ingredient_keeps_its_image_in_the_library(client, fallback_category):
    image = _upload(client, _png()).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": image["id"]}])
    client.delete(
        f"/api/edit/ingredients/{ingredient['id']}",
        params={"aliases": 0, "preservation": 0, "heating": 0, "links": 0},
    )
    unused = client.get("/api/images", params={"unused": "true"}).json()
    assert [row["id"] for row in unused] == [image["id"]]


def test_the_unused_filter_hides_attached_images(client, fallback_category):
    used = _upload(client, _png(colour=(1, 2, 3, 255))).json()
    spare = _upload(client, _png(colour=(9, 8, 7, 255))).json()
    ingredient = client.post(
        "/api/edit/ingredients", json={"name_cn": "芒果", "category_id": fallback_category.id}
    ).json()
    client.put(f"/api/edit/ingredients/{ingredient['id']}/images", json=[{"image_id": used["id"]}])
    assert [r["id"] for r in client.get("/api/images", params={"unused": "true"}).json()] == [
        spare["id"]
    ]
    everything = {r["id"]: r for r in client.get("/api/images").json()}
    assert everything[used["id"]]["attachment_count"] == 1


def test_a_stored_image_is_served_and_a_missing_one_is_404_not_the_spa(client):
    image = _upload(client, _png()).json()
    served = client.get(image["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    assert client.get("/images/library/does-not-exist.jpg").status_code == 404


def test_a_failure_while_processing_an_opened_image_is_422_not_500(client, image_dir, monkeypatch):
    from app.services import images

    def broken(_image):
        raise ValueError("malformed EXIF")

    monkeypatch.setattr(images.ImageOps, "exif_transpose", broken)
    response = _upload(client, _png())
    assert response.status_code == 422
    assert response.json()["detail"] == "That file is not an image this app can read."
