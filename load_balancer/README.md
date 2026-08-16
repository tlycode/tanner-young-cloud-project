# Load Balancer

Simulates a load balancer distributing traffic across multiple instances of
the ecommerce Flask app, with dynamic backend discovery to simulate
auto-scaling.

## How it works

- One or more instances of the *same* app (`run.py`) are started on
  different ports (e.g. 5000, 5001, ...), each using its own SQLite database
  file so they don't contend for the same file lock.
- [`load_balancer.py`](load_balancer.py) is a small Flask app that receives
  every request on port 8000 and forwards it to one of the live backends in
  round-robin order, then relays the backend's response back to the client.
- By default, the load balancer doesn't use a fixed target list. A
  background thread periodically scans a configurable range of localhost
  ports (`LB_PORT_RANGE_START`–`LB_PORT_RANGE_END`), health-checks each one
  with a `GET /`, and only load-balances across the ones that respond. This
  means you can start or stop backend instances at any port in the range
  while the load balancer is running, and it picks up the change on its own
  within one scan interval — simulating instances being added or removed by
  an auto-scaler.

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

## Simulating auto-scaling

With the load balancer already running, start another backend instance on
any port within the scan range (default 5000–5010):

```bash
PORT=5002 DATABASE_URL=sqlite:///app3.db python run.py
```

Within one health-check interval (default 5s), the load balancer's log will
show `Backend(s) up: ['http://127.0.0.1:5002']` and requests will start
rotating across all three instances. Stop that instance (Ctrl+C) and the log
will show `Backend(s) down: [...]` — it drops out of rotation automatically.

If every backend is stopped, the load balancer responds with `503 Service
Unavailable` instead of crashing.

## Configuration

- `LB_PORT` — port the load balancer listens on (default `8000`).
- `LB_PORT_RANGE_START` / `LB_PORT_RANGE_END` — inclusive range of localhost
  ports scanned for live backends (default `5000`–`5010`).
- `LB_HEALTH_INTERVAL` — seconds between health-check scans (default `5`).
- `LB_HEALTH_TIMEOUT` — per-backend health-check timeout in seconds (default `2`).
- `LB_TARGETS` — optional comma-separated list of backend URLs. If set, this
  overrides port-range scanning entirely and the load balancer round-robins
  over exactly this static list instead (no auto-discovery).

```bash
# Static target list (disables auto-scaling simulation)
LB_TARGETS="http://127.0.0.1:5000,http://127.0.0.1:5001,http://127.0.0.1:5002" \
  python load_balancer/load_balancer.py

# Wider port range, faster health checks
LB_PORT_RANGE_START=5000 LB_PORT_RANGE_END=5020 LB_HEALTH_INTERVAL=2 \
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
