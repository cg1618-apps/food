"""Recipe templates. Reads are public; writes sit behind Access.

A template is a named skeleton - lines and steps in their groups, methods,
equipment, servings, time - that the new-recipe form starts from. The list is
light (names and counts); the detail is the body resolved into the recipe
response's shapes, with `dropped` counting references that no longer exist.
Besides the usual writes, a template can be made from a recipe, and the order
of them all is saved in one call after a drag on 設定.
"""

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import RecipeTemplate
from app.routing import read_router, write_router
from app.services import recipe_templates

router = read_router("recipe-templates", "Recipe templates")
edit = write_router("recipe-templates", "Recipe templates")


def summary(row: RecipeTemplate) -> schemas.TemplateSummary:
    line_count, step_count = recipe_templates.counts(row)
    return schemas.TemplateSummary(
        id=row.id,
        name=row.name,
        sort_order=row.sort_order,
        line_count=line_count,
        step_count=step_count,
    )


def _response(db: Session, row: RecipeTemplate) -> schemas.TemplateResponse:
    body, dropped = recipe_templates.resolve(db, row)
    return schemas.TemplateResponse(
        id=row.id,
        name=row.name,
        sort_order=row.sort_order,
        body=schemas.TemplateBody(**body),
        dropped=dropped,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ==========================================
# PUBLIC READS
# ==========================================


@router.get("", response_model=list[schemas.TemplateSummary])
def list_templates(db: Session = Depends(get_db)):
    """Every template, in the owner's order: a bare array."""
    return [summary(row) for row in recipe_templates.listed(db)]


@router.get("/{template_id}", response_model=schemas.TemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    return _response(db, recipe_templates.get(db, template_id))


# ==========================================
# WRITES - behind Cloudflare Access
# ==========================================


# Registered before the /{template_id} routes, so "order" is never read as an id.
@edit.put("/order", response_model=list[schemas.TemplateSummary])
def reorder_templates(payload: schemas.TemplateOrderIn, db: Session = Depends(get_db)):
    """Save the order after a drag; answers the list. `ids` must be exactly
    the current templates, each once, or it is a 422 and changes nothing."""
    return [summary(row) for row in recipe_templates.reorder(db, payload.ids)]


@edit.post("", response_model=schemas.TemplateResponse, status_code=201)
def create_template(payload: schemas.TemplateCreate, db: Session = Depends(get_db)):
    return _response(db, recipe_templates.create(db, payload))


@edit.post(
    "/from-recipe/{recipe_id}", response_model=schemas.TemplateResponse, status_code=201
)
def create_template_from_recipe(
    recipe_id: int, payload: schemas.TemplateFromRecipe, db: Session = Depends(get_db)
):
    """A new template of that recipe's structure - 存成範本 on its page."""
    return _response(db, recipe_templates.from_recipe(db, recipe_id, payload.name))


@edit.patch("/{template_id}", response_model=schemas.TemplateResponse)
def update_template(
    template_id: int, payload: schemas.TemplateUpdate, db: Session = Depends(get_db)
):
    return _response(db, recipe_templates.update(db, template_id, payload))


@edit.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """Nothing refers to a template, so nothing blocks deleting one."""
    recipe_templates.delete(db, template_id)
    return Response(status_code=204)
