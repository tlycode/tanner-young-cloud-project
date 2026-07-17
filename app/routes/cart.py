# app/routes/cart.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from app.models import db, Product

cart = Blueprint('cart', __name__, url_prefix='/cart')

SESSION_KEY = 'cart'


def _get_cart_dict():
    """Cart is stored in the session as {product_id (str): quantity (int)}."""
    return session.setdefault(SESSION_KEY, {})


def get_cart_count():
    return sum(_get_cart_dict().values())


def get_cart_items():
    """Resolve the session cart into a list of dicts with product + line total."""
    cart_dict = _get_cart_dict()
    items = []
    total = 0.0
    stale_ids = []
    for product_id, quantity in cart_dict.items():
        product = db.session.get(Product, int(product_id))
        if product is None:
            stale_ids.append(product_id)
            continue
        line_total = product.price * quantity
        total += line_total
        items.append({'product': product, 'quantity': quantity, 'line_total': line_total})
    if stale_ids:
        for product_id in stale_ids:
            cart_dict.pop(product_id, None)
        session.modified = True
    return items, total


@cart.route('/')
def view_cart():
    items, total = get_cart_items()
    return render_template('cart.html', items=items, total=total)


@cart.route('/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    quantity = request.form.get('quantity', 1, type=int) or 1
    quantity = max(1, quantity)

    cart_dict = _get_cart_dict()
    key = str(product_id)
    cart_dict[key] = cart_dict.get(key, 0) + quantity
    session.modified = True

    current_app.logger.info(f"Added to cart: product_id={product_id} quantity={quantity}")
    flash(f'Added "{product.name}" to your cart.', 'success')
    return redirect(request.referrer or url_for('main.index'))


@cart.route('/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    quantity = request.form.get('quantity', 1, type=int) or 0
    cart_dict = _get_cart_dict()
    key = str(product_id)

    if quantity <= 0:
        cart_dict.pop(key, None)
    else:
        cart_dict[key] = quantity
    session.modified = True

    return redirect(url_for('cart.view_cart'))


@cart.route('/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart_dict = _get_cart_dict()
    cart_dict.pop(str(product_id), None)
    session.modified = True
    return redirect(url_for('cart.view_cart'))


@cart.route('/checkout', methods=['GET'])
def checkout():
    items, total = get_cart_items()
    if not items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart.view_cart'))
    return render_template('checkout.html', items=items, total=total)


@cart.route('/checkout', methods=['POST'])
def place_order():
    items, total = get_cart_items()
    if not items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart.view_cart'))

    # Mocked payment processing - no real charge is made.
    order_number = f"MOCK-{abs(hash(frozenset(session.get(SESSION_KEY, {}).items()))) % 1000000:06d}"
    current_app.logger.info(f"Mock order placed: {order_number} total=${total:.2f}")

    session[SESSION_KEY] = {}
    session.modified = True

    return render_template('order_confirmation.html', order_number=order_number, total=total)
