# Course Project Journey

A record of how the Flask ecommerce app was built for the Cloud Computing course (UCBX) — the features added at each stage, the problems hit along the way, and the configuration decisions made to resolve them.

For instructions on running the finished app, see [`README.md`](README.md). This document is the *history*: what was built, in what order, and what had to be worked through to get there.

---

## Timeline at a Glance

| Phase | Dates | Focus | Outcome |
|---|---|---|---|
| 1 | Mar 14 | Scaffold | Starter repo and README |
| 2 | May 27 | Foundation | Flask app, auth, products, CI/CD, Codio, admin roles |
| 3 | Jul 6–17 | Storefront | Tags, bulk seeding, password reset, cart, mock checkout |
| 4 | Aug 1–11 | Depth | Reviews and ratings, real orders, returns, complaints |
| 5 | Aug 15–20 | Cloud | Load balancer, auto-scaling simulation, documentation |

The project grew from a 10-line `app.py` to seven data models, seven route blueprints, 94 tests, and a load balancer — across roughly five months.

---

## Phase 1 — Scaffold (March 14)

The repository began as a course-provided starter: an empty project with a README describing the assignment. Two commits, no application code yet.

---

## Phase 2 — Foundation (May 27)

The bulk of the architecture was established in a single intense session — six commits in under two hours.

### Features built

- **Flask application** with `create_app()` factory, environment-driven configuration, and SQLAlchemy models
- **Authentication**: registration, login, logout via Flask-Login with Werkzeug password hashing
- **Product catalog**: HTML listing and detail pages, plus a JSON API (`GET/POST/PUT/DELETE /products`)
- **CSRF protection** and custom `404`/`500` error pages, both included from the start rather than retrofitted
- **CI/CD**: GitHub Actions running pytest and a Docker build on every push and pull request
- **Codio configuration**: `.codio` run command and preview mapping for the browser IDE
- **Admin roles**: `is_admin` flag, `@admin_required` decorator, product management UI, and a user-promotion page

### Challenges worked through

**Restructuring from a single file into an application factory.**
The first commit was a flat `app.py` containing 10 lines. Once authentication, models, and multiple route groups arrived, that structure could not hold. `app.py` was deleted and replaced with a package: `app/__init__.py` exposing `create_app()`, `run.py` as the entry point, `config.py` for environment configuration, and `app/routes/` for blueprints. This made testing possible — the factory accepts a `test_config` override, which is what lets the suite run against an in-memory database.

**The scaffold Dockerfile did not match the app.**
The provided Dockerfile targeted Python 3.8, exposed port 80, set a placeholder `ENV NAME World`, and ran `python app.py` — a file that no longer existed. It was rewritten entirely: Python 3.12, port 5000, `FLASK_APP`/`DATABASE_URL`/`SECRET_KEY` environment variables, and `flask run --host=0.0.0.0` so the container accepts connections from outside itself.

**`psycopg2-binary` broke the Docker build.**
The PostgreSQL driver requires build tooling absent from the `python:3.12-slim` base image, and the container only uses SQLite anyway. Rather than bloat the image with compilers, the requirements were split: [`requirements.txt`](requirements.txt) for local and CI use, and [`requirements-docker.txt`](requirements-docker.txt) — identical but without `psycopg2-binary` — for the image. The file carries a comment saying exactly why it exists.

**`pytest` was not on PATH in CI.**
The CI job initially called `pytest -v` directly and failed. Changing it to `python -m pytest -v` resolved it, since that form runs the module through the active interpreter rather than depending on a console script being on PATH. It also ensures the project root is on `sys.path`, so `import app` resolves.

**Docker layer caching.**
The original Dockerfile copied the whole project *before* installing dependencies, meaning every source edit invalidated the cached `pip install`. The rewrite copies `requirements-docker.txt` first, installs, and only then copies the source — so dependency installation is re-run only when dependencies actually change.

**Port differences between local and Codio.**
Codio expects port 3000 and requires binding to `0.0.0.0`; local development defaults to 5000. This was solved by reading `PORT` from the environment in `run.py` with a 5000 fallback, letting a single codebase serve both without edits.

---

## Phase 3 — Storefront (July 6–17)

With the foundation stable, work shifted to what a shopper actually does.

### Features built

- **Tags with filtering**: a many-to-many `Product`↔`Tag` relationship, tag chips on the catalog, and `/?tag=<name>` filtering
- **Bulk product creation**: an admin tool generating up to 100 placeholder products at once
- **Password reset**: `/forgot-password` and `/reset-password/<token>` using signed, expiring tokens
- **Shopping cart**: session-backed, with quantity updates and item removal
- **Mock checkout**: a shipping-address form and order confirmation, with no real payment processing

### Challenges worked through

