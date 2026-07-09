"""Deal detection — statistics over our own accumulated price history."""
from __future__ import annotations

import statistics
from datetime import datetime


def _median(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def assess(current_price: float, history_prices: list[float], cfg: dict,
           insight_verdict: str | None = None) -> dict:
    """Classify a fare as 'strong', 'watch', or 'none' vs its history."""
    d = cfg["deals"]
    obs = [p for p in history_prices if p is not None]
    result = {
        "level": "none",
        "median": None,
        "lowest": min(obs) if obs else None,
        "pct_below_median": None,
        "is_new_low": bool(obs) and current_price <= min(obs),
        "reasons": [],
    }

    if len(obs) < d["min_observations"]:
        if insight_verdict == "low":
            result["level"] = "watch"
            result["reasons"].append("Google rates this fare 'low' (limited history)")
        return result

    med = _median(obs)
    result["median"] = med
    pct_below = (med - current_price) / med if med else 0.0
    result["pct_below_median"] = pct_below

    lowest_window = min(obs)
    is_lowest = current_price <= lowest_window

    strong = (pct_below >= d["strong_pct_below_median"]) or \
             (is_lowest and result["is_new_low"])
    watch = pct_below >= d["watch_pct_below_median"]

    if strong:
        result["level"] = "strong"
        if pct_below >= d["strong_pct_below_median"]:
            result["reasons"].append(f"{pct_below*100:.0f}% below its median")
        if result["is_new_low"]:
            result["reasons"].append("new low since tracking began")
    elif watch:
        result["level"] = "watch"
        result["reasons"].append(f"{pct_below*100:.0f}% below its median")

    if insight_verdict == "low" and result["level"] == "none":
        result["level"] = "watch"
        result["reasons"].append("Google rates this fare 'low'")
    elif insight_verdict == "high" and result["level"] == "strong":
        result["level"] = "watch"
        result["reasons"].append("(Google rates it 'high' — verify)")

    return result


def summarize_run(assessed: list[dict]) -> dict:
    """Roll up a run's assessed fares for logging / email subject lines."""
    strong = [a for a in assessed if a["assessment"]["level"] == "strong"]
    watch = [a for a in assessed if a["assessment"]["level"] == "watch"]
    return {
        "n_strong": len(strong),
        "n_watch": len(watch),
        "strong": sorted(strong, key=lambda a: a["record"]["price"]),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
