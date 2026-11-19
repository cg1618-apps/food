# Decisions

Why food is the way it is. One file per decision, named
`YYYY-MM-DD-<topic>.md` after the day it was made: a `# Title`, then the
reasoning that still binds and the alternatives that were rejected, so nobody
proposes them again unaware. The platform's `CLAUDE.md`, "Decisions are one
file each", is the rule.

- **There is no index.** The date-prefixed file names are the index; a list
  here would be a file every pull request appends to.
- **A decision file holds the why, not the what.** What the system does today
  is on the matching page in `docs/` - `api.md`, `data-model.md`,
  `frontend.md`, `testing.md`, `deployment.md` - and a decision file points
  there rather than repeating it.
- **A decision that stops binding is deleted.** One a later decision reverses
  is deleted in the same commit that adds the reversal; git keeps the history.
- **A deliberate divergence from `media`** - the platform's reference
  implementation - is a decision, and is recorded here with its reason, so a
  later reader can tell a decision from an accident.
