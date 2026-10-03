"""The weekly schedule: a day's plain fields and its four meals, read over a
range of dates and written a whole day at a time. A meal is free text and any
number of items, each a dish and optionally one of that dish's recipes.

Every refusal test sets up the thing it refuses - an item naming the dish, a
recipe of another dish, a duplicate item - and has a mirror that commits.
"""

from datetime import date

import pytest

from app.models import ScheduleDay, ScheduleMeal, ScheduleMealItem
from app.services import schedule

pytestmark = pytest.mark.usefixtures("recipe_statuses", "source_platforms")

SLOTS = ["breakfast", "lunch", "afternoon", "dinner"]
FLAGS = ["to_buy", "thaw_morning", "thaw_noon", "thaw_evening"]


def create_dish(client, name="照燒雞腿排"):
    response = client.post("/api/edit/dishes", json={"name_cn": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_recipe(client, dish_id, name=None):
    body = {"dish_id": dish_id}
    if name:
        body["name"] = name
    response = client.post("/api/edit/recipes", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def put_day(client, day, **body):
    return client.put(f"/api/edit/schedule/{day}", json=body)


# --- the week ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "saturday"),
    [
        (date(2026, 10, 3), date(2026, 10, 3)),  # a Saturday is its own week's start
        (date(2026, 10, 4), date(2026, 10, 3)),  # Sunday
        (date(2026, 10, 9), date(2026, 10, 3)),  # Friday, the week's last day
        (date(2026, 10, 10), date(2026, 10, 10)),  # the next Saturday
        (date(2027, 1, 1), date(2026, 12, 26)),  # across a year
    ],
)
def test_a_week_starts_on_the_saturday_on_or_before_the_day(day, saturday):
    assert schedule.week_start(day) == saturday


def test_without_a_start_the_range_is_two_weeks_from_this_weeks_saturday(client, monkeypatch):
    monkeypatch.setattr(schedule, "today", lambda: date(2026, 10, 7))  # a Wednesday
    body = client.get("/api/schedule").json()
    assert len(body) == 14
    assert body[0]["date"] == "2026-10-03"
    assert body[0]["weekday"] == 5  # Saturday, Monday being 0
    assert body[-1]["date"] == "2026-10-16"


def test_every_date_in_the_range_is_answered_stored_or_not(client):
    assert put_day(client, "2026-10-04", fruit="蘋果").status_code == 200
    body = client.get("/api/schedule", params={"start": "2026-10-03", "days": 3}).json()
    assert [d["date"] for d in body] == ["2026-10-03", "2026-10-04", "2026-10-05"]
    empty = body[0]
    assert empty == {
        "date": "2026-10-03",
        "weekday": 5,
        "to_buy": False,
        "thaw_morning": False,
        "thaw_noon": False,
        "thaw_evening": False,
        "fruit": None,
        "note": None,
        "meals": {slot: None for slot in SLOTS},
    }
    assert body[1]["fruit"] == "蘋果"


@pytest.mark.parametrize("days", [0, -1, 63])
def test_a_range_outside_one_to_sixty_two_days_is_refused(client, days):
    assert client.get("/api/schedule", params={"start": "2026-10-03", "days": days}).status_code == 422
    assert client.get("/api/schedule", params={"start": "2026-10-03", "days": 62}).status_code == 200


# --- writing a day -------------------------------------------------------------


def test_a_day_round_trips_with_its_meals(client):
    dish = create_dish(client)
    recipe = create_recipe(client, dish["id"], name="A 版")
    response = put_day(
        client,
        "2026-10-05",
        to_buy=True,
        thaw_morning=True,
        thaw_noon=False,
        thaw_evening=True,
        fruit="芭樂",
        note="外食",
        meals={
            "breakfast": {"text": "吐司"},
            "dinner": {"text": "配白飯", "items": [{"dish_id": dish["id"], "recipe_id": recipe["id"]}]},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date"] == "2026-10-05" and body["weekday"] == 0
    assert (body["to_buy"], body["thaw_morning"], body["thaw_noon"]) == (True, True, False)
    assert (body["thaw_evening"], body["fruit"], body["note"]) == (True, "芭樂", "外食")
    assert body["meals"]["breakfast"] == {"text": "吐司", "items": []}
    assert body["meals"]["lunch"] is None and body["meals"]["afternoon"] is None
    dinner = body["meals"]["dinner"]
    assert dinner["text"] == "配白飯"
    [item] = dinner["items"]
    assert item["dish"] == {"id": dish["id"], "display_name": "照燒雞腿排", "kind": "dish"}
    assert item["recipe"]["id"] == recipe["id"]
    assert item["recipe"]["display_name"] == "A 版"

    read = client.get("/api/schedule", params={"start": "2026-10-05", "days": 1}).json()
    assert read == [body]


def test_the_marks_default_to_false(client, db):
    """A day that names none of the four marks stores them false - and a day
    whose marks are all false, with nothing else, keeps no row."""
    body = put_day(client, "2026-10-05", fruit="芭樂").json()
    assert [body[k] for k in FLAGS] == [False, False, False, False]
    assert put_day(client, "2026-10-06", to_buy=False, thaw_noon=False).status_code == 200
    assert db.query(ScheduleDay).filter(ScheduleDay.date == date(2026, 10, 6)).count() == 0
    # Mirror: one true mark is enough to keep a day.
    assert put_day(client, "2026-10-06", thaw_noon=True).json()["thaw_noon"] is True
    assert db.query(ScheduleDay).filter(ScheduleDay.date == date(2026, 10, 6)).count() == 1


def test_a_mark_is_a_boolean_not_text(client):
    assert put_day(client, "2026-10-05", to_buy="雞腿").status_code == 422
    assert put_day(client, "2026-10-05", to_buy=True).status_code == 200


def test_a_put_replaces_the_whole_day(client, db):
    put_day(
        client,
        "2026-10-05",
        fruit="芭樂",
        to_buy=True,
        meals={"lunch": {"text": "麵"}, "dinner": {"text": "飯"}},
    )
    response = put_day(client, "2026-10-05", note="改", meals={"dinner": {"text": "粥"}})
    body = response.json()
    assert body["fruit"] is None and body["note"] == "改" and body["to_buy"] is False
    assert body["meals"]["lunch"] is None
    assert body["meals"]["dinner"]["text"] == "粥"
    assert db.query(ScheduleMeal).count() == 1


def test_blank_text_is_null_and_an_empty_meal_is_not_stored(client, db):
    response = put_day(
        client,
        "2026-10-05",
        fruit="  ",
        note="x",
        meals={"breakfast": {"text": " ", "items": []}, "lunch": {}, "afternoon": None},
    )
    body = response.json()
    assert body["fruit"] is None
    assert body["meals"] == {slot: None for slot in SLOTS}
    assert db.query(ScheduleMeal).count() == 0
    assert db.query(ScheduleDay).count() == 1  # the note keeps the day


def test_a_day_with_nothing_left_is_deleted(client, db):
    dish = create_dish(client)
    put_day(
        client,
        "2026-10-05",
        fruit="芭樂",
        meals={"dinner": {"text": "飯", "items": [{"dish_id": dish["id"]}]}},
    )
    assert db.query(ScheduleDay).count() == 1
    response = put_day(client, "2026-10-05", fruit="", meals={"dinner": {"text": ""}})
    assert response.status_code == 200
    assert response.json()["meals"]["dinner"] is None
    assert db.query(ScheduleDay).count() == 0
    assert db.query(ScheduleMeal).count() == 0
    assert db.query(ScheduleMealItem).count() == 0


def test_an_empty_day_is_not_stored(client, db):
    assert put_day(client, "2026-10-05").status_code == 200
    assert db.query(ScheduleDay).count() == 0


def test_an_unknown_slot_or_field_is_refused(client):
    assert put_day(client, "2026-10-05", meals={"supper": {"text": "x"}}).status_code == 422
    assert put_day(client, "2026-10-05", weather="sun").status_code == 422
    # A meal's dish is an item now, never a field of the meal.
    assert put_day(client, "2026-10-05", meals={"lunch": {"dish_id": 1}}).status_code == 422
    assert client.put("/api/edit/schedule/not-a-date", json={}).status_code == 422
    # Mirror: a known slot saves.
    assert put_day(client, "2026-10-05", meals={"afternoon": {"text": "x"}}).status_code == 200


# --- a meal's items --------------------------------------------------------------


def test_a_meal_with_items_only_is_stored(client):
    dish = create_dish(client)
    body = put_day(client, "2026-10-05", meals={"lunch": {"items": [{"dish_id": dish["id"]}]}}).json()
    lunch = body["meals"]["lunch"]
    assert lunch["text"] is None
    assert lunch["items"] == [
        {"dish": {"id": dish["id"], "display_name": "照燒雞腿排", "kind": "dish"}, "recipe": None}
    ]


def test_several_items_keep_their_order(client, db):
    chicken = create_dish(client, "照燒雞腿排")
    curry = create_dish(client, "咖哩")
    soup = create_dish(client, "味噌湯")
    a = create_recipe(client, curry["id"], name="A 版")
    b = create_recipe(client, curry["id"], name="B 版")
    items = [
        {"dish_id": soup["id"]},
        {"dish_id": curry["id"], "recipe_id": b["id"]},
        {"dish_id": chicken["id"]},
        {"dish_id": curry["id"], "recipe_id": a["id"]},  # the same dish, another recipe
    ]
    body = put_day(client, "2026-10-05", meals={"dinner": {"text": "配白飯", "items": items}}).json()
    got = [
        (item["dish"]["id"], item["recipe"] and item["recipe"]["id"])
        for item in body["meals"]["dinner"]["items"]
    ]
    assert got == [
        (soup["id"], None),
        (curry["id"], b["id"]),
        (chicken["id"], None),
        (curry["id"], a["id"]),
    ]
    positions = db.query(ScheduleMealItem.position).order_by(ScheduleMealItem.position).all()
    assert [row.position for row in positions] == [0, 1, 2, 3]

    # Reordered and shortened by the next save.
    body = put_day(client, "2026-10-05", meals={"dinner": {"items": [items[2], items[1]]}}).json()
    assert [item["dish"]["id"] for item in body["meals"]["dinner"]["items"]] == [
        chicken["id"],
        curry["id"],
    ]
    assert db.query(ScheduleMealItem).count() == 2


def test_a_recipe_without_a_dish_takes_the_recipes_dish(client):
    dish = create_dish(client)
    recipe = create_recipe(client, dish["id"])
    body = put_day(
        client, "2026-10-05", meals={"lunch": {"items": [{"recipe_id": recipe["id"]}]}}
    ).json()
    [item] = body["meals"]["lunch"]["items"]
    assert item["dish"]["id"] == dish["id"]
    assert item["recipe"]["id"] == recipe["id"]


def test_an_item_naming_nothing_is_422(client, db):
    response = put_day(client, "2026-10-05", meals={"lunch": {"text": "麵", "items": [{}]}})
    assert response.status_code == 422
    assert db.query(ScheduleDay).count() == 0


def test_a_recipe_of_another_dish_is_422(client, db):
    """Two dishes, so the mismatch exists; the mirror names the right one."""
    chicken = create_dish(client, "照燒雞腿排")
    curry = create_dish(client, "咖哩")
    recipe = create_recipe(client, curry["id"])
    response = put_day(
        client,
        "2026-10-05",
        meals={"lunch": {"items": [{"dish_id": chicken["id"], "recipe_id": recipe["id"]}]}},
    )
    assert response.status_code == 422
    assert db.query(ScheduleDay).count() == 0
    ok = put_day(
        client,
        "2026-10-05",
        meals={"lunch": {"items": [{"dish_id": curry["id"], "recipe_id": recipe["id"]}]}},
    )
    assert ok.status_code == 200


def test_the_same_dish_and_recipe_twice_in_one_meal_is_422(client, db):
    """The duplicate is there; the mirrors give it another recipe, or put it
    in another meal, and save."""
    dish = create_dish(client)
    a = create_recipe(client, dish["id"], name="A 版")
    b = create_recipe(client, dish["id"], name="B 版")
    twice = [{"dish_id": dish["id"]}, {"dish_id": dish["id"]}]
    assert put_day(client, "2026-10-05", meals={"lunch": {"items": twice}}).status_code == 422
    # The recipe implies the dish, so these two are the same item.
    twice = [{"dish_id": dish["id"], "recipe_id": a["id"]}, {"recipe_id": a["id"]}]
    assert put_day(client, "2026-10-05", meals={"lunch": {"items": twice}}).status_code == 422
    assert db.query(ScheduleDay).count() == 0

    two_recipes = [
        {"dish_id": dish["id"], "recipe_id": a["id"]},
        {"dish_id": dish["id"], "recipe_id": b["id"]},
        {"dish_id": dish["id"]},
    ]
    assert put_day(client, "2026-10-05", meals={"lunch": {"items": two_recipes}}).status_code == 200
    two_meals = {
        "lunch": {"items": [{"dish_id": dish["id"]}]},
        "dinner": {"items": [{"dish_id": dish["id"]}]},
    }
    assert put_day(client, "2026-10-06", meals=two_meals).status_code == 200


def test_a_dish_or_recipe_that_does_not_exist_is_422(client):
    dish = create_dish(client)
    create_recipe(client, dish["id"])
    missing_dish = {"lunch": {"items": [{"dish_id": 999999}]}}
    missing_recipe = {"lunch": {"items": [{"recipe_id": 999999}]}}
    assert put_day(client, "2026-10-05", meals=missing_dish).status_code == 422
    assert put_day(client, "2026-10-05", meals=missing_recipe).status_code == 422


def test_a_failed_put_leaves_the_stored_day_alone(client):
    put_day(client, "2026-10-05", fruit="芭樂")
    missing = {"lunch": {"items": [{"dish_id": 999999}]}}
    assert put_day(client, "2026-10-05", meals=missing).status_code == 422
    read = client.get("/api/schedule", params={"start": "2026-10-05", "days": 1}).json()
    assert read[0]["fruit"] == "芭樂"


# --- what a meal names, deleted --------------------------------------------------


def test_a_dish_a_meal_item_names_cannot_be_deleted(client, db):
    """The items are the fixture that makes this bite; the mirror clears
    them and the dish goes. Two items on one date list that date once."""
    dish = create_dish(client)
    rice = create_dish(client, "白飯")
    put_day(
        client,
        "2026-10-05",
        meals={"dinner": {"items": [{"dish_id": rice["id"]}, {"dish_id": dish["id"]}]}},
    )
    put_day(
        client,
        "2026-10-06",
        meals={
            "lunch": {"items": [{"dish_id": dish["id"]}]},
            "dinner": {"items": [{"dish_id": dish["id"]}]},
        },
    )
    assert client.get(f"/api/dishes/{dish['id']}/cascade").json()["meals"] == 3

    response = client.delete(f"/api/edit/dishes/{dish['id']}", params={"aliases": 0})
    assert response.status_code == 409
    assert response.json()["meals"] == ["2026-10-05", "2026-10-06"]
    assert response.json()["recipes"] == [] and response.json()["used_in"] == []

    put_day(client, "2026-10-05", meals={"dinner": {"items": [{"dish_id": rice["id"]}]}})
    put_day(client, "2026-10-06", meals={"lunch": {"text": "外食"}})
    assert client.get(f"/api/dishes/{dish['id']}/cascade").json()["meals"] == 0
    assert client.delete(f"/api/edit/dishes/{dish['id']}", params={"aliases": 0}).status_code == 204


def test_an_unscheduled_dish_deletes(client):
    scheduled = create_dish(client, "咖哩")
    put_day(client, "2026-10-05", meals={"dinner": {"items": [{"dish_id": scheduled["id"]}]}})
    free = create_dish(client, "拉麵")
    assert client.get(f"/api/dishes/{free['id']}/cascade").json()["meals"] == 0
    assert client.delete(f"/api/edit/dishes/{free['id']}", params={"aliases": 0}).status_code == 204


def test_deleting_a_recipe_leaves_the_item_its_dish(client, db):
    dish = create_dish(client)
    recipe = create_recipe(client, dish["id"])
    put_day(client, "2026-10-05", meals={"dinner": {"items": [{"recipe_id": recipe["id"]}]}})

    params = {"sources": 0, "lines": 0, "steps": 0}
    assert client.delete(f"/api/edit/recipes/{recipe['id']}", params=params).status_code == 204
    db.expire_all()
    read = client.get("/api/schedule", params={"start": "2026-10-05", "days": 1}).json()
    assert read[0]["meals"]["dinner"]["items"] == [
        {"dish": {"id": dish["id"], "display_name": "照燒雞腿排", "kind": "dish"}, "recipe": None}
    ]


def test_the_meal_slots_are_served_as_a_fixed_vocabulary(client):
    body = client.get("/api/vocabularies/fixed").json()
    assert body["meal_slots"] == [
        {"value": "breakfast", "label": "早"},
        {"value": "lunch", "label": "中"},
        {"value": "afternoon", "label": "下午"},
        {"value": "dinner", "label": "晚"},
    ]
