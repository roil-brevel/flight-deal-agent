# ✈️ Flight Deal Agent

A personal, always-on flight-deal hunter. It polls flight prices on a
schedule, builds its own price history, flags fares that are notably below
their recent norm, and shows everything on a simple web dashboard with a
chat box. Runs for free on GitHub Actions.

Built for: **hub TLV**, 2 adults + 1 lap infant, prices in **USD**.

- **Goal 1 — Anywhere cheap, late August:** cheapest destinations from TLV.
- **Goal 2 — Bali (DPS), Dec 8–15 departure, 14–21 nights.**

---

## How it works

```
GitHub Actions (cron, 2×/day)
        │
        ▼
   collector.py ── Travelpayouts (free, broad radar, per-adult prices)
        │       └─ SerpAPI/Google Flights (live, family total, quota-limited)
        ▼
   prices.db (append-only SQLite = your growing price history)
        │
        ├─► deal detection (below-median / new-low)  ──► email on strong deals
        └─► dashboard/data.json  ──►  dashboard/index.html (GitHub Pages)
```

**Two sources, on purpose.** Travelpayouts is a free, cached, per-adult
"radar" that spots where prices are good and powers the *fly-anywhere*
discovery. SerpAPI/Google Flights is a live check that returns the true
**family total** for your exact passengers — used sparingly (250 free
searches/month) to confirm the fares worth acting on. Travelpayouts hunts;
SerpAPI confirms.

---

## Setup (~15 min)

### 1. Create the repo
Create a new GitHub repo and upload this folder's contents.

### 2. Add your keys as repository **Secrets**
Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add:

| Secret | Value |
|---|---|
| `TRAVELPAYOUTS_TOKEN` | your Travelpayouts API token |
| `SERPAPI_KEY` | your SerpAPI key |

Optional, for email alerts (Gmail example):

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASS` | a Gmail **App Password** (not your login password) |
| `ALERT_TO` | where deal emails go |
| `DASHBOARD_URL` | your Pages URL (see step 4) |

> 🔐 **Rotate the keys you pasted in chat.** Since they were shared in a
> conversation, regenerate fresh ones in the Travelpayouts and SerpAPI
> dashboards and store only the new ones as Secrets.

### 3. Turn on the schedule
The workflow (`.github/workflows/collect.yml`) runs twice daily and can also
be triggered manually: repo → **Actions → collect-flight-deals → Run workflow**.
Run it once now to seed data.

### 4. Publish the dashboard (GitHub Pages)
Repo → **Settings → Pages** → Source: *Deploy from a branch* → branch `main`,
folder `/dashboard`. Your dashboard appears at
`https://<you>.github.io/<repo>/`. Put that URL in the `DASHBOARD_URL` secret.

---

## Run it locally (optional)

```bash
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
set -a; source .env; set +a
python -m src.collector   # one run
# open dashboard/index.html (serve the folder so fetch() works):
python -m http.server -d dashboard 8000   # → http://localhost:8000
```

---

## Tuning

Everything lives in **`config.yaml`** — no code changes needed:

- **Routes / goals:** add more `discover` or `route` goals.
- **Dates & trip length:** `depart_from`, `depart_to`, `min_nights`, `max_nights`.
- **Passengers:** `adults`, `children`, `infants_on_lap`.
- **What counts as a deal:** `strong_pct_below_median`, `strong_is_lowest_in_days`,
  `watch_pct_below_median`, `min_observations`.
- **SerpAPI spend:** `verify_top_n` (discovery) and `verify_live` (routes)
  control how many live checks each run makes.

---

## Notes & limits

- **Prices are indicative, not bookings.** Travelpayouts data is cached from
  recent real searches (per adult); SerpAPI gives a live family total but can
  still shift by the time you book. Always confirm on the airline/OTA.
- **December is thin now.** Six months out, the free cache barely covers
  Bali, so the agent leans on SerpAPI live for it and the picture sharpens as
  the date nears.
- **The chat box** answers from the latest `data.json` (deals, August options,
  a specific destination). It's a local query engine — no extra API key. To
  make it a true LLM agent later, point it at an API in `index.html`.
- **Deal detection gets smarter with time** — it needs a few observations per
  route (`min_observations`) before it will judge a fare.
