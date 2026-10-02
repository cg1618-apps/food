"""Every schema, re-exported so call sites write `schemas.IngredientResponse`."""

from app.schemas.image import (
    AttachedImage,
    CoverRef,
    ImageAttachmentIn,
    ImageDetail,
    ImageOwner,
    ImageSummary,
)
from app.schemas.ingredient import (
    HeatingIn,
    HeatingResponse,
    IngredientCreate,
    IngredientResponse,
    IngredientSummary,
    IngredientUpdate,
    LinkIn,
    LinkResponse,
    PreservationIn,
    PreservationResponse,
    StorageRange,
)
from app.schemas.ingredient_category import (
    CategoryCreate,
    CategoryNode,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.schemas.vocabulary import (
    VocabRef,
    VocabularyCreate,
    VocabularyResponse,
    VocabularyUpdate,
)

__all__ = [
    "AttachedImage",
    "CoverRef",
    "ImageAttachmentIn",
    "ImageDetail",
    "ImageOwner",
    "ImageSummary",
    "HeatingIn",
    "HeatingResponse",
    "CategoryCreate",
    "CategoryNode",
    "CategoryResponse",
    "CategoryUpdate",
    "IngredientCreate",
    "IngredientResponse",
    "IngredientSummary",
    "IngredientUpdate",
    "LabelCreate",
    "LabelResponse",
    "LabelUpdate",
    "LinkIn",
    "LinkResponse",
    "PreservationIn",
    "PreservationResponse",
    "StorageRange",
    "VocabRef",
    "VocabularyCreate",
    "VocabularyResponse",
    "VocabularyUpdate",
]
