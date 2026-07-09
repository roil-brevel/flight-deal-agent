"""Travelpayouts (Aviasales) Data API adapter — the free broad radar."""
from __future__ import annotations

import os
from datetime import date, datetime

import requests

BASE = "https://api.travelpayouts.com"
TIMEOUT = 25


def _token() -> str:
    tok = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not tok:
        raise RuntimeError("TRAVELPAYOUTS_TOKEN not set")
    return tok


def _get(path: str, params: dict) -> dict:
    params = {**params, "token": _token()}
    r = requests.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _norm(rec: dict, goal_id: str, currency: str) -> dict:
    return {
        "goal_id": goal_id,
        "source": "travelpayouts",
        "basis": "per_adult",
        "origin": rec.get("origin"),
        "destination": rec.get("destination"),
        "depart_date": (rec.get("departure_at") or "")[:10] or None,
        "return_date": (rec.get("return_at") or "")[:10] or None,
        "price": float(rec["price"]),
        "currency": currency.upper(),
        "airline": rec.get("airline"),
        "transfers": rec.get("transfers"),
        "deep_link": None,
    }


def _within(d: str | None, lo: str, hi: str) -> bool:
    if not d:
        return False
    return lo <= d <= hi


def discover(origin: str, currency: str, depart_from: str, depart_to: str,
             goal_id: str, limit: int = 30) -> list[dict]:
    """Cheapest destinations from `origin` (city-directions endpoint)."""
    data = _get("/v1/city-directions",
                {"origin": origin, "currency": currency}).get("data", {})
    rows = []
    for _, rec in data.items():
        row = _norm(rec, goal_id, currency)
        row["in_window"] = _within(row["depart_date"], depart_from, depart_to)
        rows.append(row)
    rows.sort(key=lambda r: r["price"])
    return rows[:limit]


def calendar(origin: str, destination: str, month: str, currency: str,
             goal_id: str) -> list[dict]:
    """Cheapest fare per departure day for a given month (YYYY-MM)."""
    data = _get("/v1/prices/calendar", {
        "origin": origin, "destination": destination,
        "depart_date": month, "currency": currency,
        "calendar_type": "departure_date",
    }).get("data", {})
    return [_norm(rec, goal_id, currency) for rec in data.values()]


def prices_for_dates(origin: str, destination: str, depart_month: str,
                     currency: str, goal_id: str, limit: int = 30) -> list[dict]:
    """v3 grouped cheapest fares for a route/month (may be empty far-future)."""
    data = _get("/aviasales/v3/prices_for_dates", {
        "origin": origin, "destination": destination,
        "departure_at": depart_month, "currency": currency,
        "sorting": "price", "limit": limit, "one_way": "false",
    }).get("data", [])
    return [_norm(rec, goal_id, currency) for rec in data]


def _months_between(depart_from: str, depart_to: str) -> list[str]:
    a = datetime.strptime(depart_from, "%Y-%m-%d").date()
    b = datetime.strptime(depart_to, "%Y-%m-%d").date()
    months, cur = [], date(a.year, a.month, 1)
    while cur <= b:
        months.append(cur.strftime("%Y-%m"))
        cur = date(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    return months


def route(origin: str, destination: str, depart_from: str, depart_to: str,
          currency: str, goal_id: str) -> list[dict]:
    """All cached fares for a specific route inside the departure window."""
    rows: list[dict] = []
    for m in _months_between(depart_from, depart_to):
        try:
            rows += calendar(origin, destination, m, currency, goal_id)
        except requests.HTTPError:
            pass
        try:
            rows += prices_for_dates(origin, destination, m, currency, goal_id)
        except requests.HTTPError:
            pass
    best: dict[str, dict] = {}
    for r in rows:
        if not _within(r["depart_date"], depart_from, depart_to):
            continue
        key = r["depart_date"]
        if key not in best or r["price"] < best[key]["price"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: r["price"])
