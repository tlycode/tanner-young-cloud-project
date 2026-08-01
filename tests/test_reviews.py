# tests/test_reviews.py

from app.models import db, Product, User, Review


def _create_product(app, **kwargs):
    with app.app_context():
        p = Product(name=kwargs.get('name', 'Widget'), price=9.99, stock=5)
        db.session.add(p)
        db.session.commit()
        return p.id


def test_anonymous_cannot_create_review(client, app):
    product_id = _create_product(app)
    response = client.post(f'/products/{product_id}/reviews', data={'rating': '5'})
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_logged_in_user_can_create_review(regular_client, app):
    product_id = _create_product(app)
    response = regular_client.post(f'/products/{product_id}/reviews',
                                    data={'rating': '4', 'body': 'Pretty good'},
                                    follow_redirects=True)
    assert response.status_code == 200
    assert b'Thanks for your review' in response.data
    with app.app_context():
        reviews = Review.query.filter_by(product_id=product_id).all()
        assert len(reviews) == 1
        assert reviews[0].rating == 4
        assert reviews[0].body == 'Pretty good'


def test_invalid_rating_rejected(regular_client, app):
    product_id = _create_product(app)
    response = regular_client.post(f'/products/{product_id}/reviews',
                                    data={'rating': '6'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'between 1 and 5' in response.data
    with app.app_context():
        assert Review.query.filter_by(product_id=product_id).count() == 0


def test_duplicate_review_rejected(regular_client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '3'})
    response = regular_client.post(f'/products/{product_id}/reviews',
                                    data={'rating': '5'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'already reviewed' in response.data
    with app.app_context():
        reviews = Review.query.filter_by(product_id=product_id).all()
        assert len(reviews) == 1
        assert reviews[0].rating == 3


def test_author_can_edit_own_review(regular_client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '3', 'body': 'meh'})
    with app.app_context():
        review_id = Review.query.filter_by(product_id=product_id).first().id
    response = regular_client.post(f'/reviews/{review_id}/edit',
                                    data={'rating': '5', 'body': 'actually great'},
                                    follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        review = db.session.get(Review, review_id)
        assert review.rating == 5
        assert review.body == 'actually great'


def test_author_can_delete_own_review(regular_client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '3'})
    with app.app_context():
        review_id = Review.query.filter_by(product_id=product_id).first().id
    response = regular_client.post(f'/reviews/{review_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Review, review_id) is None


def test_other_user_cannot_edit_review(regular_client, client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '3'})
    with app.app_context():
        review_id = Review.query.filter_by(product_id=product_id).first().id

    client.post('/register', data={'email': 'other@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'other@example.com', 'password': 'password123'})
    response = client.post(f'/reviews/{review_id}/edit', data={'rating': '1'})
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(Review, review_id).rating == 3


def test_other_user_cannot_delete_review(regular_client, client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '3'})
    with app.app_context():
        review_id = Review.query.filter_by(product_id=product_id).first().id

    client.post('/register', data={'email': 'other2@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'other2@example.com', 'password': 'password123'})
    response = client.post(f'/reviews/{review_id}/delete')
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(Review, review_id) is not None


def test_admin_can_delete_any_review(regular_client, admin_client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '3'})
    with app.app_context():
        review_id = Review.query.filter_by(product_id=product_id).first().id

    response = admin_client.post(f'/reviews/{review_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Review, review_id) is None


def test_product_detail_shows_no_reviews_message(client, app):
    product_id = _create_product(app)
    response = client.get(f'/products/{product_id}')
    assert response.status_code == 200
    assert b'No reviews yet' in response.data


def test_product_detail_shows_average_rating(regular_client, client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '4'})

    client.post('/register', data={'email': 'second@example.com', 'password': 'password123'})
    client.post('/login', data={'email': 'second@example.com', 'password': 'password123'})
    client.post(f'/products/{product_id}/reviews', data={'rating': '2'})

    response = client.get(f'/products/{product_id}')
    assert response.status_code == 200
    assert b'3.0' in response.data
    assert b'2 reviews' in response.data


def test_index_shows_rating_badge(regular_client, app):
    product_id = _create_product(app)
    regular_client.post(f'/products/{product_id}/reviews', data={'rating': '5'})
    response = regular_client.get('/')
    assert response.status_code == 200
    assert b'(1)' in response.data
