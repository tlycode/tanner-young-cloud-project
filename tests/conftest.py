# tests/conftest.py

import pytest
from app import create_app
from app.models import db, User


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
def logged_in_client(client, app):
    client.post('/register', data={'email': 'admin@example.com', 'password': 'password123'})
    with app.app_context():
        user = User.query.filter_by(email='admin@example.com').first()
        user.is_admin = True
        db.session.commit()
    client.post('/login', data={'email': 'admin@example.com', 'password': 'password123'})
    return client


@pytest.fixture
def admin_client(client, app):
    client.post('/register', data={'email': 'admin2@example.com', 'password': 'password123'})
    with app.app_context():
        user = User.query.filter_by(email='admin2@example.com').first()
        user.is_admin = True
        db.session.commit()
    client.post('/login', data={'email': 'admin2@example.com', 'password': 'password123'})
    return client


@pytest.fixture
def regular_client(client):
    client.post('/register', data={'email': 'user@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'user@example.com', 'password': 'password123'})
    return client
