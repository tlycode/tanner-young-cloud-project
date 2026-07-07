# app/routes/main.py

from flask import Blueprint, render_template, request

from app.models import Product, Tag

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
    return render_template('product_detail.html', product=product)
