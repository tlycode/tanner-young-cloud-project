# tests/test_admin.py

import pytest
from app.models import db, Product, Tag, User


# --- Access control ---

def test_users_page_requires_admin(client):
    response = client.get('/admin/users')
    assert response.status_code == 403


def test_users_page_blocked_for_regular_user(regular_client):
    response = regular_client.get('/admin/users')
    assert response.status_code == 403


def test_users_page_accessible_to_admin(logged_in_client):
    response = logged_in_client.get('/admin/users')
    assert response.status_code == 200


def test_new_product_page_requires_admin(client):
    response = client.get('/admin/products/new')
    assert response.status_code == 403


def test_new_product_page_blocked_for_regular_user(regular_client):
    response = regular_client.get('/admin/products/new')
    assert response.status_code == 403


# --- Product CRUD via HTML forms ---

def test_admin_can_create_product(logged_in_client):
    response = logged_in_client.post('/admin/products/new', data={
        'name': 'Test Widget',
        'description': 'A test product',
        'price': '9.99',
        'stock': '5',
        'image_url': '',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Test Widget' in response.data


def test_create_product_invalid_price(logged_in_client):
    response = logged_in_client.post('/admin/products/new', data={
        'name': 'Bad Product',
        'price': '-1',
        'stock': '0',
    })
    assert response.status_code == 400


def test_create_product_missing_name(logged_in_client):
    response = logged_in_client.post('/admin/products/new', data={
        'name': '',
        'price': '5.00',
        'stock': '0',
    })
    assert response.status_code == 400


def test_bulk_create_products_requires_admin(client):
    response = client.post('/admin/products/bulk', data={'count': '3'})
    assert response.status_code == 403


def test_bulk_create_products_blocked_for_regular_user(regular_client):
    response = regular_client.post('/admin/products/bulk', data={'count': '3'})
    assert response.status_code == 403


def test_admin_can_bulk_create_products(logged_in_client, app):
    with app.app_context():
        before = Product.query.count()

    response = logged_in_client.post('/admin/products/bulk', data={'count': '3'},
                                     follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        assert Product.query.count() == before + 3
        products = Product.query.order_by(Product.id.desc()).limit(3).all()
        for p in products:
            assert p.image_url


def test_bulk_create_products_invalid_count(logged_in_client):
    response = logged_in_client.post('/admin/products/bulk', data={'count': '0'})
    assert response.status_code == 400


def test_bulk_create_products_count_too_large(logged_in_client):
    response = logged_in_client.post('/admin/products/bulk', data={'count': '9999'})
    assert response.status_code == 400


# --- Tags ---

def test_new_product_with_tags_creates_tags(logged_in_client, app):
    response = logged_in_client.post('/admin/products/new', data={
        'name': 'Tagged Widget',
        'price': '9.99',
        'stock': '5',
        'tags': 'electronics, sale',
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        product = Product.query.filter_by(name='Tagged Widget').first()
        assert sorted(t.name for t in product.tags) == ['electronics', 'sale']


def test_new_product_tag_reuse_does_not_duplicate(logged_in_client, app):
    logged_in_client.post('/admin/products/new', data={
        'name': 'First', 'price': '1.00', 'stock': '0', 'tags': 'sale',
    })
    logged_in_client.post('/admin/products/new', data={
        'name': 'Second', 'price': '1.00', 'stock': '0', 'tags': 'Sale',
    })

    with app.app_context():
        assert Tag.query.filter_by(name='sale').count() == 1


def test_new_product_empty_tags_field(logged_in_client, app):
    response = logged_in_client.post('/admin/products/new', data={
        'name': 'No Tags', 'price': '1.00', 'stock': '0', 'tags': '',
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        product = Product.query.filter_by(name='No Tags').first()
        assert product.tags == []


def test_new_product_duplicate_tags_in_input(logged_in_client, app):
    logged_in_client.post('/admin/products/new', data={
        'name': 'Dupe Tags', 'price': '1.00', 'stock': '0', 'tags': 'sale, sale, SALE',
    })

    with app.app_context():
        product = Product.query.filter_by(name='Dupe Tags').first()
        assert [t.name for t in product.tags] == ['sale']


def test_edit_product_updates_tags(logged_in_client, app):
    with app.app_context():
        p = Product(name='Editable', price=1.00, stock=1)
        p.tags = [Tag(name='old')]
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    logged_in_client.post(f'/admin/products/{product_id}/edit', data={
        'name': 'Editable', 'price': '1.00', 'stock': '1', 'tags': 'new',
    })

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert [t.name for t in product.tags] == ['new']


def test_edit_product_clears_tags(logged_in_client, app):
    with app.app_context():
        p = Product(name='Clearable', price=1.00, stock=1)
        p.tags = [Tag(name='keepme')]
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    logged_in_client.post(f'/admin/products/{product_id}/edit', data={
        'name': 'Clearable', 'price': '1.00', 'stock': '1', 'tags': '',
    })

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product.tags == []


def test_admin_can_edit_product(logged_in_client, app):
    with app.app_context():
        p = Product(name='Original', price=1.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    response = logged_in_client.post(f'/admin/products/{product_id}/edit', data={
        'name': 'Updated Name',
        'price': '2.50',
        'stock': '3',
        'image_url': '',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Updated Name' in response.data


def test_edit_nonexistent_product_returns_404(logged_in_client):
    response = logged_in_client.get('/admin/products/9999/edit')
    assert response.status_code == 404


def test_admin_can_delete_product(logged_in_client, app):
    with app.app_context():
        p = Product(name='To Delete', price=1.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    response = logged_in_client.post(f'/admin/products/{product_id}/delete',
                                     follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(Product, product_id) is None


def test_delete_nonexistent_product_returns_404(logged_in_client):
    response = logged_in_client.post('/admin/products/9999/delete')
    assert response.status_code == 404


# --- User promotion ---

def test_users_page_lists_users(logged_in_client, app):
    with app.app_context():
        u = User(email='other@example.com', password_hash='x', is_admin=False)
        db.session.add(u)
        db.session.commit()

    response = logged_in_client.get('/admin/users')
    assert b'other@example.com' in response.data


def test_admin_can_promote_user(logged_in_client, app):
    with app.app_context():
        u = User(email='promote@example.com', password_hash='x', is_admin=False)
        db.session.add(u)
        db.session.commit()
        user_id = u.id

    response = logged_in_client.post(f'/admin/users/{user_id}/promote',
                                     follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.is_admin is True


def test_promote_already_admin_is_safe(logged_in_client, app):
    with app.app_context():
        u = User(email='alreadyadmin@example.com', password_hash='x', is_admin=True)
        db.session.add(u)
        db.session.commit()
        user_id = u.id

    response = logged_in_client.post(f'/admin/users/{user_id}/promote',
                                     follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.is_admin is True


# --- JSON API admin restriction ---

def test_json_api_create_blocked_for_regular_user(regular_client):
    response = regular_client.post('/products', json={
        'name': 'Sneaky Product',
        'price': 1.00,
    })
    assert response.status_code == 403


def test_json_api_delete_blocked_for_regular_user(regular_client, app):
    with app.app_context():
        p = Product(name='Protected', price=5.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    response = regular_client.delete(f'/products/{product_id}')
    assert response.status_code == 403
