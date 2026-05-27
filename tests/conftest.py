# tests/conftest.py

import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def logged_in_client(client):
    client.post('/register', data={'email': 'admin@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'admin@example.com', 'password': 'password123'})
    return client
