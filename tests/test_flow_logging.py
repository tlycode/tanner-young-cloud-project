# tests/test_flow_logging.py

"""Logging coverage for the vital flows.

These assert the *level* each event is recorded at, not just that something
was logged - the level is what makes the terminal output scannable.
"""

import logging
from unittest.mock import patch

import pytest

from app.logger import NOTICE
from app.models import db, Product


def records_for(caplog, needle):
    return [r for r in caplog.records if needle in r.message]


def one_record(caplog, needle):
    matches = records_for(caplog, needle)
    assert matches, f'no log record containing {needle!r}'
    return matches[0]


@pytest.fixture
def product(app):
    with app.app_context():
        item = Product(name='Blue Mug', price=12.50, stock=10)
        db.session.add(item)
        db.session.commit()
        return item.id


# --- registration ---------------------------------------------------------

def test_successful_registration_logs_info(client, caplog):
    with caplog.at_level(logging.INFO):
        client.post('/register', data={'email': 'new@example.com', 'password': 'password123'})
    assert one_record(caplog, 'New user registered').levelno == logging.INFO


def test_short_password_logs_info(client, caplog):
    # Routine form validation - INFO, so it doesn't crowd NOTICE.
    with caplog.at_level(logging.INFO):
        client.post('/register', data={'email': 'new@example.com', 'password': 'short'})
    assert one_record(caplog, 'password too short').levelno == logging.INFO


def test_duplicate_email_logs_notice(client, caplog):
    client.post('/register', data={'email': 'dup@example.com', 'password': 'password123'})
    with caplog.at_level(NOTICE):
        client.post('/register', data={'email': 'dup@example.com', 'password': 'password123'})
    assert one_record(caplog, 'email already registered').levelno == NOTICE


def test_registration_db_failure_logs_error_with_traceback(client, caplog):
    with caplog.at_level(logging.ERROR):
        with patch('app.routes.auth.db.session.commit', side_effect=RuntimeError('db down')):
            response = client.post('/register',
                                   data={'email': 'x@example.com', 'password': 'password123'})
    record = one_record(caplog, 'Registration failed')
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert response.status_code == 302


# --- login ----------------------------------------------------------------

def test_successful_login_logs_info(client, caplog):
    client.post('/register', data={'email': 'a@example.com', 'password': 'password123'})
    with caplog.at_level(logging.INFO):
        client.post('/login', data={'email': 'a@example.com', 'password': 'password123'})
    assert one_record(caplog, 'Login success').levelno == logging.INFO


def test_single_login_failure_logs_notice(client, caplog):
    client.post('/register', data={'email': 'a@example.com', 'password': 'password123'})
    with caplog.at_level(NOTICE):
        client.post('/login', data={'email': 'a@example.com', 'password': 'nope12345'})
    record = one_record(caplog, 'Login failure')
    assert record.levelno == NOTICE
    assert 'attempts=1' in record.message
    assert 'reason=bad_password' in record.message


def test_repeated_login_failures_escalate_to_warn(client, caplog):
    client.post('/register', data={'email': 'a@example.com', 'password': 'password123'})
    with caplog.at_level(NOTICE):
        for _ in range(3):
            client.post('/login', data={'email': 'a@example.com', 'password': 'nope12345'})
    escalated = one_record(caplog, 'Repeated login failures')
    assert escalated.levelno == logging.WARNING
    assert 'attempts=3' in escalated.message


def test_unknown_email_login_is_flagged_as_such(client, caplog):
    with caplog.at_level(NOTICE):
        client.post('/login', data={'email': 'ghost@example.com', 'password': 'whatever1'})
    assert 'reason=unknown_email' in one_record(caplog, 'Login failure').message


def test_successful_login_resets_the_failure_counter(client, caplog):
    client.post('/register', data={'email': 'a@example.com', 'password': 'password123'})
    for _ in range(2):
        client.post('/login', data={'email': 'a@example.com', 'password': 'nope12345'})
    client.post('/login', data={'email': 'a@example.com', 'password': 'password123'})
    with caplog.at_level(NOTICE):
        client.post('/login', data={'email': 'a@example.com', 'password': 'nope12345'})
    # Counter restarted, so this is a NOTICE rather than a WARN.
    assert 'attempts=1' in one_record(caplog, 'Login failure').message


# --- checkout -------------------------------------------------------------

def test_successful_order_logs_info(regular_client, product, caplog):
    regular_client.post(f'/cart/add/{product}', data={'quantity': 2})
    with caplog.at_level(logging.INFO):
        regular_client.post('/cart/checkout', data={
            'full_name': 'Sam', 'address': '1 Main St', 'city': 'Berkeley', 'zip': '94704'})
    record = one_record(caplog, 'Order placed')
    assert record.levelno == logging.INFO
    assert 'total=25.00' in record.message


