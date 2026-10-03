"""TBD: a page of loose notes - an optional name and any number of links.

Standalone on purpose. An entry relates to nothing else in the app: no
ingredient, recipe, label or picture points at it and it points at none of
them. It is somewhere to drop a thing before deciding what it is.

An entry needs a name or at least one link. A CHECK cannot see the child
table, so that rule is the service's (app/services/tbd.py); the database
holds the half it can - a link's url is never blank.
"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base, get_taipei_now


class TbdEntry(Base):
    __tablename__ = "tbd_entry"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    # The owner's order on the page; a new entry is given the end.
    sort_order = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=get_taipei_now)
    updated_at = Column(DateTime, default=get_taipei_now, onupdate=get_taipei_now)

    links = relationship(
        "TbdLink",
        back_populates="entry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TbdLink.position",
    )


class TbdLink(Base):
    """CASCADE: an entry deleted takes its links. Replaced wholesale on a save,
    so `position` is the order sent and carries no unique constraint - one
    would collide with the rows being replaced inside the same flush."""

    __tablename__ = "tbd_link"

    id = Column(Integer, primary_key=True)
    entry_id = Column(
        Integer, ForeignKey("tbd_entry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    # http or https only, normalised in the schema layer: a bare host is
    # stored with https:// in front of it.
    url = Column(String, nullable=False)
    label = Column(String, nullable=True)

    entry = relationship("TbdEntry", back_populates="links")

    __table_args__ = (CheckConstraint("btrim(url) <> ''", name="ck_tbd_link_has_a_url"),)
