# SMS ↔ Student Copilot Compute API Contract

This document describes how the Pedagic SMS Nest backend integrates with the **compute-only** Student Copilot deploy (`DEPLOY_MODE=compute`).

## Responsibilities

| System | Owns |
|--------|------|
| **SMS** | Users, conversations, messages, file summaries, vector ingest & retrieval, persistence |
| **Copilot (compute)** | JWT verification, LLM inference, structured JSON responses (no DB writes) |

Copilot is **stateless**: every request must include full context. SMS is the system of record.

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
  "file_summaries": [
    { "filename": "notes.pdf", "summary": "Chapter 3 covers plant biology..." }
  ],
  "context_chunks": [
    { "source": "Biology Syllabus", "content": "Photosynthesis converts light..." }
  ]
}
```

**Response**

```json
{
  "reply": "Photosynthesis is the process...",
  "learning_method_suggestion": null
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
    { "source": "Teacher Notes", "content": "..." }
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

### POST `/api/v1/compute/revision/evaluate`

Grade student answers against ground-truth context.

**Request**

```json
{
  "subject": "Biology",
  "class_id": "SSS 1",
  "questions": [ { "id": "q1", "type": "mcq", "text": "...", "correct_answer": "B" } ],
  "answers": { "q1": "A" },
  "context_chunks": [ { "source": "Teacher Notes", "content": "..." } ],
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
const history = await smsDb.getMessages(conversationId);
const chunks = await smsVectorSearch.query({
  userId, schoolId, subject, query: message,
});
const { reply } = await copilot.post('/api/v1/compute/chat', {
  message,
  message_history: history,
  context_chunks: chunks,
  file_summaries: await smsDb.getFileSummaries(conversationId),
  user_profile: await smsDb.getUserProfile(userId),
});
await smsDb.saveMessage(conversationId, 'assistant', reply);
```

## Idempotency

SMS may retry failed requests. Copilot compute endpoints have **no side effects** — safe to replay.

## Health check

```
GET /health
→ { "status": "ok", "mode": "compute" }
```

No Postgres or Pinecone ping in compute mode.

## Disabled in compute deploy

These routes return **404** when `DEPLOY_MODE=compute`:

- `/auth/*`, `/users/me`
- `/conversations/*`, `/chat`, `/upload`
- `/notebook/*`, `/teacher/auto-ingest`
- Legacy `/revision/generate`, `/revision/evaluate`

Use the `/api/v1/compute/*` variants instead.
