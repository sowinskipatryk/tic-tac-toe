from app import db
import datetime


class GameStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.String(36))
    wins = db.Column(db.Boolean)
    loses = db.Column(db.Boolean)
    draws = db.Column(db.Boolean)
    games_played = db.Column(db.Integer)
    games_length = db.Column(db.Interval, default=datetime.timedelta())
