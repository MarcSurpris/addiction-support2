from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime
from flask_login import UserMixin
import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(12), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)

class Entry(db.Model):
    __tablename__ = 'entry'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    addiction_type = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)