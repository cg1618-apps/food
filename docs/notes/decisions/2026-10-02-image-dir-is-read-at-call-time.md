# The image directory is a setting, read at call time

A divergence from `media`, which binds its directory at import - which is why
patching it in a test does nothing there. food reads `settings.image_dir` on
every call, so a test can point it at `tmp_path`. The `/images` mount is the
exception: it is built with the app, so the test client builds the app after
the directory is set.
