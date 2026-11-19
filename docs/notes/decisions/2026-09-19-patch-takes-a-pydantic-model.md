# PATCH takes an all-optional Pydantic model

`PATCH` bodies are models with every field optional, applied with
`exclude_unset`, and `extra="forbid"`. A divergence from `media`, which takes a
raw `dict` through a shared helper that ignores unknown keys.

media's shape is load-bearing there for reasons that do not exist here -
association proxies onto a parent row, and seventeen heterogeneous endpoints.
`extra="forbid"` also refuses server-owned columns loudly instead of dropping
them silently. "Conventional beats clever" is the tiebreak.
