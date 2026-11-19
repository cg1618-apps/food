# The edit pages send a signed-out browser through the Access login

Gating `/edit` as well as `/api/edit` puts the login in front of an edit page
opened by URL, but not one reached by a click inside the SPA, which never
reaches Access. So the edit pages probe `GET /api/edit/session` and, when
signed out, navigate the whole window through it - a path Access already
gates, so it works whether or not `/edit` is. `docs/frontend.md`, "Pages",
has the mechanism.

The probe is not a route guard: it renders the page whatever the answer and
refuses nothing.

Rejected:

- **Making every edit link a full document load.** Scattered across a dozen
  components, and still blind to a session that expires on an open page.
- **Reloading the page on a failed save.** It throws away the form being
  saved.
