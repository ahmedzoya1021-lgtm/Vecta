"""
Reads and writes holdings for a specific user, via the database.
"""
from models import Holding, db


def list_holdings(user):
    return [h.to_dict() for h in user.holdings]


def add_holding(user, symbol, shares, cost_basis):
    holding = Holding(
        user_id=user.id,
        symbol=symbol.upper().strip(),
        shares=float(shares),
        cost_basis=float(cost_basis),
    )
    db.session.add(holding)
    db.session.commit()
    return holding.to_dict()


def update_holding(user, holding_id, shares, cost_basis):
    holding = Holding.query.filter_by(id=holding_id, user_id=user.id).first()
    if holding is None:
        return None
    holding.shares = float(shares)
    holding.cost_basis = float(cost_basis)
    db.session.commit()
    return holding.to_dict()


def delete_holding(user, holding_id):
    Holding.query.filter_by(id=holding_id, user_id=user.id).delete()
    db.session.commit()
