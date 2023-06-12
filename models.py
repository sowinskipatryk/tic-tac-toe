from app import db
from datetime import datetime, timedelta


class GameStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.String(36))
    wins = db.Column(db.Integer)
    draws = db.Column(db.Integer)
    losses = db.Column(db.Integer)
    games_length = db.Column(db.Interval, default=timedelta())
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
