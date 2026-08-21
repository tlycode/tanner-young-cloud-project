# Flask Ecommerce App

A server-rendered ecommerce web application built with Python and Flask, developed as part of the Cloud Computing course (UCBX). It covers the full storefront loop — browse, review, cart, checkout, order history, returns and complaints — plus an admin back office, and ships with a round-robin **load balancer** that simulates running the app behind an auto-scaling pool of instances.

## Features

**Storefront**
- Product catalog with detail pages, tag filtering, and product images
- Star ratings and reviews — one review per user per product, editable and deletable by its author
- Shopping cart (session-backed) with quantity updates and removal
- Mock checkout with a shipping-address form — no real payment is processed
- Order history: past orders, order detail, **Buy Again** (re-adds an order's items to the cart), return requests, and complaint submission

**Accounts**
- Registration and login with session management (Flask-Login)
- Password reset flow via signed, time-limited tokens (the reset link is written to the application log rather than emailed — see [Password Reset](#password-reset))

**Admin**
- Role-gated admin area (`is_admin` + `@admin_required`)
- Product management UI: create, edit, delete, and **bulk-create** placeholder products for testing
- User management — promote other accounts to admin
- Order lookup by ID and a complaints queue

**Infrastructure**
- Round-robin [load balancer](load_balancer/README.md) with health checks and dynamic backend discovery
- Dockerfile for a self-contained image
- GitHub Actions CI: pytest suite + Docker build on every push and PR

## Tech Stack

- **Framework:** Flask 3.x
- **Database:** SQLAlchemy ORM with SQLite (dev) / PostgreSQL (prod)
- **Auth:** Flask-Login + Werkzeug password hashing; `itsdangerous` for reset tokens
- **Templates:** Jinja2 (server-rendered HTML)
- **Load balancer:** Flask + `requests` (see `load_balancer/`)
- **Testing:** pytest

## Getting Started (Local)

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # edit DATABASE_URL, SECRET_KEY

# Run the development server
flask run --debug
```

The app will be available at `http://localhost:5000`. Tables are created automatically on startup (`db.create_all()` in the app factory), so there is no migration step to run for a fresh database.

**Next step for a brand-new database:** you have zero users and zero admins. Create the first admin with `flask create-admin <email>` — see [Admin Setup](#admin-setup) — then log in and add products.

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs session cookies, CSRF tokens, and password-reset tokens | `dev` (change it) |
| `DATABASE_URL` | SQLAlchemy connection string | none — set it (e.g. `sqlite:///app.db`) |
| `PORT` | Port `run.py` binds to | `5000` |
| `FLASK_APP` | Entry point for the `flask` CLI | `run.py` |

## Running on Codio

Codio is a browser-based cloud IDE. There is no separate deploy step — you run the app directly inside the Codio box and access it via a generated public URL.

**First-time setup** (run once in the Codio terminal):

```bash
# Clone your repo into the workspace
git clone <your-repo-url> .

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Open .env and set a real SECRET_KEY value
```

**Running the app:**

Use the **Run** menu in the Codio IDE and select **"Run Flask App"** — this is pre-configured in [`.codio`](.codio) to start Flask on port 3000 bound to `0.0.0.0`.

Or run manually:
```bash
source venv/bin/activate
flask run --host=0.0.0.0 --port=3000
```

Then click **Preview → "Flask App"** in the Codio IDE to open the app in your browser. Codio routes the request through a public URL in the format `https://your-box-name-3000.codio.io`.

**Port differences:**

| Environment | Port | URL |
|-------------|------|-----|
| Local | 5000 | `http://localhost:5000` |
| Codio | 3000 | `https://your-box-name-3000.codio.io` |

The port is controlled by the `PORT` environment variable in `.env`. It defaults to `5000` if not set. On Codio, add `PORT=3000` to your `.env` file (or the `.codio` run command handles it directly via `--port=3000`).

## Admin Setup

Admin-only pages (`/admin/users`, product management, order lookup, complaints) are gated behind `is_admin` on the `User` model. Regular registration (`/register`) never sets this flag, and promoting a user to admin from the UI (`/admin/users`) itself requires being logged in as an admin — so on a fresh database with zero admins, you must bootstrap the first one from the command line.

**Bootstrap the first admin:**

```bash
flask create-admin admin@example.com
```

You'll be prompted to enter (and confirm) a password. This command is idempotent and safe to re-run:
- If no user with that email exists, it creates one with `is_admin=True`.
- If a user with that email already exists, it promotes them to admin (password is left unchanged).

The command needs `FLASK_APP=run.py` (already in `.env.example`) and reads the same `DATABASE_URL` as the app — so make sure you point it at the database you actually intend to promote a user in. When running multiple instances (see below), each has its own database file:

```bash
# Create an admin in a specific instance's database
DATABASE_URL=sqlite:///app2.db flask create-admin admin@example.com
```

Once the first admin exists, log in as that user and use **Manage Users** (`/admin/users`) to promote any other account — no further CLI use is needed.

> On Codio, run this command in the terminal after `pip install -r requirements.txt` and before (or after) starting the server, with the venv activated.

## Running Multiple Instances Behind the Load Balancer

The [`load_balancer/`](load_balancer/) directory contains a small Flask reverse proxy that distributes requests round-robin across multiple instances of this same app, and discovers those instances dynamically to simulate an auto-scaler adding and removing capacity.

Each backend instance needs **its own database file** — separate SQLite files avoid contention on a single file lock. Set `PORT` and `DATABASE_URL` per instance.

**Terminal 1 — backend on port 5000:**
```bash
PORT=5000 DATABASE_URL=sqlite:///app1.db python run.py
```

**Terminal 2 — backend on port 5001:**
```bash
PORT=5001 DATABASE_URL=sqlite:///app2.db python run.py
```

**Terminal 3 — the load balancer on port 8000:**
```bash
python load_balancer/load_balancer.py
```

Then visit **http://127.0.0.1:8000**. Each request is forwarded to one of the live backends in turn; the load balancer's terminal logs which backend served each request:

```
INFO:load_balancer:GET / -> http://127.0.0.1:5000 [200]
INFO:load_balancer:GET / -> http://127.0.0.1:5001 [200]
```

**Simulating auto-scaling.** With the load balancer already running, start a third backend on any port inside its scan range (default 5000–5010):

```bash
PORT=5002 DATABASE_URL=sqlite:///app3.db python run.py
```

Within one health-check interval (default 5s) the log shows `Backend(s) up: ['http://127.0.0.1:5002']` and traffic starts rotating across all three. Ctrl+C that instance and it logs `Backend(s) down: [...]` and drops out of rotation. With every backend stopped, the load balancer returns `503 Service Unavailable` rather than crashing.

**Key configuration** (full list in [`load_balancer/README.md`](load_balancer/README.md)):

| Variable | Purpose | Default |
|---|---|---|
| `LB_PORT` | Port the load balancer listens on | `8000` |
| `LB_PORT_RANGE_START` / `LB_PORT_RANGE_END` | Inclusive localhost port range scanned for backends | `5000` / `5010` |
| `LB_HEALTH_INTERVAL` | Seconds between health-check scans | `5` |
| `LB_TARGETS` | Comma-separated static backend list; **disables** auto-discovery | unset |

> **Expect inconsistent data across instances.** Each backend has its own database, so a logged-in session or cart may look different depending on which instance handled the request. That is inherent to this simulation — a production setup would share one database and/or use sticky sessions.

## Bulk Product Creation (Testing)

For seeding test data, admins can generate placeholder products in bulk instead of adding them one at a time:

1. Log in as an admin and go to **Add Product** (`/admin/products/new`).
2. Click **Bulk Add** to open the bulk-add modal.
3. Enter a count (1–100) and submit.

This creates that many `Bulk Product N` entries (`$9.99`, 99 stock, cycling through a set of placeholder images) via `POST /admin/products/bulk` ([`app/routes/admin.py:84`](app/routes/admin.py:84)). Useful for populating the catalog to test pagination, tag filtering, checkout/cart flows, or listing performance without hand-entering products — including generating load against the load balancer.

## Password Reset

`/forgot-password` issues a signed, time-limited token (`itsdangerous`) and **logs the reset URL to the application log** instead of sending an email — there is no mail server in this project. To reset a password, submit the form and copy the `Password reset requested for ...: http://.../reset-password/<token>` line out of the server's terminal output.

The response is deliberately identical whether or not the email is registered, so the form can't be used to enumerate accounts.

## Docker (Optional)

Docker is **not required** for local development or Codio. The venv workflow above is all you need day-to-day.

Docker is included for portability — it packages the app and its dependencies into a self-contained image that runs identically anywhere, without needing Python or a venv installed. It is also verified in CI on every push.

**Build and run with Docker:**
```bash
docker build -t flask-app .
docker run -p 5000:5000 flask-app
```

The app will be available at `http://localhost:5000`.

> Note: The Docker image uses SQLite and a placeholder `SECRET_KEY=changeme`. Override these at runtime for any real deployment:
> ```bash
> docker run -p 5000:5000 -e SECRET_KEY=your-real-key flask-app
> ```
>
> The image installs `requirements-docker.txt` (same as `requirements.txt` minus `psycopg2-binary`, which isn't needed for SQLite). The load balancer is not containerized — run it from the host.

## Running Tests

```bash
pytest -v
```

Tests run against an in-memory SQLite database with CSRF disabled, via fixtures in [`tests/conftest.py`](tests/conftest.py), so they never touch your development data. The same suite runs in GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) alongside a Docker build on every push and pull request to `main`.

## Project Structure

```
app/
  __init__.py       # Application factory (create_app), error handlers, `flask create-admin` CLI
  models.py         # SQLAlchemy models: User, Product, Tag, Review, Order, OrderItem, Complaint
  decorators.py     # @admin_required
  tag_utils.py      # Tag parsing / get-or-create helpers
  routes/
    auth.py         # /register, /login, /logout, /forgot-password, /reset-password/<token>
    main.py         # HTML pages: / (catalog + tag filter), /products/<id>
    products.py     # JSON API: GET/POST/PUT/DELETE /products
    cart.py         # /cart, add/update/remove, /cart/checkout (mock payment)
    orders.py       # /orders, order detail, buy-again, return request, complaint
    reviews.py      # Create / edit / delete product reviews
    admin.py        # /admin/* — products, bulk add, users, order lookup, complaints
  templates/        # Jinja2 HTML templates (incl. admin/ subfolder)
load_balancer/
  load_balancer.py  # Round-robin proxy with health checks + backend auto-discovery
  README.md         # Detailed load balancer docs
config.py           # Configuration from environment variables
run.py              # Entry point (honors PORT)
tests/              # pytest test suite
```

---

## Security

This project was developed with security as a first-class concern. Below is an account of what was implemented and what was intentionally deferred.

### Implemented

**Password Hashing**
All passwords are hashed using Werkzeug's PBKDF2-SHA256 implementation before storage. Plaintext passwords are never persisted. A minimum password length of 8 characters is enforced at registration and on password reset.

**CSRF Protection**
All HTML forms are protected against Cross-Site Request Forgery using `flask-wtf`. A CSRF token is generated per-session and validated on every state-changing POST request. Submitting a form without a valid token returns a `400` error.

**Input Sanitization**
- The product update endpoint uses a field whitelist (`ALLOWED_UPDATE_FIELDS`) to prevent mass assignment attacks — callers cannot overwrite internal fields like `id` or `created_at` by including them in the request body.
- The product creation endpoint validates that a name is present and that price is non-negative, returning a `400` for invalid input.
- Review ratings are validated to be integers in the 1–5 range, and a database unique constraint enforces one review per user per product.
- Tag names are trimmed, lowercased, deduplicated, and length-capped before being persisted.
- Password length is validated before hashing to prevent empty or trivially short passwords.

**Password Reset Tokens**
Reset links are signed with `itsdangerous` and expire, so they can't be forged or replayed indefinitely. `/forgot-password` returns the same response for registered and unregistered emails to prevent account enumeration.

**Error Handling**
Custom `403`, `404`, and `500` error handlers prevent Flask from returning raw error pages that could expose internal route structure or stack traces. All errors render minimal HTML templates.

**Logging**
Security-relevant events are logged via Flask's built-in logger:
- Successful and failed login attempts (with the email used)
- New user registrations, password reset requests and completions
- Product creation, update, and deletion
- Order placement, return requests, and complaint submissions

This creates an audit trail for detecting abuse or debugging incidents.

**Authentication & Authorization**
Cart checkout, order history, and review actions require an authenticated session via `@login_required`. Users may only view and act on their *own* orders — order access is ownership-checked, not just login-checked (admins are the deliberate exception, for support lookups). Unauthenticated requests are redirected to the login page rather than receiving a 401, which is appropriate for a browser-facing app.

**Role-Based Access Control**
The `User` model has an `is_admin` field enforced via the `@admin_required` decorator ([`app/decorators.py`](app/decorators.py)), gating product write operations (including the JSON API), the `/admin/users` panel, order lookup, and the complaints queue to admins only. See [Admin Setup](#admin-setup) above for bootstrapping the first admin account.

---

### Not Implemented (and Why)

**Rate Limiting**
Brute-force protection on the login endpoint would require `flask-limiter` and a backing store (Redis or in-memory). This adds meaningful infrastructure complexity that is out of scope for a course project. In a production deployment, rate limiting would be handled at the reverse proxy or API gateway layer (e.g., nginx, Cloudflare) rather than in application code.

**CORS Policy**
CORS headers are only relevant when a browser-based frontend on a different origin makes API requests. This application is fully server-rendered — the browser never makes cross-origin requests — so CORS configuration provides no security benefit here. It would become relevant if the JSON API were consumed by a separate React or mobile frontend.

**HTTPS**
TLS termination is an infrastructure concern, not an application concern. In production, HTTPS would be configured at the web server (nginx) or handled automatically by the hosting platform (Heroku, Render, Railway). Hardcoding HTTPS redirects in Flask application code is fragile and unnecessary when the deployment environment handles it correctly.

**Session Timeout**
Flask-Login sessions persist until the browser is closed (session cookies). Explicit server-side session expiry (e.g., 30-minute idle timeout) was not configured. For a course project handling no real user data, the risk is low. Production apps handling sensitive data should set `PERMANENT_SESSION_LIFETIME` and call `login_manager.refresh_view` for re-authentication.

**Hardened Load Balancer**
`load_balancer/load_balancer.py` is a teaching simulation, not a production proxy: it runs on the Flask development server, trusts and forwards client headers, has no TLS, no rate limiting, no request-size limits, and no sticky sessions. Real deployments would use nginx, HAProxy, or a cloud load balancer.
