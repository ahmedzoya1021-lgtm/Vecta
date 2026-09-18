"""
Reads and writes a specific user's watchlist, via the database.
"""
from models import WatchlistItem, db


def list_watchlist(user):
    return [item.to_dict() for item in user.watchlist]


def add_to_watchlist(user, symbol):
    item = WatchlistItem(user_id=user.id, symbol=symbol.upper().strip())
    db.session.add(item)
    db.session.commit()
    return item.to_dict()


def remove_from_watchlist(user, item_id):
    WatchlistItem.query.filter_by(id=item_id, user_id=user.id).delete()
    db.session.commit()
