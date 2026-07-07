# app/routes/products.py

from flask import Blueprint, request, jsonify, current_app
from app.decorators import admin_required
from app.models import db, Product
from app.tag_utils import parse_tag_names, get_or_create_tags

products = Blueprint('products', __name__)

ALLOWED_UPDATE_FIELDS = {'name', 'description', 'price', 'stock', 'image_url'}

@products.route('/products', methods=['GET'])
def get_products():
    all_products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'price': p.price,
        'stock': p.stock,
        'image_url': p.image_url,
        'tags': [t.name for t in p.tags]
    } for p in all_products])

@products.route('/products', methods=['POST'])
@admin_required
def create_product():
    data = request.get_json()
    if not data.get('name') or data.get('price', -1) < 0:
        return jsonify({'message': 'Invalid product data'}), 400
    product = Product(
        name=data['name'],
        description=data.get('description'),
        price=data['price'],
        stock=data.get('stock', 0),
        image_url=data.get('image_url')
    )
    product.tags = get_or_create_tags(parse_tag_names(data.get('tags')))
    db.session.add(product)
    db.session.commit()
    current_app.logger.info(f"Product created: {product.name}")
    return jsonify({'message': 'Product created'}), 201

@products.route('/products/<int:id>', methods=['PUT'])
@admin_required
def update_product(id):
    product = Product.query.get_or_404(id)
    data = request.get_json()
    for key, value in data.items():
        if key in ALLOWED_UPDATE_FIELDS:
            setattr(product, key, value)
    if 'tags' in data:
        product.tags = get_or_create_tags(parse_tag_names(data['tags']))
    db.session.commit()
    current_app.logger.info(f"Product updated: id={id}")
    return jsonify({'message': 'Product updated'})

@products.route('/products/<int:id>', methods=['DELETE'])
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    current_app.logger.info(f"Product deleted: id={id}")
    return jsonify({'message': 'Product deleted'})
