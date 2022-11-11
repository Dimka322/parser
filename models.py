from flask_login import UserMixin
from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String, unique=True)
    title = db.Column(db.String)
    domain = db.Column(db.String)
    depth = db.Column(db.Integer)
    price = db.Column(db.String)
    img = db.Column(db.String)


class Structure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String, unique=True)
    structure = db.Column(db.String)