# Flask Ecommerce App

A server-rendered ecommerce web application built with Python and Flask, developed as part of the Cloud Computing course (UCBX). The app supports user registration and authentication, a product catalog with detail pages, and a JSON API for product management.

## Features

- User registration and login with session management (Flask-Login)
- Product listing and detail pages (Jinja2 HTML templates)
- Admin JSON API for creating, updating, and deleting products
- SQLite database via SQLAlchemy (configurable to PostgreSQL for production)

## Tech Stack

- **Framework:** Flask 3.x
- **Database:** SQLAlchemy ORM with SQLite (dev) / PostgreSQL (prod)
- **Auth:** Flask-Login + Werkzeug password hashing
- **Templates:** Jinja2 (server-rendered HTML)
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

The app will be available at `http://localhost:5000`.

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

## Admin Setup

Admin-only pages (`/admin/users`, product management) are gated behind `is_admin` on the `User` model. Regular registration (`/register`) never sets this flag, and promoting a user to admin from the UI (`/admin/users`) itself requires being logged in as an admin — so on a fresh database with zero admins, you must bootstrap the first one from the command line.

**Bootstrap the first admin:**

```bash
flask create-admin <email>
```

You'll be prompted to enter (and confirm) a password. This command is idempotent and safe to re-run:
- If no user with that email exists, it creates one with `is_admin=True`.
- If a user with that email already exists, it promotes them to admin (password is left unchanged).

Example:
```bash
flask create-admin admin@example.com
```

Once the first admin exists, log in as that user and use **Manage Users** (`/admin/users`) to promote any other account — no further CLI use is needed.

> On Codio, run this command in the terminal after `pip install -r requirements.txt` and before (or after) starting the server, with the venv activated.

## Bulk Product Creation (Testing)

For seeding test data, admins can generate placeholder products in bulk instead of adding them one at a time:

1. Log in as an admin and go to **Add Product** (`/admin/products/new`).
2. Click **Bulk Add** to open the bulk-add modal.
3. Enter a count (1–100) and submit.

This creates that many `Bulk Product N` entries (`$9.99`, 99 stock, cycling through a set of placeholder images) via `POST /admin/products/bulk` (`app/routes/admin.py:84`). Useful for populating the catalog to test pagination, tag filtering, checkout/cart flows, or listing performance without hand-entering products.

## Running Tests

```bash
pytest -v
```

## Project Structure

```
app/
  __init__.py       # Application factory (create_app)
  models.py         # SQLAlchemy models: User, Product
  routes/
    auth.py         # /register, /login, /logout
    products.py     # JSON API: GET/POST/PUT/DELETE /products
    main.py         # HTML pages: /, /products/<id>
  templates/        # Jinja2 HTML templates
config.py           # Configuration from environment variables
run.py              # Entry point
tests/              # pytest test suite
```

---

## Security

This project was developed with security as a first-class concern. Below is an account of what was implemented and what was intentionally deferred.

### Implemented

**Password Hashing**
All passwords are hashed using Werkzeug's PBKDF2-SHA256 implementation before storage. Plaintext passwords are never persisted. A minimum password length of 8 characters is enforced at registration.

**CSRF Protection**
All HTML forms are protected against Cross-Site Request Forgery using `flask-wtf`. A CSRF token is generated per-session and validated on every state-changing POST request. Submitting a form without a valid token returns a `400` error.

**Input Sanitization**
- The product update endpoint uses a field whitelist (`ALLOWED_UPDATE_FIELDS`) to prevent mass assignment attacks — callers cannot overwrite internal fields like `id` or `created_at` by including them in the request body.
- The product creation endpoint validates that a name is present and that price is non-negative, returning a `400` for invalid input.
- Password length is validated before hashing to prevent empty or trivially short passwords.

**Error Handling**
Custom `404` and `500` error handlers prevent Flask from returning raw error pages that could expose internal route structure or stack traces. All errors render minimal HTML templates.

**Logging**
Security-relevant events are logged via Flask's built-in logger:
- Successful and failed login attempts (with the email used)
- New user registrations
- Product creation, update, and deletion

This creates an audit trail for detecting abuse or debugging incidents.

**Authentication & Authorization**
All product write operations (POST, PUT, DELETE) require an authenticated session via `@login_required`. Unauthenticated requests are redirected to the login page rather than receiving a 401, which is appropriate for a browser-facing app.

**Role-Based Access Control**
The `User` model has an `is_admin` field enforced via the `@admin_required` decorator (`app/decorators.py`), gating product management and the `/admin/users` panel to admins only. See [Admin Setup](#admin-setup) above for bootstrapping the first admin account.

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
