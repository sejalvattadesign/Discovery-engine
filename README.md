# Spotify Music-Discovery Research Engine

A reproducible pipeline that mines real Spotify user feedback, uses an LLM + RAG to diagnose
*why music discovery fails*, and exposes a **live, queryable dashboard** you can ask questions of —
every answer cited back to real reviews.

This is the **discovery / research phase**: collect the feedback, let the data surface the problems,
and make the evidence explorable. The analysis converges on one segment (**Discovery Skeptics**) and
one root cause (**no voice + no trust**).

- **Live dashboard (Ask + Insights):** _<paste Vercel URL>_
- **RAG backend API:** _<paste Render URL>_

---

## What it does

```
COLLECT            STORE            FILTER              CODE                     SERVE
Play Store ─┐
App Store  ─┤─▶  SQLite DB  ─▶  keyword +      ─▶  LLM: theme · sentiment  ─▶  Chroma embeddings ─▶  RAG Q&A
Forum      ─┤   (reviews +      LLM relevance      · segment · job-to-be-      (MiniLM, local)      + guardrails
Reddit     ─┘    coded_reviews)  (yes/no)          done, in batches           (Next.js + FastAPI)
```

**Scale:** ~8,900 raw items → **6,319** deduped reviews → **1,786** discovery-relevant, each coded
across **4 independent sources** (Play Store · App Store · Community Forum · Reddit).

---

## Repo structure

| Path | What |
|---|---|
| `scrape/` | Source collectors (play_store, app_store, reddit via PullPush, forum) |
| `pipeline/` | load_to_db · filter_relevant · classify · resegment · classify_jtbd · aggregate · export_data · theme_details |
| `app/` | `rag_core.py` (shared RAG + two-tier guardrails) · `build_index.py` · `streamlit_app.py` |
| `api/` | `server.py` — FastAPI wrapping the RAG for the Next.js UI |
| `web/` | Next.js "Discovery Lens" dashboard (Insights + Ask views) |
| `data/` | `reviews.db` (SQLite) · `chroma/` (vector index) · `raw/` (cached scrapes) · agg CSVs + charts |
| `.github/workflows/refresh.yml` | Weekly scheduled pipeline refresh |

> This repo is the **research engine** only. Written analysis, figures, and deck material live
> separately in the `Spoti Content/` folder.

---

## Quickstart (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys (see below)
```

`.env` needs:
```
GROQ_API_KEY=...              # primary LLM (OpenAI-compatible endpoint)
ANTHROPIC_API_KEY=...         # optional fallback
REDDIT_CLIENT_ID=...          # only if re-scraping Reddit
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=...
```

### Run the pipeline (data is cached — re-runs don't re-hit APIs)

```bash
# collect  → each writes one cached file to data/raw/
python scrape/play_store.py && python scrape/app_store.py && python scrape/reddit.py

# store → filter → code
python pipeline/load_to_db.py
python pipeline/filter_relevant.py
python pipeline/classify.py
python pipeline/resegment.py           # evidence-gated segment coding
python pipeline/classify_jtbd.py       # job-to-be-done coding

# aggregate → export dashboard data → drill-downs → vector index
python pipeline/aggregate.py
python pipeline/export_data.py         # writes web/lib/data.ts
python pipeline/theme_details.py       # writes web/lib/theme_details.ts
python app/build_index.py              # builds data/chroma/
```

### Run the app

```bash
# backend (RAG + guardrails)
uvicorn api.server:app --reload --port 8000

# frontend (in a second terminal)
cd web && npm install && npm run dev      # http://localhost:3000
```

Or the all-in-one Streamlit version: `streamlit run app/streamlit_app.py`.

---

## The queryable layer

Ask anything about discovery feedback; answers are retrieved from the review corpus and **cited**
to source + date. Guardrails (a retrieval scope gate + a grounded prompt) keep it on-topic — ask
"what's the capital of France?" and it refuses. Six brief questions are preloaded as example chips
and answer instantly even if the backend is asleep.

---

## Deployment

Two deployments — **Vercel** (Next.js frontend) + **Render** (FastAPI backend). Full step-by-step in
[`DEPLOYMENT.md`](DEPLOYMENT.md); config is staged in [`render.yaml`](render.yaml) and
[`requirements-api.txt`](requirements-api.txt).

---

## Data, ethics & limits

- Usernames are anonymized; we analyze **themes, not people** — no personal info stored or shown.
- Scrapers are throttled and every raw pull is cached, so we never re-hit an API unnecessarily.
- Segments are **formed** from reviews + survey and **sized** from Spotify's public data; review
  percentages are "share of discovery *feedback*," not "of users."
- Ratings exist only on store reviews (Reddit/Forum have none).

---

## Reproducing the weekly refresh

`.github/workflows/refresh.yml` re-runs the whole pipeline on a schedule (Mondays 06:00 UTC) or on
manual dispatch, then commits the updated `data/reviews.db`, `web/lib/data.ts`, and
`web/lib/theme_details.ts`. Requires the repo pushed to GitHub with the API keys set as Actions secrets.
