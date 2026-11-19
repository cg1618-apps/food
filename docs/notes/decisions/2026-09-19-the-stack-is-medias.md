# The stack is media's: FastAPI, PostgreSQL, React + Vite, Alembic

food uses the media tracker's stack, so the platform has one framework and one
deploy shape to hold in mind.

Rejected:

- **Django.** It would have suited a library-of-entities app well and cost far
  less code per app, but it adds a second framework and a different deploy
  shape to the box.
- **A server-rendered frontend with htmx.** It would remove the build step,
  the second dev port and the stale-bundle failure mode entirely. It was not
  rejected for a technical defect but for consistency with an app that
  already works, and it is worth revisiting if the frontend turns out to be
  thin.
