"""Capture the documentation screenshots in docs/screenshots/.

Run against a live instance seeded with demo data:

    DATABASE_URL=sqlite:///demo.db PORT=5055 python run.py &
    python scripts/capture_screenshots.py

Requires playwright (a documentation-time tool, not an app dependency):

    pip install playwright && python -m playwright install chromium
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SHOT_BASE_URL", "http://127.0.0.1:5055")
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

SHOPPER = ("shopper@example.com", "shopper123")
ADMIN = ("admin@example.com", "adminpass123")

DESKTOP = {"width": 1280, "height": 900}
MOBILE = {"width": 390, "height": 844}

# (filename, path, login-as, viewport, full_page)
SHOTS = [
    ("01-home-catalog.png",      "/",                    None,    DESKTOP, False),
    ("02-product-detail.png",    "/products/1",          SHOPPER, DESKTOP, True),
    ("03-cart.png",              "/cart/",               SHOPPER, DESKTOP, False),
    ("04-checkout.png",          "/cart/checkout",       SHOPPER, DESKTOP, False),
    ("05-order-confirmation.png","/orders/1",            SHOPPER, DESKTOP, False),
    ("06-order-history.png",     "/orders/",             SHOPPER, DESKTOP, False),
    ("07-admin-users.png",       "/admin/users",         ADMIN,   DESKTOP, False),
    ("08-admin-new-product.png", "/admin/products/new",  ADMIN,   DESKTOP, False),
    ("09-login-error.png",       "__login_error__",      None,    DESKTOP, False),
    ("10-mobile-catalog.png",    "/",                    None,    MOBILE,  False),
    ("11-mobile-cart.png",       "/cart/",               SHOPPER, MOBILE,  False),
    ("12-mobile-admin-users.png","/admin/users",         ADMIN,   MOBILE,  False),
]


def login(page, creds):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type=email]", creds[0])
    page.fill("input[type=password]", creds[1])
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def add_cart_items(page):
    """Put a couple of items in the session cart so cart/checkout aren't empty."""
    for product_id, qty in ((1, 1), (5, 2)):
        page.goto(f"{BASE}/products/{product_id}", wait_until="networkidle")
        qty_input = page.query_selector("input[name=quantity]")
        if qty_input:
            qty_input.fill(str(qty))
        page.click("form[action*='/cart/add'] button[type=submit]")
        page.wait_for_load_state("networkidle")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, path, creds, viewport, full_page in SHOTS:
            ctx = browser.new_context(viewport=viewport, device_scale_factor=2)
            page = ctx.new_page()
            if creds:
                login(page, creds)
                if path in ("/cart/", "/cart/checkout"):
                    add_cart_items(page)

            if path == "__login_error__":
                page.goto(f"{BASE}/login", wait_until="networkidle")
                page.fill("input[type=email]", "shopper@example.com")
                page.fill("input[type=password]", "wrongpassword")
                page.click("button[type=submit]")
                page.wait_for_load_state("networkidle")
            else:
                page.goto(f"{BASE}{path}", wait_until="networkidle")

            page.wait_for_timeout(700)  # let remote product images settle
            page.screenshot(path=str(OUT / name), full_page=full_page)
            print(f"  captured {name}")
            ctx.close()
        browser.close()
    print(f"\nWrote {len(SHOTS)} screenshots to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
