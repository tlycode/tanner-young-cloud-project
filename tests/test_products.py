# tests/test_products.py

from app.models import db, Product, Tag


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


def test_get_products_includes_tags(client, app):
    with app.app_context():
        p = Product(name='Tagged', price=9.99, stock=5)
        p.tags = [Tag(name='electronics'), Tag(name='sale')]
        db.session.add(p)
        db.session.commit()
    response = client.get('/products')
    data = response.get_json()
    assert sorted(data[0]['tags']) == ['electronics', 'sale']


def test_create_product_with_tags(logged_in_client, app):
    response = logged_in_client.post('/products', json={
        'name': 'New Item', 'price': 4.99, 'tags': ['sale', 'new'],
    })
    assert response.status_code == 201

    with app.app_context():
        product = Product.query.filter_by(name='New Item').first()
        assert sorted(t.name for t in product.tags) == ['new', 'sale']


def test_create_product_tag_reuse(logged_in_client, app):
    logged_in_client.post('/products', json={'name': 'A', 'price': 1.0, 'tags': ['sale']})
    logged_in_client.post('/products', json={'name': 'B', 'price': 1.0, 'tags': ['Sale']})

    with app.app_context():
        assert Tag.query.filter_by(name='sale').count() == 1


def test_update_product_tags(logged_in_client, app):
    with app.app_context():
        p = Product(name='Widget', price=5.00, stock=1)
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    response = logged_in_client.put(f'/products/{product_id}', json={'tags': ['clearance']})
    assert response.status_code == 200

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert [t.name for t in product.tags] == ['clearance']


def test_update_product_tags_empty_list_clears(logged_in_client, app):
    with app.app_context():
        p = Product(name='Widget', price=5.00, stock=1)
        p.tags = [Tag(name='old')]
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    logged_in_client.put(f'/products/{product_id}', json={'tags': []})

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product.tags == []


def test_update_product_without_tags_key_leaves_tags_unchanged(logged_in_client, app):
    with app.app_context():
        p = Product(name='Widget', price=5.00, stock=1)
        p.tags = [Tag(name='keepme')]
        db.session.add(p)
        db.session.commit()
        product_id = p.id

    logged_in_client.put(f'/products/{product_id}', json={'name': 'New Name'})

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert [t.name for t in product.tags] == ['keepme']
