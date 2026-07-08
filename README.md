# Student_copilot

Student_copilot resolves the inefficiency of rigid, one-size-fits-all education and the unreliability of hallucination-prone AI by dynamically adapting to individual learning styles. It delivers a scalable, privacy-first tutoring platform that strictly grounds its responses in verified curriculum data, ensuring students receive highly personalized and factually accurate instruction.

## Tech Stack

- **Backend Framework**: Python 3.11+, FastAPI, Pydantic
- **Frontend Framework**: React 18, Vite, TypeScript
- **AI Models & Frameworks**: Google Gemini (`gemini-2.5-flash`), OpenAI (`gpt-4o`), LangChain
- **Databases & Vector Storage**: Pinecone (Vector RAG), Redis (Memory, Caching, Rate Limiting), Supabase
- **Document Processing**: PyMuPDF4LLM
- **Security & Authentication**: PyJWT (HTTPBearer), PBKDF2 HMAC, `slowapi`
- **Infrastructure & Deployment**: Docker, Railway

## System Architecture

Student_copilot is designed around four decoupled service pillars, ensuring robust performance and graceful degradation:

1. **General Tutor (GT)**: A longitudinal adaptive chat interface. It continually assesses session transcripts to identify and record the student's optimal learning modalities (e.g., visual analogies vs. mathematical proofs) into a Global Learning Profile stored in Redis.
2. **Notebook Oracle (NB) & Teacher Portal (TP)**: The ingestion pipeline for ground-truth knowledge. Utilizing a Two-Tier Chunking strategy, complex documents are parsed by PyMuPDF4LLM. Large "Parent Chunks" (2500-char) are stored in Redis, while dense "Child Chunks" (400-char) are embedded in Pinecone. This strictly eliminates AI hallucinations during information retrieval.
3. **Revision Hub (RP)**: A Socratic testing engine. It generates personalized exams based on strict multi-tenant metadata tagging (`class_id`, `subject`). Grading incorporates the student's global learning profile to provide targeted, pedantic explanations for failed concepts.
4. **Security Layer**: Cryptographic asymmetry with `HTTPBearer` PyJWT validation, aggressive rate limiting via `slowapi`, and custom payload sanitization to mitigate injection attacks.

## Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+ and npm
- **Redis**: An active instance running locally (port 6379) or via a cloud provider.
- **Pinecone**: Database account and initialized index (Dimension size: 768 for Gemini, 1536 for OpenAI `text-embedding-3-small`).
- **Supabase**: Account for relational database storage.

## Local Setup & Installation

### 1. Configure Environment

Copy the example environment configuration and populate it with your specific API keys.

```bash
cp .env.example .env
```

Ensure the following variables are defined in your `.env` file:
- `REDIS_URL`
- `PINECONE_API_KEY`
- At least one AI Provider (`GEMINI_API_KEY` or `OPENAI_API_KEY`)

### 2. Backend Startup (FastAPI)

From the root directory, configure the Python environment and start the server:

```bash
# Create and activate a virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# MacOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Launch the API server
fastapi dev main.py
```
*The API will bind to `http://localhost:8000`. Access the Swagger UI for endpoint testing at `http://localhost:8000/docs`.*

### 3. Frontend Startup (React/Vite)

In a new terminal instance, navigate to the frontend directory and start the UI:

```bash
# Navigate to the frontend directory
cd frontend

# Install exact node modules
npm install

# Start the Vite development server
npm run dev
```
*The UI will bind to `http://localhost:5173`. Open this URL in your browser to interact with the application.*

## Usage Examples

- **Teacher Portal Upload**: Navigate to the Teacher Portal in the UI to upload syllabus PDFs. The system will automatically parse, chunk, and embed the document across Redis and Pinecone.
- **Student Chat Session**: Start a conversation in the General Tutor interface. Ask questions regarding the uploaded material. The system will retrieve the exact Parent Chunk to answer your query without hallucinating outside context.
- **Revision Generation**: Request an exam from the Revision Hub. Complete the exam and review the personalized, Socratic feedback generated based on your unique learning profile.
