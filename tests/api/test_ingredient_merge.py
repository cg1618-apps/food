"""Merging one ingredient into another: the preview, the merge, the refusals.

The fixture `pair` is load-bearing for the agreement test: every kind of row
the merge moves exists on the source, and every kind that can collide - a
label, an image, a `(state, method)` note, a name the target already answers
to, a prose field the target already has - collides at least once. A preview
and a merge that disagree only on a collision would agree on an empty pair.
"""

import pytest

from app.models import (
    CookingMethod,
    Image,
    Ingredient,
    IngredientAlias,
    IngredientHeating,
    IngredientImage,
    IngredientLink,
    IngredientPreservation,
    Label,
)


def _image(db, n):
    row = Image(
        checksum=f"merge-{n}",
        storage_key=f"library/merge-{n}.jpg",
        thumb_key=f"library/thumbs/merge-{n}.jpg",
        byte_size=1,
        width=1,
        height=1,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def pair(client, db, fallback_category, recipe_statuses):
    shared_label, own_label = Label(name_cn="共", scope="ingredient"), Label(name_cn="獨", scope="ingredient")
    method = CookingMethod(name_cn="氣炸")
    db.add_all([shared_label, own_label, method])
    db.flush()
    shared_image, own_image, target_image = _image(db, 1), _image(db, 2), _image(db, 3)

    target = Ingredient(
        name_cn="蔥",
        name_en="scallion",
        category_id=fallback_category.id,
        description="目標的說明",
    )
    source = Ingredient(
        name_cn="青蔥",
        name_en="Green onion",
        name_alt="SCALLION",  # the target's own name, in another case
        category_id=fallback_category.id,
        description="來源的說明",  # dropped: the target has one
        selection_notes="挑綠的",  # moved: the target has none
    )
    db.add_all([target, source])
    db.flush()
    db.add_all(
        [
            IngredientAlias(ingredient_id=target.id, value="green onion"),
            IngredientAlias(ingredient_id=source.id, value="蔥花"),
            IngredientAlias(ingredient_id=source.id, value="蔥"),  # the target's name
            IngredientPreservation(ingredient_id=target.id, state="unused", method="冷藏"),
            IngredientPreservation(ingredient_id=source.id, state="unused", method="冷藏"),
            IngredientPreservation(ingredient_id=source.id, state="unused", method="冷凍"),
            IngredientHeating(ingredient_id=target.id, method_id=method.id, sort_order=0),
            IngredientHeating(ingredient_id=source.id, method_id=method.id, sort_order=0),
            IngredientLink(ingredient_id=source.id, url="https://example.com/a", sort_order=0),
            IngredientImage(ingredient_id=target.id, image_id=target_image.id, position=0),
            IngredientImage(ingredient_id=target.id, image_id=shared_image.id, position=1),
            IngredientImage(ingredient_id=source.id, image_id=shared_image.id, position=0),
            IngredientImage(ingredient_id=source.id, image_id=own_image.id, position=1),
        ]
    )
    target.labels.append(shared_label)
    source.labels.extend([shared_label, own_label])
    child = Ingredient(name_cn="細蔥", category_id=fallback_category.id, parent_id=source.id)
    db.add(child)
    db.flush()

    recipe = client.post(
        "/api/edit/recipes",
        json={
            "new_dish": {"name_cn": "蔥油餅"},
            "lines": [{"ingredient_id": source.id}, {"ingredient_id": source.id}],
        },
    ).json()
    return {
        "source": source.id,
        "target": target.id,
        "child": child.id,
        "recipe": recipe["id"],
        "images": [target_image.id, shared_image.id, own_image.id],
        "labels": {shared_label.id, own_label.id},
    }


def preview(client, source, into):
    return client.get(f"/api/ingredients/{source}/merge-preview", params={"into": into})


def merge(client, source, into, fingerprint=None):
    """Merge as the dialog does: with the fingerprint of the preview it showed.

    Where the preview itself is refused there is no fingerprint to echo, and a
    placeholder stands in - the refusal comes before the comparison.
    """
    if fingerprint is None:
        shown = preview(client, source, into)
        fingerprint = shown.json()["fingerprint"] if shown.status_code == 200 else "none"
    return client.post(
        f"/api/edit/ingredients/{source}/merge",
        json={"into": into, "fingerprint": fingerprint},
    )


def test_the_preview_describes_the_plan(client, pair):
    response = preview(client, pair["source"], pair["target"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"]["id"] == pair["source"]
    assert body["target"]["id"] == pair["target"]
    assert body["moves"] == {
        "lines": 2,
        "children": 1,
        "links": 1,
        "labels": 1,
        "images": 1,
        "heating": 1,
        "preservation": 1,
    }
    assert body["new_aliases"] == ["蔥花", "青蔥"]  # sorted
    assert body["dropped_preservation"] == [{"state": "unused", "method": "冷藏"}]
    assert body["prose"] == {"description": "dropped", "selection_notes": "moved"}


def test_the_merge_does_what_its_preview_said(client, pair):
    """Preview, merge, then check the outcome against the preview's numbers."""
    before = client.get(f"/api/ingredients/{pair['target']}").json()
    plan = preview(client, pair["source"], pair["target"]).json()

    response = merge(client, pair["source"], pair["target"])
    assert response.status_code == 200, response.text
    after = response.json()
    assert after["id"] == pair["target"]
    assert client.get(f"/api/ingredients/{pair['source']}").status_code == 404

    moves = plan["moves"]
    assert len(after["children"]) - len(before["children"]) == moves["children"]
    assert len(after["links"]) - len(before["links"]) == moves["links"]
    assert len(after["labels"]) - len(before["labels"]) == moves["labels"]
    assert len(after["images"]) - len(before["images"]) == moves["images"]
    assert len(after["heating"]) - len(before["heating"]) == moves["heating"]
    assert len(after["preservation"]) - len(before["preservation"]) == moves["preservation"]
    assert sorted(set(after["aliases"]) - set(before["aliases"])) == plan["new_aliases"]

    recipe = client.get(f"/api/recipes/{pair['recipe']}").json()
    repointed = [line for line in recipe["lines"] if line["ingredient"]["id"] == pair["target"]]
    assert len(repointed) == moves["lines"]

    for field, outcome in plan["prose"].items():
        expected = "挑綠的" if outcome == "moved" else before[field]
        assert after[field] == expected


def test_the_merged_gallery_appends_after_the_target_and_skips_what_it_has(client, pair):
    after = merge(client, pair["source"], pair["target"]).json()
    assert [i["image_id"] for i in after["images"]] == pair["images"]


def test_the_merged_rows_belong_to_the_target(client, pair):
    after = merge(client, pair["source"], pair["target"]).json()
    assert [c["id"] for c in after["children"]] == [pair["child"]]
    assert {label["id"] for label in after["labels"]} == pair["labels"]
    [used] = after["used_in"]
    assert (used["id"], used["display_name"]) == (pair["recipe"], "蔥油餅")
    assert used["dish"]["display_name"] == "蔥油餅"
    assert after["name_cn"] == "蔥"  # the target's names are untouched


def test_merging_into_itself_is_refused(client, pair):
    for call in (preview, merge):
        response = call(client, pair["source"], pair["source"])
        assert response.status_code == 422, response.text
    assert client.get(f"/api/ingredients/{pair['source']}").status_code == 200


def test_merging_into_a_descendant_is_refused(client, pair):
    for call in (preview, merge):
        assert call(client, pair["source"], pair["child"]).status_code == 422
    assert client.get(f"/api/ingredients/{pair['source']}").status_code == 200


def test_merging_a_child_into_its_parent_is_permitted(client, pair):
    # The mirror of the descendant refusal, on the same tree.
    assert preview(client, pair["child"], pair["source"]).status_code == 200
    assert merge(client, pair["child"], pair["source"]).status_code == 200
    assert client.get(f"/api/ingredients/{pair['child']}").status_code == 404


def test_merging_into_an_id_that_names_nothing_is_422(client, pair):
    for call in (preview, merge):
        assert call(client, pair["source"], 999999).status_code == 422


def test_merging_a_missing_source_is_404(client, pair):
    for call in (preview, merge):
        assert call(client, 999999, pair["target"]).status_code == 404


def test_the_merge_body_refuses_extra_fields(client, pair):
    fingerprint = preview(client, pair["source"], pair["target"]).json()["fingerprint"]
    response = client.post(
        f"/api/edit/ingredients/{pair['source']}/merge",
        json={"into": pair["target"], "fingerprint": fingerprint, "keep_source": True},
    )
    assert response.status_code == 422


def test_the_fingerprint_is_stable_while_nothing_changes(client, pair):
    first = preview(client, pair["source"], pair["target"]).json()["fingerprint"]
    second = preview(client, pair["source"], pair["target"]).json()["fingerprint"]
    assert first == second


def test_a_merge_with_the_previews_fingerprint_merges(client, pair):
    fingerprint = preview(client, pair["source"], pair["target"]).json()["fingerprint"]
    response = merge(client, pair["source"], pair["target"], fingerprint)
    assert response.status_code == 200, response.text
    assert client.get(f"/api/ingredients/{pair['source']}").status_code == 404


def test_a_source_edited_after_the_preview_is_409_and_changes_nothing(client, pair):
    """The stale tab: the preview was read, then the source gained a note."""
    shown = preview(client, pair["source"], pair["target"]).json()
    edited = client.patch(
        f"/api/edit/ingredients/{pair['source']}", json={"sourcing_notes": "市場買"}
    )
    assert edited.status_code == 200, edited.text
    before = client.get(f"/api/ingredients/{pair['target']}").json()

    response = merge(client, pair["source"], pair["target"], shown["fingerprint"])
    assert response.status_code == 409, response.text
    body = response.json()
    assert "preview" in body["detail"]
    fresh = body["preview"]
    assert fresh["fingerprint"] != shown["fingerprint"]
    assert fresh["prose"]["sourcing_notes"] == "moved"

    assert client.get(f"/api/ingredients/{pair['source']}").status_code == 200
    assert client.get(f"/api/ingredients/{pair['target']}").json() == before

    # The fresh preview's fingerprint is the one that now merges.
    assert merge(client, pair["source"], pair["target"], fresh["fingerprint"]).status_code == 200


def test_a_merge_without_a_fingerprint_is_422(client, pair):
    response = client.post(
        f"/api/edit/ingredients/{pair['source']}/merge", json={"into": pair["target"]}
    )
    assert response.status_code == 422
    assert client.get(f"/api/ingredients/{pair['source']}").status_code == 200


def test_moved_preservation_is_numbered_after_the_targets(client, db, pair):
    # Both rows sit at sort_order 0 on their own ingredient, so a move that
    # kept the source's number would tie with the target's note.
    merge(client, pair["source"], pair["target"])
    rows = (
        db.query(IngredientPreservation)
        .filter(IngredientPreservation.ingredient_id == pair["target"])
        .all()
    )
    order = {row.method: row.sort_order for row in rows}
    assert order == {"冷藏": 0, "冷凍": 1}
