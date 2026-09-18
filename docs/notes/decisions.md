# Decisions

Why food is the way it is. Unlike the rest of `docs/`, this page is allowed to
talk about the past: it records what was chosen, what was rejected, and the
reasoning that is still load-bearing.

## Platform decisions this app inherits

Recorded in `cg1618-apps/platform` rather than here, and summarised only so far
as they bind this app:

- **It is its own repository**, sharing no code with the other applications. The
  platform connects them by configuration, not by git pointers.
- **It shares one PostgreSQL**, with its own database and its own role.
- **It is `public`**, because repository rulesets and environments with required
  reviewers are free only for public repositories, and both gates depend on it.
- **No `pull_request`-triggered job may run on the self-hosted runner.**

## Decisions for this application

None yet. The first will be the stack.
