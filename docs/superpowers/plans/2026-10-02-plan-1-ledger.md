# Plan 1 — execution ledger and resume point

Working scaffolding: deleted with the plan when branch 1 merges. Copied out of
the git-ignored `.superpowers/sdd/` workspace so the work can continue on the
other machine.

## Resume here

Branch `feat/ingredient-storage-heating-images`. Tasks 1–6 are implemented and
reviewed; the final whole-branch review (opus) said "ready with fixes". The
final fix wave was stopped mid-way when work moved machines:

- **I1 done** — `02a91ff` (old form keeps a migrated row's min in step with
  the edited max; vitest helper).
- **M1, M2, M3: tests committed, implementation NOT done** — `test:` commit
  after `02a91ff`. M2 and M3 tests fail until fixed; M1's test should already
  pass (it proves the downgrade prefers the maximum).
  - M2: remove `sort_order` from `HeatingIn` and `LinkIn` in
    `app/schemas/ingredient.py` (order is list order); keep it on the
    responses (give `LinkResponse` its own field if it inherits `LinkIn`);
    update `docs/api.md` if it documents the input field.
  - M3: in `app/services/images.py`, wrap the post-open processing in
    `normalise()` (exif_transpose, _to_rgb, thumbnail, encode) so any
    non-`AppError` exception becomes `AppError(422, "That file is not an
    image this app can read.")`.
  - M1: grep `docs/testing.md` and `docs/notes/decisions.md` for the
    "collapses to its maximum" claim and confirm it is now true as worded.
- **M6 not done** — `docs/deployment.md` rollback paragraph: add that the
  `i2storage` downgrade also drops `ingredient.rating`, all heating rows and
  all links.
- **M7 not done** — add four entries to `docs/open-items.md` in its existing
  voice: orphan files when the commit after an upload fails; two concurrent
  identical uploads share one `.part` name; the bomb-warning escalation
  (`warnings.catch_warnings`) is process-global, not thread-safe; and
  `ingredient.updated_at` does not change when only child rows change.

Then: full suite under the lock, ruff, one scoped re-review of the fix wave,
push, open the PR into `dev` (body: what changed per task, the module-1
defect Task 3 found, the migration chain `i1ngredients → v1ocabulary →
i2storage → m1images`, the lossy `i2storage` downgrade, the bind mount, and
**the open image-backup question for the platform** — no manager session was
running), wait for CI, merge, tear the branch down, then write plan 2.

Machine note: the company dev database `food` is at `m1images`.

## Ledger

Spec: docs/superpowers/specs/2026-10-02-recipes-and-ingredients-v2-design.md
Branch: feat/ingredient-storage-heating-images, cut from dev at 7c00f79 (MERGE_BASE)

## Pre-flight scan

| Pair / task | Produces → consumes | Finding |
| --- | --- | --- |
| T1 ↔ T2 | T1 `VocabRef`, `USAGE`, `ROUTERS`, `CookingMethod` → T2 heating FK, fixed_router appended to ROUTERS, counter replaced | consistent |
| T1 ↔ T2 ↔ T4 | head pins v1ocabulary → i2storage → m1images in test_health + test_migrations | consistent, sequential |
| T2 ↔ T3 | T2 delete params aliases/preservation/heating/links → T3 CRUD tests pass all four | consistent |
| T2 ↔ T4 | T2 `_summary()`, `_response()`, `_loaded()` in ingredient router/service → T4 adds cover/images to them | consistent |
| T4 ↔ T5 | `image_dir` default `data/images` → compose `./data/images:/app/data/images` (WORKDIR /app) | consistent |
| T1 self | seed counts in test (7 courses, 12 methods) vs lists in migration | match |
| T2 self | tests use state/range/heating/links/rating; code defines all; existing tests naming duration_days told to update | consistent |
| T3 self | tests only; fixes go to owning file | consistent |
| T4 self | tests patch `config.settings.image_dir` autouse before client builds mount; service reads at call time | consistent |
| T5 self | test string matches compose entry; existing single-file test passes on `images` | consistent |
| T6 self | docs + open-items + PR | consistent |
| Global "docs in same commit as behaviour" ↔ T1-T5 deferring docs to T6 | conflict | Ruling below |
| T1 Step 1 (cut branch) | already done by controller | Ruling below |

