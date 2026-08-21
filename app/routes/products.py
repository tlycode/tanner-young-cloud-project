# app/routes/products.py

from flask import Blueprint, request, jsonify
from app.decorators import admin_required
from app.logger import get_logger
from app.models import db, Product
from app.tag_utils import parse_tag_names, get_or_create_tags

products = Blueprint('products', __name__)

log = get_logger(__name__)

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
        log.info('Product creation rejected: invalid data',
                 name=data.get('name'), price=data.get('price'))
        return jsonify({'message': 'Invalid product data'}), 400
    product = Product(
        name=data['name'],
        description=data.get('description'),
        price=data['price'],
        stock=data.get('stock', 0),
        image_url=data.get('image_url')
    )
    product.tags = get_or_create_tags(parse_tag_names(data.get('tags')))
    try:
        db.session.add(product)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Product creation failed', name=data.get('name'))
        return jsonify({'message': 'Could not create product'}), 500
    log.info('Product created', product_id=product.id, name=product.name,
             price=product.price, stock=product.stock)
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
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Product update failed', product_id=id)
        return jsonify({'message': 'Could not update product'}), 500
    changed = sorted(set(data) & ALLOWED_UPDATE_FIELDS)
    log.info('Product updated', product_id=id, name=product.name,
             fields=','.join(changed) or 'none')
    return jsonify({'message': 'Product updated'})

@products.route('/products/<int:id>', methods=['DELETE'])
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    name = product.name
    try:
        db.session.delete(product)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Product deletion failed', product_id=id, name=name)
        return jsonify({'message': 'Could not delete product'}), 500
    # Deletions are destructive and hard to reconstruct after the fact.
    log.notice('Product deleted', product_id=id, name=name)
    return jsonify({'message': 'Product deleted'})
