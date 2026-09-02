# Deployment — Hey-Nova.ai (Student Copilot)

Deploy as **compute-only** for SMS integration.

**GitHub repo:** `Algorythyme/student_copilot` · **Verified path:** [Deploy student copilot compute (detailed)](../../docs/DEPLOY-STUDENT-COPILOT-COMPUTE.md)

---

## Railway (Docker) — quick checklist

1. Connect repo **`student_copilot`**, branch **`integ`**
2. Builder: **`Dockerfile`** (`railway.toml`)
3. **Custom Start Command:** leave **empty** or `python main.py` only — **never** `--port 8003`
4. **Do not** set `PORT=8003` — Railway injects `PORT`; `main.py` reads it
5. Set compute env vars (below)
6. Deploy → `GET /health`
7. Set backend `STUDENT_COPILOT_COMPUTE_URL` → redeploy backend

`GET /health` reports `web_search` as `configured` or `disabled`; it never exposes `TAVILY_API_KEY`.

---

## Required env (compute)

```env
DEPLOY_MODE=compute
SERVE_WEB=false
REQUIRE_DATABASE=false
ENABLE_NEST_AUTH=true
ENABLE_SUPABASE_AUTH=false
ENABLE_STANDALONE_AUTH=false
AUTH_DISABLED=false
REQUIRE_WEB_SEARCH=true

NEST_JWT_PUBLIC_KEY_URL=https://<backend-public-url>/api/v1/auth/public-key
JWT_ISSUER=Pedagic School Management
JWT_AUDIENCE=school-users

LLM_PROVIDER=gemini
GEMINI_API_KEY=...
TAVILY_API_KEY=...

CORS_ALLOW_ORIGINS=https://<backend-public-url>
```

Do **not** set `JWT_PRIVATE_KEY`, `JWT_SECRET` (prod), `DATABASE_URL`, or manual `PORT=8003`.

---

## Optional env

```env
LLM_TIMEOUT_SECONDS=90
REDIS_URL=${{Redis.REDIS_URL}}
```

---

## Wire to backend

```env
STUDENT_COPILOT_COMPUTE_URL=https://<copilot-public-url>
```

---

## Local

```bash
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

See `.env.example` **PROFILE A — COMPUTE**.

---

## Notes

- Sessions and RAG live in **Nest Postgres**, not this service
- Frontend uses `/api/v1/student-copilot/*` via Nest JWT
- Supabase/Pinecone modes are legacy demo only

See [SMS integration contract](./sms-integration.md).
