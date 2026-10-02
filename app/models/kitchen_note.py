"""Kitchen notes: bookmarks to what is worth keeping that is not a recipe.

A compilation video of twenty dishes, a technique, a page to look something
up in. A note has a title rather than the name slots a catalogue entity has:
nothing will ever look one up by an English name it does not have. Titles are
not unique - two compilations may well share one.

The gallery table lives in `image.py` beside the other galleries, as the
recipe's does.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.database import Base, get_taipei_now


class KitchenNote(Base):
    __tablename__ = "kitchen_note"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    # Validated against KITCHEN_NOTE_KINDS in the schema layer.
    kind = Column(String, nullable=False, server_default=text("'reference'"))
    # http or https only, validated in the schema layer: a javascript: URL
    # rendered as a link is an XSS.
    url = Column(String, nullable=True)
    body = Column(Text, nullable=True)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    labels = relationship("Label", secondary="kitchen_note_label")
    images = relationship(
        "KitchenNoteImage",
        back_populates="kitchen_note",
        cascade="all, delete-orphan",
        order_by="KitchenNoteImage.position",
    )

    __table_args__ = (
        CheckConstraint("btrim(title) <> ''", name="ck_kitchen_note_has_a_title"),
    )

    @property
    def display_name(self) -> str:
        """What an image's owner list calls this note - its title, since a
        note has no name slots for `NameFallbackMixin` to fall back over."""
        return self.title


class KitchenNoteLabel(Base):
    """Both sides CASCADE, as `ingredient_label` and `recipe_label`."""

    __tablename__ = "kitchen_note_label"

    kitchen_note_id = Column(
        Integer, ForeignKey("kitchen_note.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed on its own, as recipe_label's: the composite key leads with the
    # note, so it cannot serve the label filter nor the cascade from a label.
    label_id = Column(
        Integer, ForeignKey("label.id", ondelete="CASCADE"), primary_key=True, index=True
    )
