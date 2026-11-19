# Public to read, with writes behind Cloudflare Access on their own prefix

There are no accounts and no login. There is one user, and the reading half
is meant to open on a phone without signing in. The write surface needs a
gate regardless, and putting it at the edge means no password is stored and
no auth code is written. `docs/api.md`, "The read/write split is the security
boundary", says how it is enforced.

**This is why reads and writes are split by path prefix**, where `media`
splits them by a comment banner and an auth dependency inside one router file.
Access is all-or-nothing per path, so the split has to be in the URL or there
is no gate. It had to be in place from the first route: cheap then, invasive
later.
