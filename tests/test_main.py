# tests/test_main.py

from app.models import db, Product


def test_index_empty(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'No products' in response.data


def test_index_with_product(client, app):
    with app.app_context():
        p = Product(name='Widget', price=9.99, stock=5)
        db.session.add(p)
        db.session.commit()
    response = client.get('/')
    assert response.status_code == 200
    assert b'Widget' in response.data


def test_product_detail(client, app):
    with app.app_context():
        p = Product(name='Gadget', price=19.99, stock=3)
        db.session.add(p)
        db.session.commit()
        product_id = p.id
    response = client.get(f'/products/{product_id}')
    assert response.status_code == 200
    assert b'Gadget' in response.data


def test_product_detail_not_found(client):
    response = client.get('/products/9999')
    assert response.status_code == 404
    assert b'404' in response.data


def test_404_returns_html(client):
    response = client.get('/nonexistent-page')
    assert response.status_code == 404
    assert b'404' in response.data
