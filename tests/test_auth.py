# tests/test_auth.py

import pytest
from app import create_app


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
