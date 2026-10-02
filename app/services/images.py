"""Reading an upload, normalising it, storing it, and deleting it.

Media's pipeline (media/app/services/integrations/image_library.py), carried
over: the extension and Content-Type are ignored; Pillow verifies, then the
image is reopened and RE-ENCODED to JPEG. The re-encode is the security
control - it strips EXIF (GPS included) and anything riding in the file - so
nothing that was uploaded is ever served as uploaded.

Two additions media does not have, both because these are phone photographs:
the EXIF orientation is applied BEFORE the metadata is dropped, or every
portrait photo lands sideways; and a pixel ceiling turns a decompression bomb
into a 422 rather than a worker eating memory.

IMAGE_DIR is read from `config.settings` on every call, never bound at import.
Media's cover route imports its directory by value, which is why patching it
in a test does nothing there.
"""

import hashlib
import io
import os
import warnings
from pathlib import Path

from fastapi import UploadFile
from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import config
from app.errors import AppError
from app.models import Image, Ingredient, IngredientImage

LONG_EDGE = 2000
THUMB_EDGE = 400
JPEG_QUALITY = 88
CHUNK = 1024 * 1024
# ~50 megapixels: well above any phone camera, far below a bomb.
MAX_PIXELS = 50_000_000

# (attachment model, owner type name, owner model). Plans 2 and 3 append their
# gallery tables here; owners() and attachment counts read only this list.
OWNER_TABLES: list[tuple[type, str, type]] = [
    (IngredientImage, "ingredient", Ingredient),
]


def image_dir() -> Path:
    return Path(config.settings.image_dir)


def image_url(key: str) -> str:
    return f"/images/{key}"


def _read_capped(upload: UploadFile) -> bytes:
    limit = config.settings.max_image_upload_mb * 1024 * 1024
    if upload.size is not None and upload.size > limit:
        raise AppError(413, f"Images are limited to {config.settings.max_image_upload_mb} MB.")
    data = bytearray()
    while chunk := upload.file.read(CHUNK):
        data.extend(chunk)
        if len(data) > limit:
            raise AppError(
                413, f"Images are limited to {config.settings.max_image_upload_mb} MB."
            )
    return bytes(data)


def _open(raw: bytes) -> PILImage.Image:
    PILImage.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with warnings.catch_warnings():
            # Pillow WARNS between 1x and 2x the ceiling and raises above it;
            # both are a bomb as far as this app is concerned.
            warnings.simplefilter("error", PILImage.DecompressionBombWarning)
            PILImage.open(io.BytesIO(raw)).verify()
            image = PILImage.open(io.BytesIO(raw))
            image.load()
    except (PILImage.DecompressionBombError, PILImage.DecompressionBombWarning):
        raise AppError(422, "That image is too large to process.") from None
    except Exception:
        raise AppError(422, "That file is not an image this app can read.") from None
    return image


def _to_rgb(image: PILImage.Image) -> PILImage.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = PILImage.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def _jpeg(image: PILImage.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def normalise(raw: bytes) -> tuple[bytes, bytes, int, int]:
    """(full JPEG, thumbnail JPEG, width, height) of the normalised image.

    A file can open cleanly and still fail later - a malformed EXIF block in
    exif_transpose, a truncated stream at encode time. Those are the upload's
    fault, not the server's, so they are a 422 like a file that fails to open.
    """
    image = _open(raw)
    try:
        image = _to_rgb(ImageOps.exif_transpose(image))
        image.thumbnail((LONG_EDGE, LONG_EDGE))
        thumb = image.copy()
        thumb.thumbnail((THUMB_EDGE, THUMB_EDGE))
        return _jpeg(image), _jpeg(thumb), image.width, image.height
    except Exception:
        raise AppError(422, "That file is not an image this app can read.") from None


def _write(key: str, data: bytes) -> None:
    path = image_dir() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    partial.write_bytes(data)
    os.replace(partial, path)


def store_upload(db: Session, upload: UploadFile) -> tuple[Image, bool]:
    full, thumb, width, height = normalise(_read_capped(upload))
    checksum = hashlib.sha256(full).hexdigest()
    storage_key = f"library/{checksum}.jpg"
    thumb_key = f"library/thumbs/{checksum}.jpg"

    existing = db.query(Image).filter(Image.checksum == checksum).one_or_none()
    # Written again even when the row exists: if the file was lost, an
    # identical re-upload is how it comes back.
    _write(storage_key, full)
    _write(thumb_key, thumb)
    if existing is not None:
        return existing, False

    image = Image(
        checksum=checksum,
        storage_key=storage_key,
        thumb_key=thumb_key,
        original_filename=upload.filename,
        byte_size=len(full),
        width=width,
        height=height,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image, True


def attachment_counts(db: Session) -> dict[int, int]:
    counts: dict[int, int] = {}
    for model, _, _ in OWNER_TABLES:
        for image_id, n in db.query(model.image_id, func.count(model.id)).group_by(model.image_id):
            counts[image_id] = counts.get(image_id, 0) + n
    return counts


def owners(db: Session, image_id: int) -> list[dict]:
    found = []
    for model, type_name, owner_model in OWNER_TABLES:
        owner_fk = next(
            c for c in model.__table__.columns if c.name.endswith("_id") and c.name != "image_id"
        )
        rows = (
            db.query(owner_model)
            .join(model, getattr(model, owner_fk.name) == owner_model.id)
            .filter(model.image_id == image_id)
            .all()
        )
        found += [{"type": type_name, "id": r.id, "display_name": r.display_name} for r in rows]
    return found


def delete_image(db: Session, image: Image) -> None:
    attached = owners(db, image.id)
    if attached:
        raise AppError(409, "That image is still attached; remove it there first.", owners=attached)
    keys = (image.storage_key, image.thumb_key)
    db.delete(image)
    db.commit()
    for key in keys:
        (image_dir() / key).unlink(missing_ok=True)


def resolve_attachments(db: Session, entries) -> dict[int, Image]:
    """The images a gallery PUT names: 404 for an unknown id, 422 for a repeat."""
    ids = [entry.image_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise AppError(422, "The same image is listed twice.")
    found = {row.id: row for row in db.query(Image).filter(Image.id.in_(ids))} if ids else {}
    missing = [i for i in ids if i not in found]
    if missing:
        raise AppError(404, f"No such image: {missing[0]}.")
    return found
