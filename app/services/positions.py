from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.position import Position
from app.services.errors import PositionNotFoundError


def list_positions(session: Session) -> list[Position]:
    return list(session.scalars(select(Position).order_by(Position.symbol)))


def get_position(session: Session, symbol: str) -> Position:
    position = session.get(Position, symbol)
    if position is None:
        raise PositionNotFoundError(f"no position exists for {symbol}")
    return position
