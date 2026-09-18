"""
Database models. Each class here becomes a table.

We use SQLAlchemy, which lets us work with database rows as Python objects
(e.g. `holding.shares`) instead of writing raw SQL.
"""
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

INSIGHT_CACHE_TTL = timedelta(hours=12)


def utcnow():
    """Naive UTC datetime — SQLite doesn't preserve timezone info, so we
    keep every stored timestamp naive-but-UTC for consistent comparisons."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    watchlist = db.relationship(
        "WatchlistItem", backref="owner", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class WatchlistItem(db.Model):
    """A company a user wants geopolitical context on — no shares, no cost
    basis. Vecta isn't tracking money here, just watching a company."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {"id": self.id, "symbol": self.symbol}


class InsightCache(db.Model):
    """Stores the last AI geopolitical summary per symbol, so we don't
    re-call Claude (and re-run a web search) every time someone looks."""

    symbol = db.Column(db.String(20), primary_key=True)
    summary = db.Column(db.Text, nullable=False)
    sources_json = db.Column(db.Text, nullable=False, default="[]")
    fetched_at = db.Column(db.DateTime, nullable=False)

    def is_fresh(self):
        return utcnow() - self.fetched_at < INSIGHT_CACHE_TTL


class WatchlistBriefing(db.Model):
    """Stores the last whole-watchlist AI briefing for a user. Unlike
    InsightCache (shared across everyone, keyed by symbol), this is unique
    per user since it depends on their specific list of companies. We clear
    a user's row whenever their watchlist changes, so it's never
    stale-wrong — the time-based freshness check below is just a backup limit."""

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    summary = db.Column(db.Text, nullable=False)
    sources_json = db.Column(db.Text, nullable=False, default="[]")
    fetched_at = db.Column(db.DateTime, nullable=False)

    def is_fresh(self):
        return utcnow() - self.fetched_at < timedelta(hours=6)


class PriceCache(db.Model):
    """Stores the last fetched stock price per symbol for a short time,
    so refreshing the page doesn't re-fetch every price every time."""

    symbol = db.Column(db.String(20), primary_key=True)
    price = db.Column(db.Float, nullable=False)
    fetched_at = db.Column(db.DateTime, nullable=False)

    def is_fresh(self):
        return utcnow() - self.fetched_at < timedelta(minutes=1)
