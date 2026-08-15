# app/routes/orders.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, current_app, session
from flask_login import login_required, current_user
from app.models import db, Order, Complaint
from app.routes.cart import _get_cart_dict

orders = Blueprint('orders', __name__, url_prefix='/orders')


def _get_order_or_404(id):
    order = db.session.get(Order, id)
    if order is None:
        abort(404)
    return order


def _check_order_access(order):
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)


@orders.route('/')
@login_required
def my_orders():
    order_list = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=order_list)


@orders.route('/<int:id>')
@login_required
def order_detail(id):
    order = _get_order_or_404(id)
    _check_order_access(order)
    return render_template('order_detail.html', order=order)


@orders.route('/<int:id>/buy-again', methods=['POST'])
@login_required
def buy_again(id):
    order = _get_order_or_404(id)
    _check_order_access(order)

    cart_dict = _get_cart_dict()
    added = 0
    for item in order.items:
        if item.product_id is None:
            continue
        key = str(item.product_id)
        cart_dict[key] = cart_dict.get(key, 0) + item.quantity
        added += 1
    session.modified = True

    if added:
        flash('Items from this order were added to your cart.', 'success')
    else:
        flash('None of the products from this order are available anymore.', 'error')
    return redirect(url_for('cart.view_cart'))


@orders.route('/<int:id>/return', methods=['POST'])
@login_required
def return_order(id):
    order = _get_order_or_404(id)
    _check_order_access(order)

    if order.status == 'return_requested':
        flash('A return has already been requested for this order.', 'error')
    else:
        order.status = 'return_requested'
        db.session.commit()
        current_app.logger.info(f"Return requested: order_id={order.id}")
        flash('Your return request has been submitted.', 'success')
    return redirect(url_for('orders.order_detail', id=order.id))


@orders.route('/<int:id>/complaint', methods=['POST'])
@login_required
def submit_complaint(id):
    order = _get_order_or_404(id)
    _check_order_access(order)

    message = request.form.get('message', '').strip()
    if not message:
        flash('Please describe your complaint before submitting.', 'error')
        return redirect(url_for('orders.order_detail', id=order.id))

    complaint = Complaint(order_id=order.id, user_id=order.user_id, message=message)
    db.session.add(complaint)
    db.session.commit()

    current_app.logger.info(f"Complaint submitted: order_id={order.id} user_id={order.user_id}")
    flash('Your complaint has been submitted.', 'success')
    return redirect(url_for('orders.order_detail', id=order.id))
