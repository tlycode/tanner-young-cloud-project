"""Simple round-robin load balancer for the ecommerce Flask app.

Distributes incoming requests across multiple backend instances of the
app (started on different ports, e.g. via `PORT=5000 python run.py` and
`PORT=5001 python run.py`).
"""
import itertools
import logging
import os

import requests
from flask import Flask, Response, request

load_balancer = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("load_balancer")

TARGETS = os.environ.get(
    "LB_TARGETS", "http://127.0.0.1:5000,http://127.0.0.1:5001"
).split(",")

_targets_cycle = itertools.cycle(TARGETS)

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


def next_target():
    return next(_targets_cycle)


@load_balancer.route(
    "/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
@load_balancer.route(
    "/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
def balance(path):
    target = next_target()
    url = f"{target}/{path}"

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            params=request.args,
            data=request.get_data(),
            headers={
                key: value
                for key, value in request.headers
                if key.lower() != "host"
            },
            cookies=request.cookies,
            allow_redirects=False,
            timeout=10,
        )
    except requests.exceptions.RequestException:
        logger.exception("Backend %s failed", target)
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
    logger.info("Load balancer starting on port %s, targets=%s", port, TARGETS)
    load_balancer.run(host="0.0.0.0", port=port)
