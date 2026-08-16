"""Simple load balancer for the ecommerce Flask app.

Distributes incoming requests across multiple backend instances of the app.
By default it simulates auto-scaling: a background thread periodically scans
a range of localhost ports, health-checks each one, and load-balances only
across the instances that are currently alive. Start a new backend on any
port within the range and it's picked up automatically within one scan
interval; stop one and it drops out of rotation.
"""
import itertools
import logging
import os
import threading
import time

import requests
from flask import Flask, Response, request

load_balancer = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("load_balancer")

STATIC_TARGETS = [
    t.strip() for t in os.environ.get("LB_TARGETS", "").split(",") if t.strip()
]
PORT_RANGE_START = int(os.environ.get("LB_PORT_RANGE_START", 5000))
PORT_RANGE_END = int(os.environ.get("LB_PORT_RANGE_END", 5010))
HEALTH_INTERVAL = float(os.environ.get("LB_HEALTH_INTERVAL", 5))
HEALTH_TIMEOUT = float(os.environ.get("LB_HEALTH_TIMEOUT", 2))

# Headers that must not be forwarded verbatim between hops.
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-encoding",
    "content-length",
}

_targets_lock = threading.Lock()
_healthy_targets = list(STATIC_TARGETS)
_rr_counter = itertools.count()


def is_healthy(url):
    try:
        resp = requests.get(url + "/", timeout=HEALTH_TIMEOUT)
        return resp.status_code < 500
    except requests.exceptions.RequestException:
        return False


def scan_targets():
    """Probe every port in the configured range and return the live ones."""
    candidates = [
        f"http://127.0.0.1:{port}"
        for port in range(PORT_RANGE_START, PORT_RANGE_END + 1)
    ]
    return [url for url in candidates if is_healthy(url)]


def health_check_loop():
    global _healthy_targets
    while True:
        discovered = set(scan_targets())
        with _targets_lock:
            previous = set(_healthy_targets)
            if discovered != previous:
                added = discovered - previous
                removed = previous - discovered
                if added:
                    logger.info("Backend(s) up: %s", sorted(added))
                if removed:
                    logger.info("Backend(s) down: %s", sorted(removed))
                _healthy_targets = sorted(discovered)
        time.sleep(HEALTH_INTERVAL)


def get_targets():
    with _targets_lock:
        return list(_healthy_targets)


def next_target(targets):
    i = next(_rr_counter) % len(targets)
    return targets[i]


def forward(target, path):
    url = f"{target}/{path}"
    resp = requests.request(
        method=request.method,
        url=url,
        params=request.args,
        data=request.get_data(),
        headers={
            key: value for key, value in request.headers if key.lower() != "host"
        },
        cookies=request.cookies,
        allow_redirects=False,
        timeout=10,
    )
    return resp


@load_balancer.route(
    "/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
@load_balancer.route(
    "/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
def balance(path):
    targets = get_targets()
    if not targets:
        logger.error("No healthy backends available")
        return Response("Service Unavailable: no healthy backends", status=503)

    target = next_target(targets)
    try:
        resp = forward(target, path)
    except requests.exceptions.RequestException:
        logger.warning("Backend %s failed, retrying with next target", target)
        remaining = [t for t in targets if t != target]
        if not remaining:
            return Response("Bad Gateway: backend unavailable", status=502)
        target = next_target(remaining)
        try:
            resp = forward(target, path)
        except requests.exceptions.RequestException:
            logger.exception("Backend %s also failed", target)
            return Response("Bad Gateway: backend unavailable", status=502)

    logger.info("%s %s -> %s [%s]", request.method, request.path, target, resp.status_code)

    response_headers = [
        (name, value)
        for name, value in resp.raw.headers.items()
        if name.lower() not in HOP_BY_HOP_HEADERS
    ]
    return Response(resp.content, status=resp.status_code, headers=response_headers)


if __name__ == "__main__":
    port = int(os.environ.get("LB_PORT", 8000))

    if STATIC_TARGETS:
        logger.info("Using static targets (LB_TARGETS set): %s", STATIC_TARGETS)
    else:
        logger.info(
            "Scanning ports %s-%s for live backends (initial scan)...",
            PORT_RANGE_START,
            PORT_RANGE_END,
        )
        _healthy_targets = scan_targets()
        logger.info("Discovered backends: %s", _healthy_targets)
        threading.Thread(target=health_check_loop, daemon=True).start()

    logger.info("Load balancer starting on port %s", port)
    load_balancer.run(host="0.0.0.0", port=port)
