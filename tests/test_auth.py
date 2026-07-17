# tests/test_auth.py

import re

import pytest
from app import create_app
from app.models import db, User
from app.routes.auth import generate_reset_token


def test_register(client):
    response = client.post('/register', data={
        'email': 'test@example.com',
        'password': 'password123'
    })
    assert response.status_code == 302


def test_register_duplicate_email(client):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    response = client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    assert response.status_code == 302
    assert b'/register' in response.headers['Location'].encode()


def test_register_short_password(client):
    response = client.post('/register', data={
        'email': 'test@example.com',
        'password': 'abc'
    })
    assert response.status_code == 302
    assert b'/register' in response.headers['Location'].encode()


def test_login_success(client):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    response = client.post('/login', data={'email': 'test@example.com', 'password': 'password123'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_login_invalid_password(client):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    response = client.post('/login', data={'email': 'test@example.com', 'password': 'wrong'})
    assert response.status_code == 302
    assert b'/login' in response.headers['Location'].encode()


def test_logout(logged_in_client):
    response = logged_in_client.get('/logout')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')


def test_forgot_password_known_email_logs_link(client, app, caplog):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    with caplog.at_level('INFO'):
        response = client.post('/forgot-password', data={'email': 'test@example.com'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')
    assert any('Password reset requested for test@example.com' in r.message for r in caplog.records)


def test_forgot_password_unknown_email_does_not_leak(client):
    response = client.post('/forgot-password', data={'email': 'nobody@example.com'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')


def test_reset_password_with_valid_token(client, app):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        token = generate_reset_token(user)

    response = client.post(f'/reset-password/{token}', data={'password': 'newpassword456'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/login')

    login_response = client.post('/login', data={'email': 'test@example.com', 'password': 'newpassword456'})
    assert login_response.headers['Location'].endswith('/')

    old_login_response = client.post('/login', data={'email': 'test@example.com', 'password': 'password123'})
    assert b'/login' in old_login_response.headers['Location'].encode()


def test_reset_password_token_is_single_use(client, app):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        token = generate_reset_token(user)

    client.post(f'/reset-password/{token}', data={'password': 'newpassword456'})
    second_response = client.post(f'/reset-password/{token}', data={'password': 'anotherpassword789'})
    assert second_response.status_code == 302
    assert second_response.headers['Location'].endswith('/forgot-password')


def test_reset_password_invalid_token(client):
    response = client.get('/reset-password/not-a-real-token')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/forgot-password')


def test_reset_password_short_password(client, app):
    client.post('/register', data={'email': 'test@example.com', 'password': 'password123'})
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        token = generate_reset_token(user)

    response = client.post(f'/reset-password/{token}', data={'password': 'abc'})
    assert response.status_code == 302
    assert f'/reset-password/{token}' in response.headers['Location']


def test_csrf_token_required():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': True,
        'WTF_CSRF_CHECK_DEFAULT': True,
    })
    client = app.test_client()
    response = client.post('/register', data={
        'email': 'test@example.com',
        'password': 'password123'
    })
    assert response.status_code == 400
