"""A recipe template: a named skeleton a new recipe can start from.

The body is one JSONB document in the recipe payload's own shapes - the lines
with their groups, the steps with their groups and kinds, the method and
equipment ids, servings and time - rather than a set of tables mirroring
`recipe_line`, `recipe_step` and the rest. A template is a snapshot that is
only ever read whole into a form and written whole from one; nothing filters,
joins or counts by what is inside it. docs/notes/decisions.md has the
trade-off, including why that does not reopen the "no list in a column" rule.

There are no foreign keys into the JSON, so what it names can be deleted from
under it. `app/services/recipe_templates.py` drops a reference that no longer
exists when it reads a template, and says how many it dropped; an ingredient
merge rewrites the merged id to its target inside every body.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base, get_taipei_now


class RecipeTemplate(Base):
    __tablename__ = "recipe_template"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    # The owner's order on 設定 and in the new-recipe chooser; a new template
    # is given the end.
    sort_order = Column(Integer, nullable=False)
    # Validated through app/schemas/recipe_template.py before it is stored,
    # and stored in that schema's canonical form.
    body = Column(JSONB, nullable=False)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_recipe_template_has_a_name"),
        # Case-insensitive, as every name here is: lower() in the index rather
        # than a citext column.
        Index("uq_recipe_template_name", func.lower(name), unique=True),
    )
