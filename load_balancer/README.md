# Load Balancer

Simulates a load balancer distributing traffic across two instances of the
ecommerce Flask app.

## How it works

- Two instances of the *same* app (`run.py`) are started on different ports
  (5000 and 5001), each using its own SQLite database file so they don't
  contend for the same file lock.
- [`load_balancer.py`](load_balancer.py) is a small Flask app that receives
  every request on port 8000 and forwards it to one of the two backends in
  round-robin order, then relays the backend's response back to the client.

## Running it

From the project root, in three separate terminals (after installing
`requirements.txt`, which now includes `requests`):

**Terminal 1 — backend instance 1 (port 5000):**

```bash
PORT=5000 DATABASE_URL=sqlite:///app1.db python run.py
```

**Terminal 2 — backend instance 2 (port 5001):**

```bash
PORT=5001 DATABASE_URL=sqlite:///app2.db python run.py
```

**Terminal 3 — the load balancer (port 8000):**

```bash
python load_balancer/load_balancer.py
```

Then visit **http://127.0.0.1:8000** — every request is forwarded to
`127.0.0.1:5000` or `127.0.0.1:5001` alternately. Watch the load balancer's
terminal output to see which backend handled each request.

## Configuration

- `LB_PORT` — port the load balancer listens on (default `8000`).
- `LB_TARGETS` — comma-separated list of backend URLs (default
  `http://127.0.0.1:5000,http://127.0.0.1:5001`).

```bash
LB_TARGETS="http://127.0.0.1:5000,http://127.0.0.1:5001,http://127.0.0.1:5002" \
  python load_balancer/load_balancer.py
```

## Notes

- Sessions (login, cart) are stored server-side via Flask's signed cookie
  session, but since each backend uses a separate SQLite database, a user
  routed to instance 1 on one request and instance 2 on the next may not see
  consistent data (e.g. their cart). This is expected for this simple
  round-robin simulation — a production setup would use a shared database
  and/or sticky sessions.
- The load balancer forwards headers, query params, form/JSON bodies, and
  cookies, and strips hop-by-hop headers (`Content-Length`,
  `Transfer-Encoding`, etc.) before relaying the response so Flask/Werkzeug
  can recompute them correctly.
