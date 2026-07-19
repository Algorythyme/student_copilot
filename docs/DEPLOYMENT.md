# Deployment — Hey-Nova.ai (Student Copilot)

Deploy as **compute-only** for SMS integration.

## Master documentation

- [Deploy student copilot compute (detailed)](../../docs/DEPLOY-STUDENT-COPILOT-COMPUTE.md)
- [SMS integration contract](./sms-integration.md)

## Railway (Docker)

1. Root directory: `Hey-Nova.ai`
2. Dockerfile: `Dockerfile` (set `PORT=8003` or override start command)
3. Health: `/health`

### Required env (compute)

```env
DEPLOY_MODE=compute
SERVE_WEB=false
REQUIRE_DATABASE=false
ENABLE_NEST_AUTH=true
ENABLE_SUPABASE_AUTH=false
ENABLE_STANDALONE_AUTH=false
NEST_JWT_PUBLIC_KEY_URL=https://<backend>/api/v1/auth/public-key
GEMINI_API_KEY=...
LLM_PROVIDER=gemini
```

### Optional env

```env
# Per-LLM-call timeout in seconds (default 90)
LLM_TIMEOUT_SECONDS=90
# Redis-backed rate limiting (recommended in prod; in-memory fallback if unset)
REDIS_URL=...
```

4. Copy public URL to backend `STUDENT_COPILOT_COMPUTE_URL`

## Local

```bash
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

## Notes

- Sessions and RAG live in **Nest Postgres**, not this service
- Frontend uses `/api/v1/student-copilot/*` via Nest JWT
- Standalone Supabase/Pinecone modes are for legacy demo only