Ruling: docs for T1–T5 land in T6 on the same branch — the PR into dev carries behaviour and docs together, and data-model.md describes the schema as a whole, so three partial rewrites would each be wrong until the last — costs: intermediate commits on the branch lack docs (invisible to dev's consumers).
Ruling: T1 Step 1 is skipped — the controller already cut feat/ingredient-storage-heating-images from dev 7c00f79 with the spec and plan merged (PR #13) — costs nothing.

## Progress
Task 1: dispatched (BASE 7c00f79, implementer sonnet)
Task 1: ⚠️ resolved by controller — suite green per report (141 passed); PATCH name collision answers 409 via existing IntegrityError handler + new CONSTRAINT_MESSAGES (23505→409).
Task 1: minor (deferred): vocab delete-409 path unreachable until a real counter — Task 2's air_fryer test covers cooking-method refusal; courses/equipment get counters in plan 2
Task 1: minor (deferred): test_vocabularies docstring claims in-use fixtures that don't exist (plan-mandated)
Task 1: minor (deferred): renaming-away-every-name has no paired permitted case (drop one of two names)
Task 1: minor (deferred): PATCH {"sort_order": null} accepted by schema, refused only by NOT NULL backstop (422 via 23502)
Task 1: minor (deferred): v1ocabulary downgrade label branch has no in-use test
Task 1: minor (deferred): no test for PATCH rename onto an existing name (409)
Task 1: complete (commits 7c00f79..412e8cd, review clean)
Task 2: dispatched (BASE 412e8cd, implementer sonnet)
Task 2: review (a8446b6) — Needs fixes: 2 Important (i2storage downgrade/upgrade-over-data untested; delete dialog 409 loop on stale heating/links count)
Ruling: promote reviewer Minor 1 (old form clobbers state/min on save) into fix round 1 — it silently loses data on dev between now and plan 4 — costs one small extra frontend edit if wrong.
Task 2: minor (deferred): HeatingIn.duration/notes and LinkIn.title not blank-normalised (store "")
Task 2: minor (deferred): _apply_heating queries IN () when no heating rows
Task 2: minor (deferred): IngredientSummary.fridge null means both "not computed" (parent/children) and "no fridge row"
Task 2: minor (deferred): app/schemas/__init__.py __all__ out of order
Task 2: minor (deferred): long lines (router, test, IngredientForm)
Task 2: minor (deferred): delete dialog sentence omits heating/links counts (plan-mandated; plan 4 rewrites dialog)
Task 2: fix round 1/5 dispatched (FIX_BASE a8446b6, resumed implementer)
Task 2: fix round 1/5 (3 addressed, 0 open; commits a8446b6..29d03f0)
Task 2: complete (commits 412e8cd..29d03f0, review clean)
Task 3: dispatched (BASE 29d03f0, implementer sonnet)
Task 3: defect found+fixed: PATCH re-sending an existing alias / (state,method) storage row was 409 (INSERT-before-DELETE on wholesale replace) — dfcfad1
Task 3: minor (deferred): conftest rollback after a refused request discards uncommitted fixture rows (latent; add docstring note)
Task 3: minor (deferred): no test for case-only alias change or preservation-row removal
Task 3: minor (deferred): _apply_aliases `in wanted` list scan
Task 3: complete (commits 29d03f0..054ab58, review clean)
Task 4: dispatched (BASE 054ab58, implementer sonnet)
Task 4: minor (deferred): SPA /images guard test is vacuous (mount claims /images/...); add GET /images → 404
Task 4: minor (deferred): bomb-warning escalation via warnings.catch_warnings is process-global/thread-unsafe; 50–100 MP band untested — explicit w*h check would be deterministic
Task 4: minor (deferred): MAX_IMAGE_PIXELS reassigned per call (set once at import)
Task 4: minor (deferred): concurrent identical uploads share one .part name (use a unique temp name)
Task 4: minor (deferred): size cap bounds processing not receipt (multipart spools first) — document in Task 6
Task 4: minor (deferred): main.py comment says dir created on first upload; code creates eagerly — fix in Task 6
Task 4: minor (deferred): upload_image runs full attachment_counts; list_images builds used-id list in Python
Task 4: minor (deferred): tests leave PIL images unclosed; no unused=false test
Task 4: minor (deferred): upload writes files before DB insert — failed commit leaves orphan files (implementer concern)
Task 4: complete (commits 054ab58..ed4d3fd, review clean)
Task 5: ⚠️ resolved by controller — docker-compose.prod.yml environment block sets only PORT (read earlier); dockerfile has no USER so container runs as root, host dir ownership not an issue
Task 5: minor (deferred): IMAGE_DIR default is relative; relies on CWD /app (could set absolute in compose)
Task 5: complete (commits ed4d3fd..ce3966a, review clean)
Ruling: Task 6 is split — a subagent writes the docs (steps 1–3, plus the main.py comment fix and the size-cap doc note from Task 4's minors); the controller does the running-app verification, the manager question and the PR (steps 4–6) — platform CLAUDE.md keeps opening/merging PRs and anything needing the owner in the main session — costs nothing.
Task 6: review (a13f39c) — Needs fixes: 1 Important (.env.example lacks IMAGE_DIR/MAX_IMAGE_UPLOAD_MB) + verify downgrade collapse sentence; fix round 1/5 dispatched (resumed)
Task 6: fix round 1 committed 1bedcc3 (.env.example settings, api.md rewrap; downgrade sentence verified unchanged)
Task 6: step 4 verified by controller in running app (127.0.0.1:8001, dev DB upgraded to m1images): create/edit (min kept, max 7→10)/detail/delete via dialog OK; seeded categories+labels listed; image upload→attach→serve 200 image/jpeg→delete 409 owners→clear→delete 204→serve 404
Task 6: minor (deferred): detail page + category counts stale after save until reload (pre-existing cache-invalidation gap, plan 4)
Task 6: minor (deferred): ingredient.updated_at does not change when only child rows (storage/heating/links/aliases) change
Task 6: note: Chrome via `localhost` left API requests pending (browser connection state), 127.0.0.1 fine — environment, not app
Task 6: step 5: no manager session running (ListAgents) — backup question goes to owner + PR body
Task 6: fix round 1/5 (2 addressed, 0 open; commits a13f39c..1bedcc3)
Task 6: complete (commits ce3966a..1bedcc3, review clean; steps 4–5 by controller, step 6 pending final review)
Final review (opus, 7c00f79..1bedcc3): With fixes — I1 old form 422s when lowering days on migrated min=max rows; minors M1–M8; deferred-minor triage all CAN WAIT/RESOLVED
Ruling: final fix wave = I1 + M1 (downgrade test proves max-preferred) + M2 (drop ignored sort_order from HeatingIn/LinkIn) + M3 (normalise() errors → 422) + M6 (deployment.md rollback loss names rating/heating/links) + M7 (open-items entries for orphan files, shared .part, process-global warning filter, updated_at on child edits) — each is minutes and M7 is required by the platform's tracking rule since the ledger is deleted — costs one fix dispatch.
Ruling: M4 (404 vs 422 for unknown ids in a body) deferred to plan 2, which must choose one convention for recipe lines — costs a later consistency pass if plan 2 picks 422.
Ruling: M5 (plan's OWNER_TABLES type typo) not fixed — the plan is scaffolding deleted when the work ends and the code is right — costs nothing.
Ruling: M8 nits not fixed — gitignored, harmless — costs nothing.
