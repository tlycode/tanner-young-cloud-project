# tests/test_orders.py

from app.models import db, Product, Order, OrderItem, Complaint, User


def _create_product(app, **kwargs):
    with app.app_context():
        p = Product(name=kwargs.get('name', 'Widget'), price=9.99, stock=50)
        db.session.add(p)
        db.session.commit()
        return p.id


SHIPPING = {
    'full_name': 'Jane Doe',
    'address': '123 Main St',
    'city': 'Springfield',
    'zip': '12345',
    'card_number': '4242424242424242',
    'card_expiry': '12/30',
    'card_cvc': '123',
}


def _place_order(client, product_id, quantity=2):
    client.post(f'/cart/add/{product_id}', data={'quantity': str(quantity)})
    return client.post('/cart/checkout', data=SHIPPING, follow_redirects=True)


def _make_admin(app, email='admin3@example.com'):
    admin = app.test_client()
    admin.post('/register', data={'email': email, 'password': 'password123'})
    with app.app_context():
        u = User.query.filter_by(email=email).first()
        u.is_admin = True
        db.session.commit()
    admin.post('/login', data={'email': email, 'password': 'password123'})
    return admin


def test_anonymous_checkout_requires_login(client, app):
    product_id = _create_product(app)
    client.post(f'/cart/add/{product_id}', data={'quantity': '1'})
    response = client.get('/cart/checkout')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

    response = client.post('/cart/checkout', data=SHIPPING)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_placing_order_creates_order_and_items(regular_client, app):
    product_id = _create_product(app, name='Gadget')
    response = _place_order(regular_client, product_id, quantity=3)
    assert response.status_code == 200
    assert b'has been placed' in response.data

    with app.app_context():
        order = Order.query.first()
        assert order is not None
        assert order.full_name == 'Jane Doe'
        assert order.city == 'Springfield'
        assert order.total == round(9.99 * 3, 2)
        items = OrderItem.query.filter_by(order_id=order.id).all()
        assert len(items) == 1
        assert items[0].quantity == 3
        assert items[0].product_name == 'Gadget'
        assert items[0].unit_price == 9.99


def test_placing_order_clears_cart(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    response = regular_client.get('/cart/')
    assert b'Your cart is empty' in response.data


def test_my_orders_lists_only_own_orders(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)

    response = regular_client.get('/orders/')
    assert response.status_code == 200
    assert b'Order #' in response.data

    # regular_client and client share the same underlying test client/cookie
    # jar (regular_client is built from the client fixture), so switch identity
    # on a fresh client to verify the other user's history stays empty.
    other_client = app.test_client()
    other_client.post('/register', data={'email': 'other@example.com', 'password': 'password123'})
    other_client.post('/login', data={'email': 'other@example.com', 'password': 'password123'})

    response = other_client.get('/orders/')
    assert response.status_code == 200
    assert b"You haven't placed any orders yet" in response.data


def test_owner_can_view_order_detail(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    response = regular_client.get(f'/orders/{order_id}')
    assert response.status_code == 200
    assert b'Springfield' in response.data


def test_other_user_cannot_view_order_detail(regular_client, client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    client.post('/register', data={'email': 'other2@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'other2@example.com', 'password': 'password123'})
    response = client.get(f'/orders/{order_id}')
    assert response.status_code == 403


def test_admin_can_view_any_order_detail(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    # Use a separate client for the admin so it doesn't share regular_client's
    # cookie jar/session (regular_client is built from the shared client fixture).
    admin = _make_admin(app)
    response = admin.get(f'/orders/{order_id}')
    assert response.status_code == 200
    assert b'Viewing as admin' in response.data


def test_buy_again_adds_items_to_cart(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id, quantity=2)
    with app.app_context():
        order_id = Order.query.first().id

    response = regular_client.post(f'/orders/{order_id}/buy-again', follow_redirects=True)
    assert response.status_code == 200
    cart_response = regular_client.get('/cart/')
    assert b'Widget' in cart_response.data


def test_return_order_sets_status(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    response = regular_client.post(f'/orders/{order_id}/return', follow_redirects=True)
    assert response.status_code == 200
    assert b'Return request' in response.data or b'return request' in response.data
    with app.app_context():
        assert db.session.get(Order, order_id).status == 'return_requested'


def test_return_order_twice_is_blocked(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    regular_client.post(f'/orders/{order_id}/return')
    response = regular_client.post(f'/orders/{order_id}/return', follow_redirects=True)
    assert response.status_code == 200
    assert b'already been requested' in response.data


def test_other_user_cannot_return_order(regular_client, client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    client.post('/register', data={'email': 'other3@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'other3@example.com', 'password': 'password123'})
    response = client.post(f'/orders/{order_id}/return')
    assert response.status_code == 403


def test_submit_complaint_creates_record(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    response = regular_client.post(f'/orders/{order_id}/complaint',
                                    data={'message': 'Item arrived damaged'},
                                    follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        complaint = Complaint.query.filter_by(order_id=order_id).first()
        assert complaint is not None
        assert complaint.message == 'Item arrived damaged'


def test_empty_complaint_rejected(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    response = regular_client.post(f'/orders/{order_id}/complaint',
                                    data={'message': '   '}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Complaint.query.filter_by(order_id=order_id).count() == 0


def test_admin_complaints_page_lists_complaints(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id
    regular_client.post(f'/orders/{order_id}/complaint', data={'message': 'Box was crushed'})

    admin = _make_admin(app)
    response = admin.get('/admin/complaints')
    assert response.status_code == 200
    assert b'Box was crushed' in response.data


def test_regular_user_cannot_view_admin_complaints(regular_client):
    response = regular_client.get('/admin/complaints')
    assert response.status_code == 403


def test_admin_order_lookup_redirects_to_detail(regular_client, app):
    product_id = _create_product(app)
    _place_order(regular_client, product_id)
    with app.app_context():
        order_id = Order.query.first().id

    admin = _make_admin(app)
    response = admin.get(f'/admin/orders/lookup?order_id={order_id}')
    assert response.status_code == 302
    assert f'/admin/orders/{order_id}' in response.headers['Location']

    response = admin.get(f'/admin/orders/{order_id}')
    assert response.status_code == 200