def test_incomplete_address_logs_info_with_missing_fields(regular_client, product, caplog):
    regular_client.post(f'/cart/add/{product}', data={'quantity': 1})
    with caplog.at_level(logging.INFO):
        regular_client.post('/cart/checkout', data={
            'full_name': 'Sam', 'address': '', 'city': '', 'zip': ''})
    record = one_record(caplog, 'incomplete shipping address')
    assert record.levelno == logging.INFO
    # The missing fields are what make this actionable.
    assert 'missing=address,city,zip' in record.message


def test_order_db_failure_logs_error_and_preserves_cart(regular_client, product, caplog):
    regular_client.post(f'/cart/add/{product}', data={'quantity': 1})
    with caplog.at_level(logging.ERROR):
        with patch('app.routes.cart.db.session.commit', side_effect=RuntimeError('db down')):
            regular_client.post('/cart/checkout', data={
                'full_name': 'Sam', 'address': '1 Main St', 'city': 'Berkeley', 'zip': '94704'})
    record = one_record(caplog, 'Order failed: could not save order')
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    # The shopper must be able to retry, so the cart has to survive.
    with regular_client.session_transaction() as sess:
        assert sess['cart'] == {str(product): 1}


def test_empty_cart_at_submission_logs_error(regular_client, caplog):
    with caplog.at_level(logging.ERROR):
        regular_client.post('/cart/checkout', data={
            'full_name': 'Sam', 'address': '1 Main St', 'city': 'Berkeley', 'zip': '94704'})
    assert one_record(caplog, 'cart was empty at submission').levelno == logging.ERROR


def test_stale_cart_products_log_warn(regular_client, product, app, caplog):
    regular_client.post(f'/cart/add/{product}', data={'quantity': 1})
    with app.app_context():
        db.session.delete(db.session.get(Product, product))
        db.session.commit()
    with caplog.at_level(logging.WARNING):
        regular_client.get('/cart/')
    assert one_record(caplog, 'products that no longer exist').levelno == logging.WARNING


# --- products -------------------------------------------------------------

def test_admin_product_creation_logs_info(admin_client, caplog):
    with caplog.at_level(logging.INFO):
        admin_client.post('/admin/products/new', data={
            'name': 'Red Mug', 'description': '', 'price': '9.99', 'stock': '5'})
    record = one_record(caplog, 'Product created via admin')
    assert record.levelno == logging.INFO
    assert 'admin_id=' in record.message


def test_invalid_price_logs_info(admin_client, caplog):
    with caplog.at_level(logging.INFO):
        admin_client.post('/admin/products/new', data={
            'name': 'Red Mug', 'price': 'not-a-number', 'stock': '5'})
    assert one_record(caplog, 'invalid price').levelno == logging.INFO


def test_product_deletion_logs_notice(admin_client, product, caplog):
    with caplog.at_level(NOTICE):
        admin_client.post(f'/admin/products/{product}/delete')
    record = one_record(caplog, 'Product deleted via admin')
    assert record.levelno == NOTICE
    assert 'name=Blue Mug' in record.message


def test_admin_promotion_logs_notice(admin_client, client, app, caplog):
    client.post('/register', data={'email': 'promote@example.com', 'password': 'password123'})
    with app.app_context():
        from app.models import User
        target = User.query.filter_by(email='promote@example.com').first().id
    with caplog.at_level(NOTICE):
        admin_client.post(f'/admin/users/{target}/promote')
    assert one_record(caplog, 'User promoted to admin').levelno == NOTICE


def test_api_product_creation_db_failure_logs_error(admin_client, caplog):
    with caplog.at_level(logging.ERROR):
        with patch('app.routes.products.db.session.commit', side_effect=RuntimeError('db down')):
            response = admin_client.post('/products', json={'name': 'Mug', 'price': 1.00})
    assert response.status_code == 500
    assert one_record(caplog, 'Product creation failed').levelno == logging.ERROR


# --- access control -------------------------------------------------------

def test_accessing_another_users_order_logs_warn(client, regular_client, product, app, caplog):
    regular_client.post(f'/cart/add/{product}', data={'quantity': 1})
    regular_client.post('/cart/checkout', data={
        'full_name': 'Sam', 'address': '1 Main St', 'city': 'Berkeley', 'zip': '94704'})
    client.post('/register', data={'email': 'nosy@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'nosy@example.com', 'password': 'password123'})
    with caplog.at_level(logging.WARNING):
        response = client.get('/orders/1')
    assert response.status_code == 403
    assert one_record(caplog, "another user's order").levelno == logging.WARNING


def test_notice_is_reserved_for_significant_events(admin_client, product, caplog):
    """NOTICE should surface events worth attention, not form-validation noise."""
    with caplog.at_level(logging.INFO):
        # A typo in a form field.
        admin_client.post('/admin/products/new', data={
            'name': 'Mug', 'price': 'not-a-number', 'stock': '5'})
        # An irreversible change.
        admin_client.post(f'/admin/products/{product}/delete')

    assert one_record(caplog, 'invalid price').levelno == logging.INFO
    assert one_record(caplog, 'Product deleted via admin').levelno == NOTICE
