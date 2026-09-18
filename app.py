"""
Vecta — a watchlist with AI-generated geopolitical context, not a portfolio
tracker. We deliberately don't track shares or cost basis: other apps
already do P&L tracking well, and that's not the point here.

Run it with: python app.py
Then open http://localhost:5000 in your browser.
"""
import json
import os

import yfinance as yf
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager, current_user, login_required

import insights
import storage
from auth import auth_bp
from models import InsightCache, PriceCache, User, WatchlistBriefing, db, utcnow

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    os.path.dirname(__file__), "vecta.db"
)
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.register_blueprint(auth_bp)

with app.app_context():
    db.create_all()


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/watchlist")
@login_required
def get_watchlist():
    items = storage.list_watchlist(current_user)
    for item in items:
        item["price"] = _get_price(item["symbol"])
    return jsonify({"watchlist": items})


def _invalidate_watchlist_briefing(user):
    """The watchlist changed, so any cached briefing is now describing a
    list that no longer exists — clear it."""
    cached = db.session.get(WatchlistBriefing, user.id)
    if cached is not None:
        db.session.delete(cached)
        db.session.commit()


@app.route("/api/watchlist", methods=["POST"])
@login_required
def add_to_watchlist():
    data = request.get_json()
    symbol = data.get("symbol", "")

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    item = storage.add_to_watchlist(current_user, symbol)
    _invalidate_watchlist_briefing(current_user)
    return jsonify(item), 201


@app.route("/api/watchlist/<int:item_id>", methods=["DELETE"])
@login_required
def remove_from_watchlist(item_id):
    storage.remove_from_watchlist(current_user, item_id)
    _invalidate_watchlist_briefing(current_user)
    return "", 204


@app.route("/api/insights/<symbol>")
@login_required
def get_insight(symbol):
    symbol = symbol.upper()

    cached = db.session.get(InsightCache, symbol)
    if cached is not None and cached.is_fresh():
        return jsonify(
            {"available": True, "summary": cached.summary, "sources": json.loads(cached.sources_json)}
        )

    result = insights.get_geopolitical_context(symbol)

    if result["available"]:
        cached = cached or InsightCache(symbol=symbol)
        cached.summary = result["summary"]
        cached.sources_json = json.dumps(result.get("sources", []))
        cached.fetched_at = utcnow()
        db.session.add(cached)
        db.session.commit()

    return jsonify(result)


@app.route("/api/watchlist-briefing")
@login_required
def get_watchlist_briefing():
    cached = db.session.get(WatchlistBriefing, current_user.id)
    if cached is not None and cached.is_fresh():
        return jsonify(
            {"available": True, "summary": cached.summary, "sources": json.loads(cached.sources_json)}
        )

    symbols = [item["symbol"] for item in storage.list_watchlist(current_user)]

    if not symbols:
        return jsonify({"available": False, "summary": "Add a company first to get a briefing."})

    result = insights.get_watchlist_briefing(symbols)

    if result["available"]:
        cached = cached or WatchlistBriefing(user_id=current_user.id)
        cached.summary = result["summary"]
        cached.sources_json = json.dumps(result.get("sources", []))
        cached.fetched_at = utcnow()
        db.session.add(cached)
        db.session.commit()

    return jsonify(result)


def _get_price(symbol):
    cached = db.session.get(PriceCache, symbol)
    if cached is not None and cached.is_fresh():
        return cached.price

    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.get("lastPrice")
        price = float(price) if price is not None else None
    except Exception:
        price = None

    if price is not None:
        cached = cached or PriceCache(symbol=symbol)
        cached.price = price
        cached.fetched_at = utcnow()
        db.session.add(cached)
        db.session.commit()
        return price

    # Fetch failed — fall back to the last known price if we have one, even if stale.
    return cached.price if cached is not None else None


if __name__ == "__main__":
    app.run(debug=True, port=5000)
