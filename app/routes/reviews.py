# app/routes/reviews.py

from flask import Blueprint, redirect, url_for, request, flash, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.models import db, Product, Review

reviews = Blueprint('reviews', __name__)

MIN_RATING = 1
MAX_RATING = 5


def _parse_rating(raw):
    try:
        rating = int(raw)
    except (TypeError, ValueError):
        return None
    if rating < MIN_RATING or rating > MAX_RATING:
        return None
    return rating


@reviews.route('/products/<int:product_id>/reviews', methods=['POST'])
@login_required
def create_review(product_id):
    product = Product.query.get_or_404(product_id)

    rating = _parse_rating(request.form.get('rating'))
    if rating is None:
        flash('Please choose a star rating between 1 and 5.', 'error')
        return redirect(url_for('main.product_detail', id=product.id))

    body = request.form.get('body', '').strip() or None

    review = Review(product_id=product.id, user_id=current_user.id, rating=rating, body=body)
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("You've already reviewed this product.", 'error')
        return redirect(url_for('main.product_detail', id=product.id))

    current_app.logger.info(f"Review created: product_id={product.id} user_id={current_user.id}")
    flash('Thanks for your review!', 'success')
    return redirect(url_for('main.product_detail', id=product.id))


@reviews.route('/reviews/<int:id>/edit', methods=['POST'])
@login_required
def edit_review(id):
    review = Review.query.get_or_404(id)
    if review.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    rating = _parse_rating(request.form.get('rating'))
    if rating is None:
        flash('Please choose a star rating between 1 and 5.', 'error')
        return redirect(url_for('main.product_detail', id=review.product_id))

    review.rating = rating
    review.body = request.form.get('body', '').strip() or None
    db.session.commit()

    current_app.logger.info(f"Review updated: id={id}")
    flash('Review updated.', 'success')
    return redirect(url_for('main.product_detail', id=review.product_id))


@reviews.route('/reviews/<int:id>/delete', methods=['POST'])
@login_required
def delete_review(id):
    review = Review.query.get_or_404(id)
    if review.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()

    current_app.logger.info(f"Review deleted: id={id}")
    flash('Review deleted.', 'success')
    return redirect(url_for('main.product_detail', id=product_id))
