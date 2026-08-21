# app/routes/admin.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import current_user
from app.logger import get_logger
from app.models import db, User, Product, Order, Complaint
from app.decorators import admin_required
from app.tag_utils import parse_tag_names, get_or_create_tags

admin = Blueprint('admin', __name__, url_prefix='/admin')

log = get_logger(__name__)

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
    try:
        user.is_admin = True
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Admin promotion failed', target_user_id=id,
                      admin_id=current_user.id)
        flash('Something went wrong promoting that user. Please try again.', 'error')
        return redirect(url_for('admin.users'))
    # Privilege escalation - always visible at the default level.
    log.notice('User promoted to admin', target_user_id=user.id,
               email=user.email, admin_id=current_user.id)
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
            log.info('Product creation rejected: invalid price',
                     price=price_str, admin_id=current_user.id)
            flash('Price must be a non-negative number.', 'error')
            return render_template('admin/product_form.html', product=None), 400

        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            log.info('Product creation rejected: invalid stock',
                     stock=stock_str, admin_id=current_user.id)
            flash('Stock must be a non-negative integer.', 'error')
            return render_template('admin/product_form.html', product=None), 400

        if not name:
            log.info('Product creation rejected: missing name',
                     admin_id=current_user.id)
            flash('Name is required.', 'error')
            return render_template('admin/product_form.html', product=None), 400

        product = Product(name=name, description=description or None,
                          price=price, stock=stock, image_url=image_url)
        product.tags = get_or_create_tags(parse_tag_names(request.form.get('tags', '')))
        try:
            db.session.add(product)
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception('Product creation failed via admin', name=name,
                          admin_id=current_user.id)
            flash('Something went wrong adding that product. Please try again.', 'error')
            return render_template('admin/product_form.html', product=None), 500
        log.info('Product created via admin', product_id=product.id,
                 name=product.name, price=product.price, stock=product.stock,
                 admin_id=current_user.id)
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
        log.info('Bulk product creation rejected: invalid count',
                 count=count_str, admin_id=current_user.id)
        flash(f'Count must be a whole number between 1 and {MAX_BULK_PRODUCTS}.', 'error')
        return render_template('admin/product_form.html', product=None), 400

    existing = Product.query.count()
    for i in range(count):
        image_url = BULK_PRODUCT_IMAGES[(existing + i) % len(BULK_PRODUCT_IMAGES)]
        product = Product(name=f'Bulk Product {existing + i + 1}',
                          price=9.99, stock=99, image_url=image_url)
        db.session.add(product)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Bulk product creation failed', count=count,
                      admin_id=current_user.id)
        flash('Something went wrong adding those products. Please try again.', 'error')
        return render_template('admin/product_form.html', product=None), 500
    log.info('Bulk created products via admin', count=count,
             admin_id=current_user.id)
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
            log.info('Product update rejected: invalid price', product_id=id,
                     price=price_str, admin_id=current_user.id)
            flash('Price must be a non-negative number.', 'error')
            return render_template('admin/product_form.html', product=product), 400

        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            log.info('Product update rejected: invalid stock', product_id=id,
                     stock=stock_str, admin_id=current_user.id)
            flash('Stock must be a non-negative integer.', 'error')
            return render_template('admin/product_form.html', product=product), 400

        if not name:
            log.info('Product update rejected: missing name', product_id=id,
                     admin_id=current_user.id)
            flash('Name is required.', 'error')
            return render_template('admin/product_form.html', product=product), 400

        product.name = name
        product.description = description or None
        product.price = price
        product.stock = stock
        product.image_url = image_url
        product.tags = get_or_create_tags(parse_tag_names(request.form.get('tags', '')))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception('Product update failed via admin', product_id=id,
                          admin_id=current_user.id)
            flash('Something went wrong updating that product. Please try again.', 'error')
            return render_template('admin/product_form.html', product=product), 500
        log.info('Product updated via admin', product_id=id, name=product.name,
                 price=product.price, stock=product.stock,
                 admin_id=current_user.id)
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
    try:
        db.session.delete(product)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Product deletion failed via admin', product_id=id,
                      name=name, admin_id=current_user.id)
        flash('Something went wrong deleting that product. Please try again.', 'error')
        return redirect(url_for('main.index'))
    # Destructive and hard to reconstruct after the fact.
    log.notice('Product deleted via admin', product_id=id, name=name,
               admin_id=current_user.id)
    flash(f'"{name}" deleted.', 'success')
    return redirect(url_for('main.index'))


@admin.route('/orders/lookup', methods=['GET'])
@admin_required
def order_lookup():
    order_id = request.args.get('order_id', type=int)
    if order_id is None:
        log.info('Order lookup rejected: non-numeric order id',
                 value=request.args.get('order_id'), admin_id=current_user.id)
        flash('Please enter a numeric order ID.', 'error')
        return redirect(url_for('admin.users'))
    return redirect(url_for('admin.order_detail', id=order_id))


@admin.route('/orders/<int:id>')
@admin_required
def order_detail(id):
    order = db.session.get(Order, id)
    if order is None:
        abort(404)
    return render_template('order_detail.html', order=order)


@admin.route('/complaints')
@admin_required
def complaints():
    all_complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template('admin/complaints.html', complaints=all_complaints)
