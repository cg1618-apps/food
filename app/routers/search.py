"""The universal search behind the top bar's search box and the /search page.

Public and read-only, so it is a read router with no write counterpart. The
matching and ranking are app/services/universal_search.py's.
"""

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.routing import read_router
from app.services import universal_search

router = read_router("search", "Search")


@router.get("", response_model=schemas.SearchResponse)
def search_everything(
    q: str = Query(default="", description="Matches names and aliases, as each library does"),
    limit: int = Query(
        default=universal_search.DEFAULT_LIMIT,
        ge=1,
        le=universal_search.MAX_LIMIT,
        description="Rows per bucket",
    ),
    db: Session = Depends(get_db),
):
    """One bucket per kind - dishes, recipes, ingredients, notes, authors,
    heating, tbd - each best match first. A blank `q` answers every bucket
    empty rather than everything."""
    buckets = universal_search.search(db, q, limit)
    return schemas.SearchResponse(
        query=q,
        results=schemas.SearchBuckets(
            **{key: [vars(hit) for hit in hits] for key, hits in buckets.items()}
        ),
    )
