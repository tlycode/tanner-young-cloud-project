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

