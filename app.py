"""
Vecta — Stage 3.

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
from models import InsightCache, PortfolioInsight, PriceCache, User, db, utcnow

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


def _compute_portfolio(user):
    holdings = storage.list_holdings(user)
    result = []
    total_value = 0.0
    total_cost = 0.0

    for h in holdings:
        price = _get_price(h["symbol"])
        value = price * h["shares"] if price is not None else None
        cost = h["cost_basis"] * h["shares"]
        gain = (value - cost) if value is not None else None

        if value is not None:
            total_value += value
        total_cost += cost

        result.append(
            {
                **h,
                "price": price,
                "value": value,
                "gain": gain,
                "gain_pct": (gain / cost * 100) if gain is not None and cost else None,
            }
        )

    # Now that we know the total, go back and add each holding's % of the whole.
    for h in result:
        h["weight_pct"] = (h["value"] / total_value * 100) if h["value"] and total_value else None

    return {
        "holdings": result,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_gain": total_value - total_cost,
    }


@app.route("/api/portfolio")
@login_required
def get_portfolio():
    return jsonify(_compute_portfolio(current_user))


def _invalidate_portfolio_insight(user):
    """Your holdings changed, so any cached whole-portfolio briefing is now
    describing a portfolio that no longer exists — clear it."""
    cached = db.session.get(PortfolioInsight, user.id)
    if cached is not None:
        db.session.delete(cached)
        db.session.commit()


@app.route("/api/holdings", methods=["POST"])
@login_required
def add_holding():
    data = request.get_json()
    symbol = data.get("symbol", "")
    shares = data.get("shares")
    cost_basis = data.get("cost_basis")

    if not symbol or shares is None or cost_basis is None:
        return jsonify({"error": "symbol, shares, and cost_basis are required"}), 400

    holding = storage.add_holding(current_user, symbol, shares, cost_basis)
    _invalidate_portfolio_insight(current_user)
    return jsonify(holding), 201


@app.route("/api/holdings/<int:holding_id>", methods=["PUT"])
@login_required
def update_holding(holding_id):
    data = request.get_json()
    shares = data.get("shares")
    cost_basis = data.get("cost_basis")

    if shares is None or cost_basis is None:
        return jsonify({"error": "shares and cost_basis are required"}), 400

    holding = storage.update_holding(current_user, holding_id, shares, cost_basis)
    if holding is None:
        return jsonify({"error": "not found"}), 404
    _invalidate_portfolio_insight(current_user)
    return jsonify(holding)


@app.route("/api/holdings/<int:holding_id>", methods=["DELETE"])
@login_required
def delete_holding(holding_id):
    storage.delete_holding(current_user, holding_id)
    _invalidate_portfolio_insight(current_user)
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


@app.route("/api/portfolio-insight")
@login_required
def get_portfolio_insight():
    cached = db.session.get(PortfolioInsight, current_user.id)
    if cached is not None and cached.is_fresh():
        return jsonify(
            {"available": True, "summary": cached.summary, "sources": json.loads(cached.sources_json)}
        )

    portfolio = _compute_portfolio(current_user)
    holdings_with_weight = [
        {"symbol": h["symbol"], "weight_pct": h["weight_pct"]}
        for h in portfolio["holdings"]
        if h["weight_pct"] is not None
    ]

    if not holdings_with_weight:
        return jsonify({"available": False, "summary": "Add a holding first to get a portfolio briefing."})

    result = insights.get_portfolio_briefing(holdings_with_weight)

    if result["available"]:
        cached = cached or PortfolioInsight(user_id=current_user.id)
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
