# The upload pipeline is media's, plus two additions

The re-encode to JPEG is `media`'s security control and is kept. Added:

- **The EXIF orientation is applied first**, because the re-encode drops the
  tag and portrait phone photos would otherwise be stored sideways.
- **A 50 megapixel ceiling**, so a small PNG declaring 30000 by 30000 pixels
  is a 422 and not a worker eating memory.

Both are tested. `docs/api.md`, "Images", has the behaviour.
