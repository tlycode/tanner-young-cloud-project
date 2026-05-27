# tests/test_products.py

from app.models import db, Product


def test_get_products_empty(client):
    response = client.get('/products')
    assert response.status_code == 200
    assert response.get_json() == []


def test_get_products_with_data(client, app):
    with app.app_context():
        p = Product(name='Widget', price=9.99, stock=5)
        db.session.add(p)
        db.session.commit()
    response = client.get('/products')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['name'] == 'Widget'


def test_create_product_authenticated(logged_in_client):
    response = logged_in_client.post('/products', json={
        'name': 'New Item',
        'description': 'A thing',
        'price': 4.99,
        'stock': 10
    })
    assert response.status_code == 201


def test_create_product_unauthenticated(client):
    response = client.post('/products', json={
        'name': 'New Item',
        'description': 'A thing',
        'price': 4.99,
        'stock': 10
    })
    assert response.status_code == 403


def test_create_product_invalid_price(logged_in_client):
    response = logged_in_client.post('/products', json={
        'name': 'Bad Item',
        'price': -5
    })
    assert response.status_code == 400


def test_update_product(logged_in_client, app):
    with app.app_context():
        p = Product(name='Old Name', price=5.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id
    response = logged_in_client.put(f'/products/{product_id}', json={'name': 'New Name'})
    assert response.status_code == 200


def test_update_product_disallows_id_change(logged_in_client, app):
    with app.app_context():
        p = Product(name='Widget', price=5.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id
    logged_in_client.put(f'/products/{product_id}', json={'id': 999})
    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product is not None
        assert product.id == product_id


def test_delete_product(logged_in_client, app):
    with app.app_context():
        p = Product(name='To Delete', price=1.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id
    response = logged_in_client.delete(f'/products/{product_id}')
    assert response.status_code == 200