**Seeding test data by hand did not scale.**
Testing pagination, tag filters, and cart behavior needs many products, and adding them one at a time through a form is tedious. The bulk creation tool solved this — but the first version created products with `stock=0`, which meant every bulk product was unpurchasable and useless for exercising the very cart and checkout flows it was meant to support. Changing the default to `stock=99` made the generated catalog immediately usable.

**Tag input needed normalization.**
Free-text comma-separated tags invite duplicates and inconsistency — `Shoes`, `shoes`, and ` shoes ` would otherwise become three distinct rows. [`app/tag_utils.py`](app/tag_utils.py) centralizes the handling: trim, lowercase, truncate to 50 characters, and drop duplicates, with `get_or_create_tags()` reusing existing rows instead of inserting near-identical ones.

**Password reset without a mail server.**
A real reset flow emails a link, but this project has no SMTP service and adding one was out of scope. The compromise was to build the security-relevant half properly — `itsdangerous` signed tokens that expire and cannot be forged — and log the reset URL to the application console instead of sending it. Functionally complete and testable; only delivery is stubbed.

**Account enumeration in the reset form.**
A naive implementation reveals which emails are registered by responding differently to known and unknown addresses. `/forgot-password` deliberately returns an identical message either way, and logs both cases server-side.

**Undocumented admin bootstrap.**
The `flask create-admin` CLI command existed since Phase 2 but appeared nowhere in the README, making a fresh clone effectively unusable — registration never grants admin, and promoting a user requires already being an admin, so a new database was a locked door. Documenting the bootstrap path resolved a genuine chicken-and-egg problem.

---

## Phase 4 — Depth (August 1–11)

This phase converted mocked behavior into real persisted data.

### Features built

- **Reviews and star ratings**: one review per user per product, editable and deletable by its author, with average ratings on the catalog and detail pages
- **Real orders**: `Order` and `OrderItem` records persisted at checkout
- **Order history**: a "My Orders" page, per-order detail with shipping information, and a **Buy Again** action
- **Returns and complaints**: customer-initiated return requests and complaint submission
- **Admin support tools**: order lookup by ID and a complaints queue

### Challenges worked through

**Checkout was faking order numbers.**
The Phase 3 checkout generated a display string from a hash of the cart — `f"MOCK-{abs(hash(...)) % 1000000:06d}"` — and persisted nothing. The order vanished the moment the page rendered. Phase 4 replaced this with real `Order` and `OrderItem` rows, which is what made order history, returns, and complaints possible at all. Checkout also became `@login_required`, since order history is inherently per-user.

**Order line items had to survive product changes.**
Storing only a product foreign key means an order's displayed price changes whenever an admin edits that product, and the line breaks entirely if the product is deleted. `OrderItem` therefore *snapshots* `product_name` and `unit_price` at purchase time, and its `product_id` uses `ondelete='SET NULL'` — so a deleted product leaves order history intact and readable rather than corrupting it.

**Preventing duplicate reviews.**
Checking for an existing review in application code alone leaves a race condition where concurrent submissions both pass the check. A database-level `UniqueConstraint('product_id', 'user_id')` enforces the rule, with the resulting `IntegrityError` caught and surfaced as a friendly message.

**Rating input could not be trusted.**
Form values arrive as strings and may be missing, non-numeric, or out of range. `_parse_rating()` centralizes validation, returning `None` for anything that is not an integer from 1 to 5.

**Authorization needed ownership, not just login.**
`@login_required` alone would let any signed-in user read any order by guessing IDs. `_check_order_access()` compares `order.user_id` against the current user and aborts with `403` otherwise — with a deliberate exception allowing admins through, since order lookup is exactly what the support tools need.

**`__pycache__` files were tracked in git.**
`.gitignore` listed `__pycache__`, but the files had been committed *before* that rule existed, and gitignore does not apply to already-tracked files. Every Python run produced spurious modified-file noise. Untracking them with `git rm --cached` fixed it permanently.

---

## Phase 5 — Cloud (August 15–20)

The final phase addressed the course's core subject: running an application across multiple instances.

### Features built

- **Round-robin load balancer** ([`load_balancer/load_balancer.py`](load_balancer/load_balancer.py)) distributing requests across backend instances
- **Health checking** so failed backends are skipped rather than crashing the proxy
- **Dynamic backend discovery** — a background thread scans a port range and adjusts the rotation as instances appear and disappear, simulating an auto-scaler
- **Documentation** bringing the README in line with the full feature set

### Challenges worked through

**SQLite file locking across instances.**
Pointing several instances at one SQLite file causes lock contention, since SQLite permits only one writer at a time. Each backend was given its own database via `DATABASE_URL` (`app1.db`, `app2.db`, `app3.db`). This trades away shared state — documented honestly as a limitation rather than hidden, since a user routed to different instances may see different cart contents. A production system would use a shared PostgreSQL instance and/or sticky sessions.

