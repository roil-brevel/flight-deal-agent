"""Email alerts for strong deals — sent via SMTP (e.g. Gmail app password).

Optional: if the SMTP_* env vars aren't set, the agent skips email.
Secrets: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO.
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


def _cfg() -> dict | None:
    need = ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "ALERT_TO")
    if not all(os.environ.get(k) for k in need):
        return None
    return {
        "host": os.environ["SMTP_HOST"],
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ["SMTP_USER"],
        "pw": os.environ["SMTP_PASS"],
        "to": os.environ["ALERT_TO"],
    }


def _fmt_deal(a: dict) -> str:
    r, asr = a["record"], a["assessment"]
    cur = r["currency"]
    line = (f"  • {r['origin']}→{r['destination']}  {cur} {r['price']:.0f}"
            f"  ({r.get('airline') or '?'}, {r.get('transfers', '?')} stops)")
    if r.get("depart_date"):
        line += f"\n    {r['depart_date']}"
        if r.get("return_date"):
            line += f" → {r['return_date']}"
    if asr.get("reasons"):
        line += f"\n    why: {', '.join(asr['reasons'])}"
    if r.get("deep_link"):
        line += f"\n    {r['deep_link']}"
    return line


def send_strong_deals(summary: dict, dashboard_url: str | None = None) -> bool:
    cfg = _cfg()
    strong = summary.get("strong", [])
    if not cfg or not strong:
        return False

    subject = f"✈️ {len(strong)} strong flight deal" + \
              ("s" if len(strong) != 1 else "") + " found"
    body = ["Your flight agent found deals notably below their recent norm:\n"]
    body += [_fmt_deal(a) for a in strong]
    if dashboard_url:
        body.append(f"\nFull dashboard: {dashboard_url}")
    body.append("\n(Travelpayouts prices are per-adult indicative; SerpAPI "
                "prices are your family total. Verify before booking.)")

    msg = MIMEText("\n".join(body))
    msg["Subject"] = subject
    msg["From"] = cfg["user"]
    msg["To"] = cfg["to"]

    with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
        s.starttls()
        s.login(cfg["user"], cfg["pw"])
        s.sendmail(cfg["user"], [cfg["to"]], msg.as_string())
    return True
