# tests/test_main.py

from app.models import db, Product, Tag


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


def test_index_shows_tag_badges(client, app):
    with app.app_context():
        p = Product(name='Widget', price=9.99, stock=5)
        p.tags = [Tag(name='electronics')]
        db.session.add(p)
        db.session.commit()
    response = client.get('/')
    assert response.status_code == 200
    assert b'electronics' in response.data
    assert b'tag=electronics' in response.data


def test_index_filter_by_tag(client, app):
    with app.app_context():
        sale = Product(name='On Sale', price=9.99, stock=5)
        sale.tags = [Tag(name='sale')]
        other = Product(name='Regular', price=9.99, stock=5)
        db.session.add_all([sale, other])
        db.session.commit()
    response = client.get('/?tag=sale')
    assert response.status_code == 200
    assert b'On Sale' in response.data
    assert b'Regular' not in response.data


def test_index_filter_by_tag_case_insensitive(client, app):
    with app.app_context():
        p = Product(name='On Sale', price=9.99, stock=5)
        p.tags = [Tag(name='sale')]
        db.session.add(p)
        db.session.commit()
    response = client.get('/?tag=Sale')
    assert response.status_code == 200
    assert b'On Sale' in response.data


def test_index_filter_unknown_tag_returns_empty(client, app):
    response = client.get('/?tag=doesnotexist')
    assert response.status_code == 200
    assert b'No products' in response.data


def test_index_all_tags_link_present(client, app):
    with app.app_context():
        p = Product(name='On Sale', price=9.99, stock=5)
        p.tags = [Tag(name='sale')]
        db.session.add(p)
        db.session.commit()
    response = client.get('/?tag=sale')
    assert response.status_code == 200
    assert b'All' in response.data


def test_product_detail_shows_tags(client, app):
    with app.app_context():
        p = Product(name='Gadget', price=19.99, stock=3)
        p.tags = [Tag(name='electronics')]
        db.session.add(p)
        db.session.commit()
        product_id = p.id
    response = client.get(f'/products/{product_id}')
    assert response.status_code == 200
    assert b'electronics' in response.data
