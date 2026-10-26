"""FIFO position and P&L calculation (pure Python, no Django imports)."""
from collections import defaultdict, deque
from decimal import Decimal


def compute_positions(transactions):
    """
    transactions: iterable of dicts with keys ticker, type ("BUY"/"SELL"),
    quantity, price, already sorted oldest -> newest.

    Returns {ticker: {quantity, cost_basis, avg_cost, realized_pnl}} using FIFO lots.
    Raises ValueError when a SELL exceeds the quantity currently held.
    """
    lots = defaultdict(deque)          # ticker -> deque([qty, price])
    realized = defaultdict(lambda: Decimal("0"))

    for t in transactions:
        ticker = t["ticker"]
        qty = Decimal(str(t["quantity"]))
        price = Decimal(str(t["price"]))

        if t["type"] == "BUY":
            lots[ticker].append([qty, price])
        elif t["type"] == "SELL":
            remaining = qty
            while remaining > 0:
                if not lots[ticker]:
                    raise ValueError(f"Cannot sell {qty} {ticker}: more than currently held")
                lot = lots[ticker][0]
                take = min(lot[0], remaining)
                realized[ticker] += (price - lot[1]) * take
                lot[0] -= take
                remaining -= take
                if lot[0] == 0:
                    lots[ticker].popleft()
        else:
            raise ValueError(f"Unknown transaction type: {t['type']}")

    positions = {}
    for ticker in set(lots) | set(realized):
        held = sum((lot[0] for lot in lots[ticker]), Decimal("0"))
        cost = sum((lot[0] * lot[1] for lot in lots[ticker]), Decimal("0"))
        positions[ticker] = {
            "quantity": held,
            "cost_basis": cost,
            "avg_cost": cost / held if held else Decimal("0"),
            "realized_pnl": realized[ticker],
        }
    return positions
