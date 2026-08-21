# app/routes/orders.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, session
from flask_login import login_required, current_user
from app.logger import get_logger
from app.models import db, Order, Complaint
from app.routes.cart import _get_cart_dict

orders = Blueprint('orders', __name__, url_prefix='/orders')

log = get_logger(__name__)


def _get_order_or_404(id):
    order = db.session.get(Order, id)
    if order is None:
        abort(404)
    return order


def _check_order_access(order):
    if order.user_id != current_user.id and not current_user.is_admin:
        log.warn('Blocked access to another user\'s order',
                 order_id=order.id, user_id=current_user.id,
                 owner_id=order.user_id)
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
        log.info('Buy again: items added to cart', order_id=order.id,
                 user_id=current_user.id, items=added)
        flash('Items from this order were added to your cart.', 'success')
    else:
        # Dead end - the shopper asked to reorder and got nothing.
        log.error('Buy again failed: no products from the order still exist',
                  order_id=order.id, user_id=current_user.id)
        flash('None of the products from this order are available anymore.', 'error')
    return redirect(url_for('cart.view_cart'))


@orders.route('/<int:id>/return', methods=['POST'])
@login_required
def return_order(id):
    order = _get_order_or_404(id)
    _check_order_access(order)

    if order.status == 'return_requested':
        log.notice('Duplicate return request', order_id=order.id,
                   user_id=current_user.id)
        flash('A return has already been requested for this order.', 'error')
    else:
        try:
            order.status = 'return_requested'
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception('Return request failed', order_id=order.id,
                          user_id=current_user.id)
            flash('Something went wrong submitting your return. Please try again.', 'error')
            return redirect(url_for('orders.order_detail', id=order.id))
        log.info('Return requested', order_id=order.id, user_id=current_user.id)
        flash('Your return request has been submitted.', 'success')
    return redirect(url_for('orders.order_detail', id=order.id))


@orders.route('/<int:id>/complaint', methods=['POST'])
@login_required
def submit_complaint(id):
    order = _get_order_or_404(id)
    _check_order_access(order)

    message = request.form.get('message', '').strip()
    if not message:
        log.info('Complaint rejected: empty message', order_id=order.id,
                 user_id=current_user.id)
        flash('Please describe your complaint before submitting.', 'error')
        return redirect(url_for('orders.order_detail', id=order.id))

    complaint = Complaint(order_id=order.id, user_id=order.user_id, message=message)
    try:
        db.session.add(complaint)
        db.session.commit()
    except Exception:
        # Losing a complaint means an unhappy shopper goes unheard.
        db.session.rollback()
        log.exception('Complaint submission failed', order_id=order.id,
                      user_id=order.user_id)
        flash('Something went wrong submitting your complaint. Please try again.', 'error')
        return redirect(url_for('orders.order_detail', id=order.id))

    # A complaint is a signal worth seeing without turning on INFO.
    log.notice('Complaint submitted', complaint_id=complaint.id,
               order_id=order.id, user_id=order.user_id)
    flash('Your complaint has been submitted.', 'success')
    return redirect(url_for('orders.order_detail', id=order.id))
