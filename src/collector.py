"""Collector — one run of the flight deal agent.

Run locally with:  python -m src.collector
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import deals, notify, store
from .build_dashboard import build as build_dashboard
from .sources import serpapi_flights as sa
from .sources import travelpayouts as tp

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yaml"


def load_config() -> dict:
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for goal in cfg.get("goals", []):
        for k in ("depart_from", "depart_to", "destination", "origin"):
            if k in goal and not isinstance(goal[k], str):
                goal[k] = goal[k].isoformat()
    return cfg


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _assess_record(conn, cfg, rec, insight_verdict=None) -> dict:
    hist = store.history_for_route(
        conn, rec["goal_id"], rec["origin"], rec["destination"],
        rec["source"], days=90)
    prices = [h["price"] for h in hist]
    assessment = deals.assess(rec["price"], prices, cfg, insight_verdict)
    return {"record": rec, "assessment": assessment}


def run() -> dict:
    cfg = load_config()
    currency = cfg["currency"]
    pax = cfg["passengers"]
    observed_at = _now()
    serpapi_calls = 0
    serp_enabled = cfg["sources"]["serpapi"]["enabled"] and \
        bool(os.environ.get("SERPAPI_KEY"))
    tp_enabled = cfg["sources"]["travelpayouts"]["enabled"] and \
        bool(os.environ.get("TRAVELPAYOUTS_TOKEN"))

    all_records: list[dict] = []
    assessed: list[dict] = []

    with store.connect() as conn:
        for goal in cfg["goals"]:
            gid = goal["id"]

            radar: list[dict] = []
            if tp_enabled:
                try:
                    if goal["type"] == "discover":
                        radar = tp.discover(
                            goal["origin"], currency,
                            goal["depart_from"], goal["depart_to"], gid,
                            limit=goal.get("max_results", 30))
                    else:
                        radar = tp.route(
                            goal["origin"], goal["destination"],
                            goal["depart_from"], goal["depart_to"],
                            currency, gid)
                except Exception as e:
                    print(f"[{gid}] travelpayouts error: {e}")

            for r in radar:
                r["observed_at"] = observed_at
            all_records += radar

            verify_targets: list[tuple[str, str]] = []
            if goal["type"] == "discover":
                top = [r for r in radar if r.get("in_window")][
                    : goal.get("verify_top_n", 0)]
                verify_targets = [(t["origin"], t["destination"]) for t in top]
            elif goal.get("verify_live"):
                verify_targets = [(goal["origin"], goal["destination"])]

            for origin, dest in verify_targets:
                if not serp_enabled:
                    break
                try:
                    res = sa.best_in_window(
                        origin, dest, goal["depart_from"], goal["depart_to"],
                        goal["min_nights"], goal["max_nights"], currency,
                        pax, gid, budget_calls=3)
                    serpapi_calls += res["calls"]
                    live = res["cheapest"]
                    if live:
                        live["observed_at"] = observed_at
                        all_records.append(live)
                        verdict = (res["insights"] or {}).get("verdict")
                        assessed.append(_assess_record(conn, cfg, live, verdict))
                except Exception as e:
                    print(f"[{gid}] serpapi error {origin}->{dest}: {e}")

            seen = set()
            for r in sorted(radar, key=lambda x: x["price"]):
                k = (r["origin"], r["destination"])
                if k in seen:
                    continue
                seen.add(k)
                assessed.append(_assess_record(conn, cfg, r))

        n = store.insert_observations(conn, all_records)
        print(f"Logged {n} observations. SerpAPI calls this run: {serpapi_calls}")

        summary = deals.summarize_run(assessed)
        build_dashboard(conn, cfg, summary)

    dash_url = os.environ.get("DASHBOARD_URL")
    sent = notify.send_strong_deals(summary, dash_url)
    print(f"Strong: {summary['n_strong']}, Watch: {summary['n_watch']}, "
          f"email_sent={sent}")
    return summary


def main():
    run()


if __name__ == "__main__":
    main()
