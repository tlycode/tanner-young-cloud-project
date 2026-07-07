# app/routes/admin.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, current_app
from app.models import db, User, Product
from app.decorators import admin_required
from app.tag_utils import parse_tag_names, get_or_create_tags

admin = Blueprint('admin', __name__, url_prefix='/admin')

# Preset placeholder images used to fill in image_url for bulk-generated products.
BULK_PRODUCT_IMAGES = [
    'https://picsum.photos/seed/product1/400/400',
    'https://picsum.photos/seed/product2/400/400',
    'https://picsum.photos/seed/product3/400/400',
    'https://picsum.photos/seed/product4/400/400',
    'https://picsum.photos/seed/product5/400/400',
]

MAX_BULK_PRODUCTS = 100


@admin.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.id).all()
    return render_template('admin/users.html', users=all_users)


@admin.route('/users/<int:id>/promote', methods=['POST'])
@admin_required
def promote_user(id):
    user = db.session.get(User, id)
    if user is None:
        abort(404)
    user.is_admin = True
    db.session.commit()
    current_app.logger.info(f"User promoted to admin: {user.email}")
    flash(f'{user.email} is now an admin.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/products/new', methods=['GET', 'POST'])
@admin_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '')
        stock_str = request.form.get('stock', '0')
        image_url = request.form.get('image_url', '').strip() or None

        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            flash('Price must be a non-negative number.', 'error')
            return render_template('admin/product_form.html', product=None), 400

        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash('Stock must be a non-negative integer.', 'error')
            return render_template('admin/product_form.html', product=None), 400

        if not name:
            flash('Name is required.', 'error')
            return render_template('admin/product_form.html', product=None), 400

        product = Product(name=name, description=description or None,
                          price=price, stock=stock, image_url=image_url)
        product.tags = get_or_create_tags(parse_tag_names(request.form.get('tags', '')))
        db.session.add(product)
        db.session.commit()
        current_app.logger.info(f"Product created via admin: {product.name}")
        flash(f'"{product.name}" added.', 'success')
        return redirect(url_for('main.index'))

    return render_template('admin/product_form.html', product=None)


@admin.route('/products/bulk', methods=['POST'])
@admin_required
def bulk_create_products():
    count_str = request.form.get('count', '')
    try:
        count = int(count_str)
        if count < 1 or count > MAX_BULK_PRODUCTS:
            raise ValueError
    except ValueError:
        flash(f'Count must be a whole number between 1 and {MAX_BULK_PRODUCTS}.', 'error')
        return render_template('admin/product_form.html', product=None), 400

    existing = Product.query.count()
    for i in range(count):
        image_url = BULK_PRODUCT_IMAGES[(existing + i) % len(BULK_PRODUCT_IMAGES)]
        product = Product(name=f'Bulk Product {existing + i + 1}',
                          price=9.99, stock=0, image_url=image_url)
        db.session.add(product)
    db.session.commit()
    current_app.logger.info(f"Bulk created {count} products via admin")
    flash(f'{count} products added.', 'success')
    return redirect(url_for('main.index'))


@admin.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    product = db.session.get(Product, id)
    if product is None:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '')
        stock_str = request.form.get('stock', '0')
        image_url = request.form.get('image_url', '').strip() or None

        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            flash('Price must be a non-negative number.', 'error')
            return render_template('admin/product_form.html', product=product), 400

        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            flash('Stock must be a non-negative integer.', 'error')
            return render_template('admin/product_form.html', product=product), 400

        if not name:
            flash('Name is required.', 'error')
            return render_template('admin/product_form.html', product=product), 400

        product.name = name
        product.description = description or None
        product.price = price
        product.stock = stock
        product.image_url = image_url
        product.tags = get_or_create_tags(parse_tag_names(request.form.get('tags', '')))
        db.session.commit()
        current_app.logger.info(f"Product updated via admin: id={id}")
        flash(f'"{product.name}" updated.', 'success')
        return redirect(url_for('main.product_detail', id=product.id))

    return render_template('admin/product_form.html', product=product)


@admin.route('/products/<int:id>/delete', methods=['POST'])
@admin_required
def delete_product(id):
    product = db.session.get(Product, id)
    if product is None:
        abort(404)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    current_app.logger.info(f"Product deleted via admin: id={id}")
    flash(f'"{name}" deleted.', 'success')
    return redirect(url_for('main.index'))
