"""Render the dashboard's data file (dashboard/data.json)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import store

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data.json"


def _ddmm(iso: str | None) -> str:
    if not iso:
        return ""
    d = datetime.strptime(iso[:10], "%Y-%m-%d")
    return d.strftime("%d%m")


def aviasales_link(origin, dest, depart, ret, adults=1) -> str:
    """Build an Aviasales search URL (add ?marker=<id> for affiliate credit)."""
    seg = f"{origin}{_ddmm(depart)}{dest}"
    if ret:
        seg += _ddmm(ret)
    return f"https://www.aviasales.com/search/{seg}{adults}"


def _sparkline(conn, rec, days=90) -> list[dict]:
    hist = store.history_for_route(
        conn, rec["goal_id"], rec["origin"], rec["destination"],
        rec["source"], days=days)
    return [{"t": h["observed_at"][:10], "p": h["price"]} for h in hist]


def build(conn, cfg: dict, summary: dict) -> Path:
    adults = cfg["passengers"].get("adults", 1)
    goals_out = []
    for goal in cfg["goals"]:
        gid = goal["id"]
        latest = store.latest_per_route(conn, gid)
        routes = []
        for rec in latest:
            spark = _sparkline(conn, rec)
            prices = [s["p"] for s in spark]
            routes.append({
                "origin": rec["origin"],
                "destination": rec["destination"],
                "source": rec["source"],
                "basis": rec["basis"],
                "price": rec["price"],
                "currency": rec["currency"],
                "airline": rec["airline"],
                "transfers": rec["transfers"],
                "depart_date": rec["depart_date"],
                "return_date": rec["return_date"],
                "lowest_seen": min(prices) if prices else rec["price"],
                "median": (sorted(prices)[len(prices) // 2] if prices else None),
                "n_obs": len(prices),
                "sparkline": spark,
                "link": rec.get("deep_link") or aviasales_link(
                    rec["origin"], rec["destination"],
                    rec["depart_date"], rec["return_date"], adults),
            })
        goals_out.append({
            "id": gid,
            "label": goal["label"],
            "type": goal["type"],
            "routes": routes,
        })

    deals_now = []
    for a in summary.get("strong", []):
        r = a["record"]
        deals_now.append({
            "origin": r["origin"], "destination": r["destination"],
            "price": r["price"], "currency": r["currency"],
            "basis": r["basis"], "airline": r.get("airline"),
            "transfers": r.get("transfers"),
            "depart_date": r.get("depart_date"),
            "return_date": r.get("return_date"),
            "reasons": a["assessment"].get("reasons", []),
            "link": r.get("deep_link") or aviasales_link(
                r["origin"], r["destination"],
                r.get("depart_date"), r.get("return_date"), adults),
        })

    payload = {
        "generated_at": summary.get("generated_at"),
        "currency": cfg["currency"],
        "passengers": cfg["passengers"],
        "n_strong": summary.get("n_strong", 0),
        "n_watch": summary.get("n_watch", 0),
        "deals_now": deals_now,
        "goals": goals_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Dashboard data → {OUT}")
    return OUT
