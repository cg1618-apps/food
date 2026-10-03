"""加熱: a page of notes on how to heat or reheat a food - a frozen toast, a
sausage, something from the microwave.

Standalone on purpose, as TBD is. A note relates to nothing else in the app:
it names the food in words rather than pointing at an ingredient or a dish,
because what it is about is usually a bought thing ("冷凍吐司") that has no
place in either library. An ingredient's own heating guide is a different
thing and stays on the ingredient.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Text

from app.database import Base, get_taipei_now


class HeatingNote(Base):
    __tablename__ = "heating_note"

    id = Column(Integer, primary_key=True)
    # What is being heated. Required: a note about nothing cannot be found.
    name = Column(String, nullable=False)
    # How, in the owner's words - free text, line breaks kept.
    body = Column(Text, nullable=True)
    # The owner's order on the page; a new note is given the end.
    sort_order = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    __table_args__ = (CheckConstraint("btrim(name) <> ''", name="ck_heating_note_has_a_name"),)
