# app/routes/main.py

from flask import Blueprint, render_template

from app.models import Product

main = Blueprint('main', __name__)

@main.route('/')
def index():
    all_products = Product.query.all()
    return render_template('index.html', products=all_products)

@main.route('/products/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('product_detail.html', product=product)
