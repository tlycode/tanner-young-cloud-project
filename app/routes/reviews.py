# app/routes/reviews.py

from flask import Blueprint, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.logger import get_logger
from app.models import db, Product, Review

reviews = Blueprint('reviews', __name__)

log = get_logger(__name__)

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
        log.info('Review rejected: invalid rating', product_id=product.id,
                 user_id=current_user.id, rating=request.form.get('rating'))
        flash('Please choose a star rating between 1 and 5.', 'error')
        return redirect(url_for('main.product_detail', id=product.id))

    body = request.form.get('body', '').strip() or None

    review = Review(product_id=product.id, user_id=current_user.id, rating=rating, body=body)
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError:
        # Expected: the one-review-per-product constraint doing its job.
        db.session.rollback()
        log.notice('Review rejected: duplicate', product_id=product.id,
                   user_id=current_user.id)
        flash("You've already reviewed this product.", 'error')
        return redirect(url_for('main.product_detail', id=product.id))
    except Exception:
        db.session.rollback()
        log.exception('Review creation failed', product_id=product.id,
                      user_id=current_user.id)
        flash('Something went wrong saving your review. Please try again.', 'error')
        return redirect(url_for('main.product_detail', id=product.id))

    log.info('Review created', review_id=review.id, product_id=product.id,
             user_id=current_user.id, rating=rating)
    flash('Thanks for your review!', 'success')
    return redirect(url_for('main.product_detail', id=product.id))


@reviews.route('/reviews/<int:id>/edit', methods=['POST'])
@login_required
def edit_review(id):
    review = Review.query.get_or_404(id)
    if review.user_id != current_user.id and not current_user.is_admin:
        log.warn("Blocked edit of another user's review", review_id=id,
                 user_id=current_user.id, owner_id=review.user_id)
        abort(403)

    rating = _parse_rating(request.form.get('rating'))
    if rating is None:
        log.info('Review update rejected: invalid rating', review_id=id,
                 user_id=current_user.id, rating=request.form.get('rating'))
        flash('Please choose a star rating between 1 and 5.', 'error')
        return redirect(url_for('main.product_detail', id=review.product_id))

    review.rating = rating
    review.body = request.form.get('body', '').strip() or None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Review update failed', review_id=id,
                      user_id=current_user.id)
        flash('Something went wrong updating your review. Please try again.', 'error')
        return redirect(url_for('main.product_detail', id=review.product_id))

    log.info('Review updated', review_id=id, user_id=current_user.id,
             rating=rating)
    flash('Review updated.', 'success')
    return redirect(url_for('main.product_detail', id=review.product_id))


@reviews.route('/reviews/<int:id>/delete', methods=['POST'])
@login_required
def delete_review(id):
    review = Review.query.get_or_404(id)
    if review.user_id != current_user.id and not current_user.is_admin:
        log.warn("Blocked deletion of another user's review", review_id=id,
                 user_id=current_user.id, owner_id=review.user_id)
        abort(403)

    product_id = review.product_id
    try:
        db.session.delete(review)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Review deletion failed', review_id=id,
                      user_id=current_user.id)
        flash('Something went wrong deleting your review. Please try again.', 'error')
        return redirect(url_for('main.product_detail', id=product_id))

    log.notice('Review deleted', review_id=id, product_id=product_id,
               user_id=current_user.id)
    flash('Review deleted.', 'success')
    return redirect(url_for('main.product_detail', id=product_id))
