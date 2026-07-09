"""SerpAPI Google Flights adapter — live verification + price insights."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests

BASE = "https://serpapi.com/search.json"
TIMEOUT = 40


def _key() -> str:
    k = os.environ.get("SERPAPI_KEY")
    if not k:
        raise RuntimeError("SERPAPI_KEY not set")
    return k


def search(origin: str, destination: str, outbound_date: str,
           return_date: str | None, currency: str, passengers: dict,
           goal_id: str) -> dict:
    """One live Google Flights query. Returns {cheapest, insights, raw_count}."""
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": outbound_date,
        "currency": currency,
        "hl": "en",
        "adults": passengers.get("adults", 1),
        "children": passengers.get("children", 0),
        "infants_on_lap": passengers.get("infants_on_lap", 0),
        "infants_in_seat": passengers.get("infants_in_seat", 0),
        "api_key": _key(),
    }
    if return_date:
        params["return_date"] = return_date
        params["type"] = 1
    else:
        params["type"] = 2

    r = requests.get(BASE, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()

    flights = (data.get("best_flights") or []) + (data.get("other_flights") or [])
    cheapest = None
    for f in flights:
        price = f.get("price")
        if price is None:
            continue
        if cheapest is None or price < cheapest["price"]:
            legs = f.get("flights", [])
            cheapest = {
                "goal_id": goal_id,
                "source": "serpapi",
                "basis": "family_total",
                "origin": origin,
                "destination": destination,
                "depart_date": outbound_date,
                "return_date": return_date,
                "price": float(price),
                "currency": currency.upper(),
                "airline": legs[0].get("airline") if legs else None,
                "transfers": max(len(legs) - 1, 0),
                "deep_link": data.get("search_metadata", {}).get("google_flights_url"),
            }

    insights = None
    pi = data.get("price_insights")
    if pi:
        insights = {
            "verdict": pi.get("price_level"),
            "lowest": pi.get("lowest_price"),
            "typical_range": pi.get("typical_price_range"),
        }
    return {"cheapest": cheapest, "insights": insights, "raw_count": len(flights)}


def best_in_window(origin: str, destination: str, depart_from: str,
                   depart_to: str, min_nights: int, max_nights: int,
                   currency: str, passengers: dict, goal_id: str,
                   probe_days: list[str] | None = None,
                   budget_calls: int = 3) -> dict:
    """Probe a few departure dates in the window, return the best family total."""
    a = datetime.strptime(depart_from, "%Y-%m-%d").date()
    b = datetime.strptime(depart_to, "%Y-%m-%d").date()
    span = (b - a).days
    if probe_days is None:
        n = min(budget_calls, span + 1)
        step = max(span // max(n - 1, 1), 1) if n > 1 else 1
        probe_days = [(a + timedelta(days=i * step)).isoformat()
                      for i in range(n)]

    nights = (min_nights + max_nights) // 2
    best, insights, calls = None, None, 0
    for d in probe_days:
        dep = datetime.strptime(d, "%Y-%m-%d").date()
        ret = (dep + timedelta(days=nights)).isoformat()
        res = search(origin, destination, d, ret, currency, passengers, goal_id)
        calls += 1
        if res["insights"] and insights is None:
            insights = res["insights"]
        c = res["cheapest"]
        if c and (best is None or c["price"] < best["price"]):
            best = c
    return {"cheapest": best, "insights": insights, "calls": calls}
