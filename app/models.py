# app/models.py

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password_hash = db.Column(db.String(128), nullable=False)

    is_admin = db.Column(db.Boolean, default=False)


product_tags = db.Table(
    'product_tags',
    db.Column('product_id', db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True),
)


class Tag(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(50), unique=True, nullable=False)


class Product(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)

    description = db.Column(db.Text)

    price = db.Column(db.Float, nullable=False)

    stock = db.Column(db.Integer, default=0)

    image_url = db.Column(db.String(200))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    tags = db.relationship('Tag', secondary=product_tags,
                           backref=db.backref('products', lazy='dynamic'),
                           lazy='joined')


class Review(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    rating = db.Column(db.Integer, nullable=False)

    body = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', backref=db.backref('reviews', lazy='dynamic', cascade='all, delete-orphan'))

    user = db.relationship('User')

    __table_args__ = (db.UniqueConstraint('product_id', 'user_id', name='uq_review_product_user'),)


class Order(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    status = db.Column(db.String(20), nullable=False, default='placed')

    total = db.Column(db.Float, nullable=False)

    full_name = db.Column(db.String(200), nullable=False)

    address = db.Column(db.String(200), nullable=False)

    city = db.Column(db.String(100), nullable=False)

    zip_code = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User')

    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan', lazy='joined')


class OrderItem(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'), nullable=False)

    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='SET NULL'), nullable=True)

    product_name = db.Column(db.String(200), nullable=False)

    unit_price = db.Column(db.Float, nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    product = db.relationship('Product')


class Complaint(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)

    message = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    order = db.relationship('Order', backref=db.backref('complaints', lazy='dynamic', cascade='all, delete-orphan'))

    user = db.relationship('User')

