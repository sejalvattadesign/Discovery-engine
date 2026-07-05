# Deployment Plan — Detour Discovery Engine

Two deployments: **Hugging Face Spaces** (Python FastAPI RAG backend) + **Vercel** (Next.js dashboard).
The frontend never talks to the backend from the browser — its own `/api/ask` route proxies
server-to-server, so there are no CORS issues and the backend URL stays private.

```
Browser ── Vercel (Next.js) ──/api/ask──▶ Hugging Face Space (FastAPI + Chroma + Groq)
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

## 1. Backend → Hugging Face Spaces (deploy this FIRST — the frontend needs its URL)

The backend is deployed using Docker in the Hugging Face Space repository.

1. Clone or set up the Hugging Face Space repo (`discovery`).
2. Copy the backend files (`api/`, `app/`, `data/`, `pipeline/`, etc.) and the `Dockerfile` into the space repository.
3. Commit and push the changes. Hugging Face will build the Docker container and start the FastAPI service.
4. Set the secret environment variables in the Hugging Face Space Settings:
   - `GROQ_API_KEY` = your **rotated** key
   - `ANTHROPIC_API_KEY` = (optional fallback)
5. Copy the Space URL, e.g. `https://sejalvatta-discovery.hf.space`.
6. **Smoke test:**
   ```bash
   curl https://sejalvatta-discovery.hf.space/health
   curl -X POST https://sejalvatta-discovery.hf.space/ask \
     -H "Content-Type: application/json" \
     -d '{"question":"Why do users distrust Discover Weekly?","k":4}'
   ```

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
