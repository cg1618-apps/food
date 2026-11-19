# A gallery per owner, attached on save

A divergence from `media`, whose `ImagePicker` holds one picture for an
owner's role and attaches it the moment it is picked. food's owners each hold
an ordered gallery whose first picture is the cover, so `GalleryPicker` is a
list - several uploads at once, reorder, a focus and a caption per picture -
and it attaches nothing itself: the form PUTs the whole gallery with its save,
after the first save for a new owner.

A cancelled form therefore leaves at most an unused picture in the library and
changes no owner, where media's attach-on-pick changes the owner before Save
is pressed.
