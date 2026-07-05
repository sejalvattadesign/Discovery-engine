# Deployment Plan — Detour Discovery Engine

Two deployments: **Render** (Python FastAPI RAG backend) + **Vercel** (Next.js dashboard).
The frontend never talks to the backend from the browser — its own `/api/ask` route proxies
server-to-server, so there are no CORS issues and the backend URL stays private.

```
Browser ── Vercel (Next.js) ──/api/ask──▶ Render (FastAPI + Chroma + Groq)
                 web/                          api/server.py → app/rag_core.py
```

---

## 0. Prerequisites (do once)

- [ ] **Rotate the Groq API key** — the old one was pasted in plaintext and is compromised.
- [ ] **`git init` at the repo root**, commit, and push to GitHub. Confirm `.gitignore` excludes
      `.env`, `.venv/`, `data/raw/`, `node_modules/`, `.next/` (already set).
- [ ] **Remove the nested `web/.git`** so the whole project is ONE repo:
      `rm -rf web/.git` before the root commit (otherwise Vercel/GitHub treat `web/` oddly).
- [ ] **Commit the vector index** so the backend has data at runtime:
      make sure `data/chroma/` and `data/reviews.db` are committed (they are NOT gitignored).
      The backend only needs `data/chroma/` to answer; committing it avoids a rebuild on deploy.

---

## 1. Backend → Render (deploy this FIRST — the frontend needs its URL)

Config is already staged in **`render.yaml`** and **`requirements-api.txt`**.

1. Render → **New + → Blueprint** → connect the GitHub repo → it auto-reads `render.yaml`.
2. When prompted, set the secret env vars (they are `sync: false`, so not in git):
   - `GROQ_API_KEY` = your **rotated** key
   - `ANTHROPIC_API_KEY` = (optional fallback)
3. Deploy. Render will:
   - `pip install -r requirements-api.txt` (slim serve deps only)
   - pre-cache the MiniLM embedding model (so the first question is fast)
   - start `uvicorn api.server:app --host 0.0.0.0 --port $PORT`
   - health-check `GET /health` → `{"ok": true}`
4. Copy the service URL, e.g. `https://detour-rag-backend.onrender.com`.
5. **Smoke test:**
   ```bash
   curl https://detour-rag-backend.onrender.com/health
   curl -X POST https://detour-rag-backend.onrender.com/ask \
     -H "Content-Type: application/json" \
     -d '{"question":"Why do users distrust Discover Weekly?","k":4}'
   ```

**Two caveats on Render free tier:**
- **Spin-down:** free services sleep after ~15 min idle → first request cold-starts (~30–60s).
  For a graded link, either upgrade to a paid instance, add a cron ping to keep it warm, or rely on
  the fact that the **6 preloaded chip answers work even if the backend is asleep** (only free-typed
  questions hit Render).
- **Memory (512 MB):** torch + sentence-transformers + Chroma can run tight. If it OOMs, bump to a
  paid instance, or move the backend to **Hugging Face Spaces** (16 GB free CPU, more ML-friendly) —
  same `uvicorn` start command.

---

## 2. Frontend → Vercel

1. Vercel → **Add New → Project** → import the same GitHub repo.
2. **Root Directory: `web`** (important — the Next.js app lives in `web/`, not repo root).
   Framework preset auto-detects **Next.js**; leave build/output defaults.
3. **Environment Variable:**
   - `BACKEND_URL` = `https://detour-rag-backend.onrender.com` (your Render URL, no trailing slash)
   *(Used by `web/app/api/ask/route.ts`; it already reads `process.env.BACKEND_URL`.)*
4. Deploy → you get a public URL like `https://detour-xyz.vercel.app`.
5. **Verify in an incognito window** (grader must reach it un-gated):
   - Insights view loads charts (static, from `web/lib/data.ts`).
   - Click a preloaded chip → instant cited answer.
   - Type a free question → it round-trips through Render and returns a cited answer.
   - Ask "what's the capital of France?" → guardrail refuses.

---

## 3. Post-deploy hardening (optional)

- **Tighten CORS:** in `api/server.py`, change `allow_origins=["*"]` to your exact Vercel domain.
  (Not strictly required, since traffic is server-to-server, but good hygiene.)
- **Keep-warm ping:** a cron (or the existing GitHub Action) hitting `/health` every ~10 min avoids
  cold starts on the free tier.
- **Put the live link on the deck** (S2 "LIVE LINK" TODO and S9 dashboard reference).

---

## What's already wired for you

| Concern | Status |
|---|---|
| Frontend → backend via env var | ✅ `BACKEND_URL` in `web/app/api/ask/route.ts` |
| Health check endpoint | ✅ `GET /health` |
| CORS | ✅ open (tighten later) |
| Backend blueprint | ✅ `render.yaml` |
| Slim backend deps | ✅ `requirements-api.txt` (+ MiniLM pre-cache) |
| Request timeout for slow LLM | ✅ 60s in the proxy route |
| Backend-down resilience | ✅ 6 preloaded answers work offline |
