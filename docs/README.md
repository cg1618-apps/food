# Documentation for food

Start here. Every page describes the system **as it is**, in the present tense —
never how it got here. The record of how things changed lives in git history and
in `notes/`.

| Page | What it holds |
| --- | --- |
| `data-model.md` | The tables, what each column is for, and why deletion behaves differently per relationship. |
| `api.md` | The routes, the read/write split that Cloudflare Access gates, the error shape, and which status a constraint violation answers. |
| `deployment.md` | How a deploy runs, what a rollback costs as data, and where the dumps are. What `bin/rollback` points at when it freezes. |
| `testing.md` | How the suite is arranged, and which tests are load-bearing while looking like decoration. |
| `frontend.md` | The pages, the layering, and why there is no route guard. |
| `logging.md` | What a log line looks like, why uvicorn's loggers are taken over, and why an inbound `X-Request-ID` is validated. food's half of a platform contract. |
| `notes/decisions.md` | Why things are the way they are, including rejected alternatives and the divergences from `media`. The one page allowed to talk about the past. |
| `superpowers/specs/` | Working scaffolding for a task in progress. **Deleted when that task ends**, with anything durable moved into a real page first. |

Pages appear as the application does.
