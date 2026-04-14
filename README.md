# ≡ƒ¢í∩╕Å student_copilot ΓÇö The Sovereign AI Tutor

**"Engineering is applied philosophy."**

student_copilot is a privacy-first, dynamically adaptive AI education platform built on first-principles. Instead of forcing students into rigid, symmetrical learning paths, student_copilot adapts longitudinally to *how* a student learns, while strictly gating "ground truth" knowledge through an impenetrable Role-Based Access Control (RBAC) vector architecture.

It is designed for real human asymmetry: minimizing attack surfaces, ensuring graceful degradation, eliminating non-critical bloat, and relentlessly curating the signal-to-noise ratio in modern AI education.

---

## ≡ƒÅ¢ Architecture Overview

At its core, student_copilot is divided into four cleanly decoupled service pillars. It operates on a **FastAPI** Python Backend and a **React/Vite** Frontend. Memory is statefully managed via **Redis** (for fast, ephemeral chat and long-term learning profiles) and **Pinecone** (for strict, embedded vector knowledge).

```text
ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ        ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ
Γöé  FRONTEND (React/Vite)  Γöé        Γöé  BACKEND (FastAPI - Python)  Γöé
Γöé                         Γöé        Γöé                              Γöé
Γöé  - General Tutor        Γöé ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓû║Γöé  - Auth (JWT / PBKDF2 HMAC)  Γöé
Γöé  - Notebook Oracle      Γöé        Γöé  - Vector RAG Engine         Γöé
Γöé  - Teacher Portal       Γöé        Γöé  - Longitudinal Profiler     Γöé
Γöé  - Revision Hub         Γöé        Γöé  - Socratic Exam Generator   Γöé
ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ        ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ
                                                  Γöé
                                   ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓö┤ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ
                                   Γû╝                              Γû╝
                         ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ        ΓöîΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÉ
                         Γöé   REDIS (Memory)  Γöé        Γöé PINECONE (Vectors)Γöé
                         Γöé - Global Profiles Γöé        Γöé - Semantic Embeds Γöé
                         Γöé - JWT Validation  Γöé        Γöé - RBAC Metadata   Γöé
                         Γöé - Parent Chunks   Γöé        Γöé - Child Chunks    Γöé
                         ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ        ΓööΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÿ
```

---

## ≡ƒº⌐ The Four Pillars

### 1. General Tutor (GT)
**Purpose**: Longitudinal, adaptive chat that learns *how* the student learns.
- **Workflow**: A student engages in free-form conversation. On session closure, an unseen instance of the LLM audits the entire transcript. It identifies newly observed learning modalities (e.g., "Student responds better to visual analogies than raw math") and permanently updates their **Global Learning Method** in Redis. Future sessions inherit this pedagogy.
- *Philosophy: The system must evolve alongside the student.*

### 2. Notebook Oracle (NB) & Teacher Portal (TP)
**Purpose**: Secure curation and anti-hallucination true ground retrieval.
- **Workflow (Two-Tier Chunking)**: When a teacher uploads a syllabus document (TP) or a student uploads their notes (NB), the system utilizes **PyMuPDF4LLM** to natively extract complex visual structures (Markup tables, headers, metadata). It breaks documents into massive 2500-char **Parent Chunks** stored securely in Redis, and laser-focused 400-char **Child Chunks** embedded in Pinecone. 
- During retrieval, Pinecone finds the exact child match, and the backend dynamically hydrates the LLM context window using the entire Parent chunk. 
- *Philosophy: Zero invention. In violent disagreement with LLM hallucinations. Maximum semantic context delivery.*

### 3. Revision Hub (RP)
**Purpose**: Socratic testing loop over the ground truth.
- **Workflow**: A student requests a personalized exam. The backend queries Pinecone for the teacher's globally uploaded vectors via strict Multi-Tenant metadata tagging (`class_id` & `subject`). Upon grading, the LLM uses the student's *Global Learning Method* to pedantically explain any failed concepts in a tone optimized for them.
- *Philosophy: A closed loop. Exam ΓåÆ Grade ΓåÆ Explain ΓåÆ Grow.*

---

## ≡ƒ¢á∩╕Å Tech Stack & Dependencies

- **Backend (Python 3.11+)**: FastAPI, `langchain`, `redis`, `pymupdf4llm`, `slowapi` 
- **AI Core**: Google Gemini (`gemini-2.5-flash`) / OpenAI (`gpt-4o`)
- **Memory/Storage**: 
  - **Redis**: Centralized single pool connection for Profiles, Rate Limits, and Large Parent Chunks.
  - **Pinecone**: Dense vector RAG.
- **Frontend**: React 18, Vite, TypeScript, Vanilla CSS components.

---

## ≡ƒÜÇ Setup & Launch Sequence

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- An active Redis instance running locally (port 6379) or via cloud URL
- Pinecone DB account + Index created (dimension size: 768 for Gemini, 1536 for OpenAI `text-embedding-3-small`)

### 2. Configure Environment
Copy the example file and fill in your keys.

```bash
cd general_tutor
cp ../.env.example .env
```
Ensure `REDIS_URL`, `PINECONE_API_KEY`, and at least one LLM Provider (`GEMINI_API_KEY` or `OPENAI_API_KEY`) are present.

### 3. System Startup Commands

**Terminal 1: Start the Backend (FastAPI)**
```bash
# Enter the backend directory
cd general_tutor

# Create standard virtualenv
python -m venv venv
# Windows:
venv\Scripts\activate
# MacOS/Linux:
# source venv/bin/activate

# Install strict dependencies
pip install -r requirements.txt

# Run the single Sovereign API Server
fastapi dev main.py
```
> The API will securely bind to `http://localhost:8000`. You can test endpoints via the Swagger UI at `http://localhost:8000/docs`.

**Terminal 2: Start the Frontend (React/Vite)**
```bash
# In a new terminal, enter the frontend directory
cd frontend

# Install exact node modules
npm install

# Start the Vite hyper-fast dev server
npm run dev
```
> The beautiful dark-mode UI will bind to `http://localhost:5173`. Open this URL in your browser to begin testing.

---

## ≡ƒ¢í∩╕Å Production Hardening (Hostile-Ready)

To survive real human chaos, student_copilot ships with enforced constraints:

1. **Cryptographic Asymmetry**: Endpoints are locked behind `HTTPBearer` PyJWT validation. Passwords are never raw-hashed; they are generated using rigorous `pbkdf2_hmac` military-grade encryption bound to random 16-byte salts.
2. **Aggressive Rate Limiting**: `slowapi` restricts expensive AI actions out of the box (e.g., 20 chats/min, 5 uploads/min) utilizing a unified Redis pool to prevent TCP exhaustion.
3. **Pydantic Sanitization**: Custom `validate_safe_string` Regex sanitizes every payload key (`subject`, `class_id`, etc.) mitigating dangerous traversal/injection attacks before hydration.
4. **Data Ephemerality (TTL)**: Heavy Parent Chunks and Session arrays auto-expire to cap unbounded server memory growth. Global learning profiles persist statically until commanded otherwise.

**Sovereign Architect offline. Everything is up to date.**
