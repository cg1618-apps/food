"""`a2lternatives` adds `recipe_line_alternative`, and its downgrade removes
it and nothing else.

`test_migrations_build_the_schema.py` proves the upgrade builds the table the
models declare. What it cannot see is the downgrade, so this runs it with a
line and an alternative in the database: the line must survive, the table
must go, and the chain must build again afterwards.
"""

from sqlalchemy import inspect, text

from tests.migrations.conftest import previous_revision


def test_the_downgrade_drops_the_alternatives_and_keeps_the_lines(scratch):
    scratch.alembic("upgrade", "a2lternatives")
    with scratch.begin() as conn:
        dish = conn.execute(text("INSERT INTO dish (name_cn) VALUES ('照燒雞') RETURNING id")).scalar()
        recipe = conn.execute(
            text(
                "INSERT INTO recipe (dish_id, status_id) "
                "VALUES (:dish, (SELECT min(id) FROM recipe_status)) RETURNING id"
            ),
            {"dish": dish},
        ).scalar()
        thigh, breast = (
            conn.execute(
                text(
                    "INSERT INTO ingredient (name_cn, category_id) "
                    "VALUES (:name, (SELECT id FROM ingredient_category WHERE is_fallback)) "
                    "RETURNING id"
                ),
                {"name": name},
            ).scalar()
            for name in ("雞腿測試", "雞胸肉測試")
        )
        line = conn.execute(
            text(
                "INSERT INTO recipe_line (recipe_id, position, ingredient_id) "
                "VALUES (:recipe, 0, :thigh) RETURNING id"
            ),
            {"recipe": recipe, "thigh": thigh},
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO recipe_line_alternative (line_id, position, ingredient_id) "
                "VALUES (:line, 0, :breast)"
            ),
            {"line": line, "breast": breast},
        )

    scratch.alembic("downgrade", previous_revision("a2lternatives"))
    with scratch.connect() as conn:
        assert "recipe_line_alternative" not in inspect(conn).get_table_names()
        assert conn.execute(text("SELECT count(*) FROM recipe_line")).scalar() == 1

    scratch.alembic("upgrade", "head")
    with scratch.connect() as conn:
        assert "recipe_line_alternative" in inspect(conn).get_table_names()
