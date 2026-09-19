# SMS ↔ Student Copilot Compute API Contract

This document describes how the Pedagic SMS Nest backend integrates with the **compute-only** Student Copilot deploy (`DEPLOY_MODE=compute`).

## Responsibilities

| System | Owns |
|--------|------|
| **SMS (Nest)** | Users, sessions, **all RAG** (pgvector on Prisma Postgres), approved-artifact ingest, persistence |
| **Copilot (compute)** | JWT verification, LLM inference, structured JSON responses (no DB writes) |

Copilot is **stateless**: every request must include full context in the body. SMS supplies **`context_chunks`** from approved, student-safe artifacts only. Source labels are generic; resolved titles remain private in SMS metadata.

## Authentication

All compute endpoints require:

```
Authorization: Bearer <Nest RS256 JWT>
```

Configure copilot with:

- `NEST_JWT_PUBLIC_KEY_URL` — fetches SMS public key, or
- `JWT_PUBLIC_KEY` — inline PEM

### JWT claims (logging / rate-limit keys only)

| Claim | Description |
|-------|-------------|
| `sub` | User ID |
| `role` | e.g. `STUDENT` |
| `schoolId` | School tenant |
| `email` | Optional display name |

Copilot does **not** look up users in Postgres in compute mode.

## Base URL

```
POST https://<copilot-compute-host>/api/v1/compute/<action>
```

## Endpoints

### POST `/api/v1/compute/chat`

One chat turn with full history and RAG context from SMS.

**Request**

```json
{
  "message": "Explain photosynthesis",
  "user_profile": {
    "full_name": "Victor",
    "class_id": "SSS 1",
    "subjects": "Biology",
    "learning_method": "visual analogies"
  },
  "message_history": [
    { "role": "user", "content": "What is a cell?" },
    { "role": "assistant", "content": "A cell is..." }
  ],
  "context_chunks": [
    { "source": "Study material 1", "content": "Photosynthesis converts light..." }
  ]
}
```

`file_summaries` is **optional and unused** in the SMS integration path — Nest does not send upload-derived summaries for KB.

**Response**

```json
{
  "reply": "Photosynthesis is the process...",
  "learning_method_suggestion": null,
  "search_used": true,
  "search_failed": false
}
```

### POST `/api/v1/compute/revision/generate`

Generate an exam from SMS-retrieved context.

**Request**

```json
{
  "subject": "Biology",
  "class_id": "SSS 1",
  "topics": "Photosynthesis",
  "mcq_count": 5,
  "theory_count": 2,
  "context_chunks": [
    { "source": "Study material 1", "content": "..." }
  ],
  "user_profile": {
    "learning_method": "visual analogies"
  }
}
```

**Response**

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "mcq",
      "text": "...",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "B"
    }
  ]
}
```

### POST `/api/v1/compute/practice/generate`

MCQ-only practice batch from SMS-retrieved **curriculum** context. One LLM call returns 20 MCQs. Token-cheap: no evaluate, no tools, no theory.

`context_chunks` is required and must be non-empty. Fail closed if SMS has no indexed curriculum for the topic.

`user_profile` may be attached for parity (use `learning_method` only). Copilot does **not** interpolate `full_name` into the prompt.

**Request**

```json
{
  "subject": "Mathematics",
  "class_id": "SSS1",
  "topics": "Quadratic Equations",
  "week": 5,
  "term": "First Term",
  "country": "Nigeria",
  "difficulty": 0.3,
  "mcq_count": 20,
  "theory_count": 0,
  "context_chunks": [
    { "source": "Curriculum 1", "content": "..." }
  ],
  "user_profile": {
    "full_name": "Ada Lovelace",
    "class_id": "SSS1",
    "subjects": "Mathematics",
    "learning_method": "visual analogies",
    "country": "Nigeria"
  },
  "exclude_stems": ["optional previously seen stems"]
}
```

| Field | Notes |
|-------|--------|
| `difficulty` | Required, `0.1`–`1.0` (Bloom: recall → exam-hard) |
| `mcq_count` | Default `20`; response is exactly this many MCQs (one LLM call). SMS sits 10 and keeps the rest as unused leftovers |
| `theory_count` | Default `0`; ignored — output is MCQ-only |
| `country` | One-line exam-body hint (Nigeria → WAEC/NECO). Same map idea as curriculum-builder `COUNTRY_EXAM_BODY_MAP` |
| `week` | Optional integer interpolated into the prompt |
| `term` | Optional string (`"First Term"`) or integer; interpolated into the prompt |
| `exclude_stems` | Optional previously seen stems; honored if present (capped) |

**Response**

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "mcq",
      "text": "...",
      "options": ["A", "B", "C", "D"],
      "correct_answer": "B"
    }
  ]
}
```

Scoring stays in SMS. Do not call `/revision/evaluate` for practice marks.

### POST `/api/v1/compute/revision/evaluate`

Grade student answers against ground-truth context.

**Request**

```json
{
  "subject": "Biology",
  "class_id": "SSS 1",
  "questions": [ { "id": "q1", "type": "mcq", "text": "...", "correct_answer": "B" } ],
  "answers": { "q1": "A" },
  "context_chunks": [ { "source": "Study material 1", "content": "..." } ],
  "user_profile": { "learning_method": "visual analogies" }
}
```

**Response**

```json
{
  "feedback": "Question q1: ...",
  "status": "evaluated"
}
```

### POST `/api/v1/compute/summarize`

Summarize extracted document text (SMS stores the result).

**Request**

```json
{
  "text": "Full extracted document text...",
  "filename": "notes.pdf"
}
```

**Response**

```json
{
  "summary": "Concise summary..."
}
```

### POST `/api/v1/compute/evaluate-session`

Optional end-of-session learning method analysis.

**Request**

```json
{
  "user_profile": { "full_name": "Victor", "class_id": "SSS 1" },
  "message_history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "current_learning_method": "visual analogies"
}
```

**Response**

```json
{
  "learning_method": "visual analogies with step-by-step diagrams",
  "status": "updated"
}
```

## Nest integration flow (pseudo-code)

```typescript
const history = await smsDb.getStudentCopilotMessages(sessionId);
const chunks = await smsEmbeddings.retrieve({
  schoolId, classId, subjectId, query: message,
});
const { reply } = await copilot.post('/api/v1/compute/chat', {
  message,
  message_history: history,
  context_chunks: chunks,
  user_profile: await smsDb.getStudentProfile(userId), // personalization only
});
await smsDb.saveMessage(sessionId, 'assistant', reply);
```

## Idempotency

SMS may retry failed requests. Copilot compute endpoints have **no side effects** — safe to replay.

## Health check

```
GET /health
→ { "status": "ok", "mode": "compute", "web_search": "configured" }
```

No Postgres or Pinecone ping in compute mode.

## Disabled in compute deploy

These routes return **404** when `DEPLOY_MODE=compute`:

- `/auth/*`, `/users/me`
- `/conversations/*`, `/chat`, `/upload`
- `/notebook/*`, `/teacher/auto-ingest`
- Legacy `/revision/generate`, `/revision/evaluate`

Use the `/api/v1/compute/*` variants instead.
