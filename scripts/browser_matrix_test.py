"""Cross-browser / cross-viewport smoke test used for the final-submission report.

Drives a real purchase flow in Chromium, Firefox and WebKit (Safari's engine),
and checks every documented page for horizontal overflow at phone, tablet and
desktop widths.

    DATABASE_URL=sqlite:///demo.db PORT=5055 python run.py &
    python scripts/browser_matrix_test.py

Requires playwright (a testing-time tool, not an app dependency):

    pip install playwright && python -m playwright install
"""

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("SHOT_BASE_URL", "http://127.0.0.1:5055")
SHOPPER = ("shopper@example.com", "shopper123")

PAGES = ["/", "/products/1", "/cart/", "/orders/", "/login", "/register",
         "/cart/checkout", "/forgot-password", "/admin/users"]
WIDTHS = [(390, "phone"), (768, "tablet"), (1280, "desktop")]

results = []
failures = []


def check(label, condition, detail=""):
    results.append((label, bool(condition), detail))
    if not condition:
        failures.append(f"{label} — {detail}")


def purchase_flow(page, engine):
    # Login
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type=email]", SHOPPER[0])
    page.fill("input[type=password]", SHOPPER[1])
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    check(f"[{engine}] login succeeds", "Logged in successfully" in page.content())

    # Invalid login shows an error
    page.goto(f"{BASE}/logout", wait_until="networkidle")
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type=email]", SHOPPER[0])
    page.fill("input[type=password]", "wrongpassword")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    check(f"[{engine}] invalid login shows error",
          "Invalid email or password" in page.content())

    # Log back in and add to cart
    page.fill("input[type=email]", SHOPPER[0])
    page.fill("input[type=password]", SHOPPER[1])
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")

    page.goto(f"{BASE}/products/1", wait_until="networkidle")
    page.click("form[action*='/cart/add'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE}/cart/", wait_until="networkidle")
    check(f"[{engine}] item appears in cart", "Aurora Wireless Headphones" in page.content())

    # Checkout requires a complete address (HTML5 validation blocks empty submit)
    page.goto(f"{BASE}/cart/checkout", wait_until="networkidle")
    empty_valid = page.eval_on_selector("form[action*='checkout']", "f => f.checkValidity()")
    check(f"[{engine}] empty checkout form is rejected", empty_valid is False)

    for field, value in (("full_name", "Tanner Young"), ("address", "1600 Shattuck Ave"),
                         ("city", "Berkeley"), ("zip", "94709"),
                         ("card_number", "4242 4242 4242 4242"),
                         ("card_expiry", "12/28"), ("card_cvc", "123")):
        page.fill(f"[name={field}]", value)
    page.click("form[action*='checkout'] button[type=submit]")
    page.wait_for_load_state("networkidle")
    check(f"[{engine}] order is placed", "Thank you for your order" in page.content())

    # A shopper cannot open another account's order
    resp = page.goto(f"{BASE}/orders/3", wait_until="networkidle")
    check(f"[{engine}] other user's order returns 403", resp.status == 403,
          f"got {resp.status}")


def overflow_check(page, engine, width, label):
    for path in PAGES:
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        scroll_w = page.evaluate("document.documentElement.scrollWidth")
        check(f"[{engine}] {label} ({width}px) no overflow on {path}",
              scroll_w <= width + 1, f"scrollWidth={scroll_w}")


def main():
    with sync_playwright() as pw:
        for engine_name in ("chromium", "firefox", "webkit"):
            browser = getattr(pw, engine_name).launch()
            ctx = browser.new_context(viewport={"width": 1280, "height": 900})
            page = ctx.new_page()
            purchase_flow(page, engine_name)
            ctx.close()

            # Responsive sweep, logged in so admin/cart pages render fully
            for width, label in WIDTHS:
                ctx = browser.new_context(viewport={"width": width, "height": 900})
                page = ctx.new_page()
                page.goto(f"{BASE}/login", wait_until="networkidle")
                page.fill("input[type=email]", SHOPPER[0])
                page.fill("input[type=password]", SHOPPER[1])
                page.click("button[type=submit]")
                page.wait_for_load_state("networkidle")
                overflow_check(page, engine_name, width, label)
                ctx.close()
            browser.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    for label, ok, detail in results:
        if not ok:
            print(f"  FAIL {label} — {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
