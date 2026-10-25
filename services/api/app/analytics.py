"""Position accounting using average-cost method."""
from __future__ import annotations

from collections import defaultdict

from . import prices


def positions(txns) -> tuple[dict[str, dict], float]:
    """Returns ({symbol: {qty, avg_cost}}, realized_pnl)."""
    pos = defaultdict(lambda: {"qty": 0.0, "cost": 0.0})
    realized = 0.0
    for t in sorted(txns, key=lambda x: (x.trade_date, x.id or 0)):
        p = pos[t.symbol]
        if t.side == "buy":
            p["qty"] += t.quantity
            p["cost"] += t.quantity * t.price + t.fees
        else:
            if t.quantity > p["qty"] + 1e-9:
                raise ValueError(f"cannot sell {t.quantity} {t.symbol}; only {p['qty']} held")
            avg = p["cost"] / p["qty"]
            realized += t.quantity * (t.price - avg) - t.fees
            p["qty"] -= t.quantity
            p["cost"] -= avg * t.quantity
    out = {s: {"qty": v["qty"], "avg_cost": v["cost"] / v["qty"]} for s, v in pos.items() if v["qty"] > 1e-9}
    return out, realized


def summary(txns) -> dict:
    pos, realized = positions(txns)
    holdings, total_value, total_cost = [], 0.0, 0.0
    for sym, p in sorted(pos.items()):
        px = prices.latest(sym)
        value, cost = p["qty"] * px, p["qty"] * p["avg_cost"]
        total_value += value
        total_cost += cost
        holdings.append({
            "symbol": sym, "quantity": round(p["qty"], 6), "avg_cost": round(p["avg_cost"], 4),
            "price": px, "market_value": round(value, 2), "cost_basis": round(cost, 2),
            "unrealized_pnl": round(value - cost, 2),
            "unrealized_pnl_pct": round((value / cost - 1) * 100, 2) if cost else 0.0,
        })
    for h in holdings:
        h["weight"] = round(h["market_value"] / total_value, 4) if total_value else 0.0
    return {
        "holdings": holdings,
        "totals": {
            "market_value": round(total_value, 2), "cost_basis": round(total_cost, 2),
            "unrealized_pnl": round(total_value - total_cost, 2),
            "unrealized_pnl_pct": round((total_value / total_cost - 1) * 100, 2) if total_cost else 0.0,
            "realized_pnl": round(realized, 2),
        },
    }
