"""An author's page. Reads are public; the gallery PUT sits behind Access.

The list, create, update and delete of an author are the vocabulary
factory's (app/routers/vocabulary.py), under the same `/authors` prefix, and
are not repeated here. What the factory has no shape for is an author read on
its own: the detail - names, remark, links, gallery, and the recipes whose
sources name the author - the delete preview, and the gallery, which is
written by its own PUT as every gallery is.

The delete stays the factory's: refused with a 409 carrying `usage_count`
while any source names the author. `cascade` is the preview the delete
dialog reads first, so the refusal is said before the button is pressed.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Author, AuthorImage
from app.routers.recipe import summary
from app.routing import read_router, write_router
from app.services import authors, images, recipes, vocabularies

router = read_router("authors", "Authors")
edit = write_router("authors", "Authors")


def _detail(db: Session, row: Author) -> schemas.AuthorDetail:
    listed = recipes.search(db, author_id=[row.id])
    return schemas.AuthorDetail(
        id=row.id,
        display_name=row.display_name,
        name_cn=row.name_cn,
        name_en=row.name_en,
        sort_order=row.sort_order,
        usage_count=vocabularies.usage(db, Author).get(row.id, 0),
        notes=row.notes,
        links=[schemas.AuthorLinkResponse(label=link.label, url=link.url) for link in row.links],
        recipe_count=len(listed),
        cover=images.cover(row.images),
        images=images.attached(row.images),
        recipes=[summary(recipe) for recipe in listed],
    )


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("/{author_id}", response_model=schemas.AuthorDetail)
def get_author(author_id: int, db: Session = Depends(get_db)):
    return _detail(db, authors.get(db, author_id))


@router.get("/{author_id}/cascade", response_model=schemas.AuthorCascade)
def cascade_preview(author_id: int, db: Session = Depends(get_db)):
    """What refuses a delete: the `sources` naming the author and the
    `recipes` they belong to. Neither is echoed on the delete."""
    authors.get(db, author_id)
    return authors.cascade_counts(db, author_id)


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


@edit.put("/{author_id}/images", response_model=schemas.AuthorDetail)
def set_author_images(
    author_id: int,
    payload: list[schemas.ImageAttachmentIn],
    db: Session = Depends(get_db),
):
    """Replace the gallery, in order. Position 0 is the cover."""
    author = authors.get(db, author_id)
    images.set_images(db, author, "images", AuthorImage, payload)
    return _detail(db, authors.get(db, author_id))
