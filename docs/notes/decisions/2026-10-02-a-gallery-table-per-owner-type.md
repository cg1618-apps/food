# A gallery table per owner type, not media's polymorphic table

`media` has one attachment table keyed by `owner_type` and `owner_id`, which
nothing constrains, and records that nothing stops an attachment outliving its
owner. food has a small gallery table per owner type (ingredients, dishes,
recipes, kitchen notes, authors), each with real foreign keys, which removes
that whole class of defect for the price of one shared module's worth of
repetition. `images.OWNER_TABLES` is the one list the library's usage counts
and owner listings read, so a new owner type is registered there and needs no
code of its own.

The owner side cascades and the image side restricts: deleting an owner
removes its gallery and never a picture, and a picture still shown somewhere
cannot be deleted.
