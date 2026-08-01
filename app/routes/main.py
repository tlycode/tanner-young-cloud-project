# app/routes/main.py

from flask import Blueprint, render_template, request
from flask_login import current_user

from app.models import Product, Tag, Review

main = Blueprint('main', __name__)

@main.route('/')
def index():
    tag_name = request.args.get('tag', '').strip().lower() or None
    query = Product.query
    if tag_name:
        query = query.join(Product.tags).filter(Tag.name == tag_name)
    all_products = query.all()
    all_tags = Tag.query.order_by(Tag.name).all()
    return render_template('index.html', products=all_products,
                           all_tags=all_tags, current_tag=tag_name)

@main.route('/products/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    product_reviews = product.reviews.order_by(Review.created_at.desc()).all()
    avg_rating = (sum(r.rating for r in product_reviews) / len(product_reviews)) if product_reviews else None
    user_review = None
    if current_user.is_authenticated:
        user_review = next((r for r in product_reviews if r.user_id == current_user.id), None)
    return render_template('product_detail.html', product=product, reviews=product_reviews,
                           avg_rating=avg_rating, user_review=user_review)
