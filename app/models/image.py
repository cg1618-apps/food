"""The image library: one row per stored picture, and one gallery per owner.

Media's two-table library, with one deliberate difference: attachments are a
join table PER OWNER with real foreign keys, not one polymorphic table with an
owner_type and an owner_id nothing constrains. Media records that "nothing in
the database stops an attachment outliving its owner", and carries orphan gaps
because of it. food has three owner types - ingredients, recipes and kitchen
notes; three small tables remove the class.

Owner side CASCADE (deleting a recipe removes its gallery, never the picture);
image side RESTRICT (an attached picture cannot be deleted - the API answers
409 naming the owners first).
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base, get_taipei_now


class Image(Base):
    __tablename__ = "image"

    id = Column(Integer, primary_key=True)
    # SHA-256 of the NORMALISED JPEG bytes. Identical pixels deduplicate;
    # "the same picture" in two formats does not, and is not meant to - media
    # learned that the hard way.
    checksum = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)
    thumb_key = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    byte_size = Column(BigInteger, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=get_taipei_now)

    __table_args__ = (UniqueConstraint("checksum", name="uq_image_checksum"),)


class IngredientImage(Base):
    """One picture in one ingredient's gallery. Position 0 is the cover."""

    __tablename__ = "ingredient_image"

    id = Column(Integer, primary_key=True)
    ingredient_id = Column(
        Integer, ForeignKey("ingredient.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id = Column(
        Integer, ForeignKey("image.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # "X% Y%", 0-100 each, or NULL for centred. Where a cropped thumbnail
    # centres - per attachment, because one picture may be cropped
    # differently in two galleries.
    focus = Column(String, nullable=True)

    ingredient = relationship("Ingredient", back_populates="images")
    image = relationship("Image", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("ingredient_id", "position", name="uq_ingredient_image_position"),
        UniqueConstraint("ingredient_id", "image_id", name="uq_ingredient_image_once"),
    )


class RecipeImage(Base):
    """One picture in one recipe's gallery. The same shape as IngredientImage."""

    __tablename__ = "recipe_image"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(
        Integer, ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id = Column(
        Integer, ForeignKey("image.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    focus = Column(String, nullable=True)

    recipe = relationship("Recipe", back_populates="images")
    image = relationship("Image", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_image_position"),
        UniqueConstraint("recipe_id", "image_id", name="uq_recipe_image_once"),
    )


class KitchenNoteImage(Base):
    """One picture in one kitchen note's gallery. The same shape again."""

    __tablename__ = "kitchen_note_image"

    id = Column(Integer, primary_key=True)
    kitchen_note_id = Column(
        Integer, ForeignKey("kitchen_note.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id = Column(
        Integer, ForeignKey("image.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    focus = Column(String, nullable=True)

    kitchen_note = relationship("KitchenNote", back_populates="images")
    image = relationship("Image", passive_deletes="all")

    __table_args__ = (
        UniqueConstraint("kitchen_note_id", "position", name="uq_kitchen_note_image_position"),
        UniqueConstraint("kitchen_note_id", "image_id", name="uq_kitchen_note_image_once"),
    )
