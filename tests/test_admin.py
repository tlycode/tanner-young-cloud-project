# tests/test_admin.py

import pytest
from app.models import db, Product, User


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
