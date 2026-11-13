class PositionNotFoundError(Exception):
    pass


class LatestPriceNotFoundError(Exception):
    pass


class TradeNotFoundError(Exception):
    pass


class OversellError(Exception):
    pass


class DuplicateTradeConflictError(Exception):
    pass