**Relaying responses corrupted them.**
Forwarding a backend's headers verbatim breaks the response: `Content-Length` and `Transfer-Encoding` describe the *original* hop, and `Content-Encoding` announces a compression the proxy has already undone. Werkzeug then recomputes conflicting values and the client receives a malformed reply. A `HOP_BY_HOP_HEADERS` set is stripped before relaying so the framework recalculates them correctly.

**A static target list could not simulate auto-scaling.**
The first version round-robined over a fixed list read from `LB_TARGETS`, which is fine for demonstrating distribution but cannot show instances joining or leaving — the defining behavior of elastic infrastructure. The rewrite added a daemon thread that scans a configurable port range every few seconds, health-checks each candidate, and updates the rotation. Starting a backend inside the range brings it into service within one interval; stopping it removes it. `LB_TARGETS` was retained as an override for the static case.

**Shared state between threads.**
The health-check thread writes the target list while request handlers read it. A `threading.Lock` guards the list, and `itertools.count()` provides the round-robin counter — chosen because its increment is atomic, avoiding a second lock in the request path.

**Failures needed to degrade, not crash.**
Two distinct failure modes are handled: a backend dying *between* the health check and the request (caught, retried once against a different target, then `502`), and every backend being down (`503` rather than an unhandled exception).

**Documentation had fallen behind the code.**
By this point the README still described only auth, a catalog, and a JSON API. It listed two models where there were seven, and three route files where there were seven — omitting reviews, cart, checkout, orders, returns, complaints, tags, password reset, and the load balancer entirely. The final commit rewrote it, and the multi-instance workflow was *executed* rather than assumed: two backends plus the balancer confirmed round-robin distribution, a third backend started mid-run produced `Backend(s) up`, and stopping it produced `Backend(s) down`. The sample log output in the README is copied from that verified run.

---

## Testing Throughout

Tests accompanied features rather than following them. The suite reached **94 tests**:

| File | Tests | Covers |
|---|---|---|
| [`tests/test_admin.py`](tests/test_admin.py) | 28 | Admin gating, product management, bulk creation |
| [`tests/test_orders.py`](tests/test_orders.py) | 16 | Checkout, history, buy-again, returns, complaints |
| [`tests/test_products.py`](tests/test_products.py) | 14 | JSON API, validation, mass-assignment protection |
| [`tests/test_auth.py`](tests/test_auth.py) | 13 | Registration, login, password reset |
| [`tests/test_reviews.py`](tests/test_reviews.py) | 12 | Review creation, editing, deletion, ratings |
| [`tests/test_main.py`](tests/test_main.py) | 11 | Catalog, detail pages, tag filtering |

Two configuration decisions in [`tests/conftest.py`](tests/conftest.py) made this practical: an **in-memory SQLite** database (`sqlite:///:memory:`) so tests never touch development data and start clean, and **`WTF_CSRF_ENABLED: False`** so tests can POST directly without scraping tokens out of rendered HTML — while CSRF stays on everywhere else.

---

## Key Configuration Decisions

| Decision | Reason |
|---|---|
| Application factory (`create_app`) | Enables per-test configuration overrides and multiple instances in one process |
| All config from environment variables | One codebase runs on local, Codio, Docker, and CI unchanged |
| `PORT` with a 5000 default | Codio needs 3000, local uses 5000, no code edits between them |
| Split `requirements-docker.txt` | Omits `psycopg2-binary`, which needs build tooling absent from the slim image |
| `python -m pytest` in CI | Does not depend on console scripts being on PATH; fixes `sys.path` for imports |
| `db.create_all()` at startup | No migration step for a fresh database in a course context |
| Snapshotted order line items | Order history stays accurate when products are edited or deleted |
| Per-instance SQLite databases | Avoids write-lock contention between load-balanced instances |
| CSRF disabled only in tests | Keeps protection everywhere real while keeping tests readable |

---

## What Was Deliberately Left Out

Documented here so the omissions read as decisions rather than oversights. The README's Security section gives the full reasoning.

- **Rate limiting** — belongs at a reverse proxy or gateway, not in application code
- **CORS** — the app is fully server-rendered, so no cross-origin requests occur
- **HTTPS** — TLS termination is an infrastructure concern
- **Session timeouts** — low risk for a project holding no real user data
- **Email delivery** — no mail server; reset links are logged instead
- **Real payment processing** — checkout is explicitly mocked
- **A production-grade load balancer** — the included one is a teaching simulation on the Flask development server, not a replacement for nginx, HAProxy, or a cloud load balancer

---

## Closing Note

The recurring theme across all five phases is *replacing something provisional with something real*: a single file became an application factory, a scaffold Dockerfile was rewritten to match the app, a hashed fake order number became persisted records, and a fixed list of load balancer targets became live health-checked discovery. Each step was small enough to test, and the tests are what made the next step safe.
