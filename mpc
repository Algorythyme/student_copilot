# Student Copilot — E2E Test Plan (Frontend)

> **Pre-requisites**: Backend running (`fastapi dev main.py`), Frontend running (`npm run dev`), Supabase + Upstash + Pinecone configured in `.env`, `parent_chunks` table created in Supabase.

---

## Phase 0: Startup Verification

| # | Action | Expected Result |
|---|---|---|
| 0.1 | Start backend: `fastapi dev main.py` | Console shows: LLM initialized, Redis connected, Pinecone index ready (auto-created if absent) |
| 0.2 | Start frontend: `cd frontend && npm run dev` | Vite dev server binds to `http://localhost:5173` |
| 0.3 | Open `http://localhost:5173` in browser | Auth screen renders ("Sovereign Login") |
| 0.4 | Open `http://localhost:8000/docs` in another tab | Swagger UI loads with all endpoint groups |
| 0.5 | Hit `http://localhost:8000/health` | Returns `{"status": "ok"}` — confirms Redis is alive |

---

## Phase 1: Authentication — Student Registration

| # | Action | Expected Result |
|---|---|---|
| 1.1 | On the Auth screen, click **"Register Here."** | Form expands to show registration fields |
| 1.2 | Ensure **"Student"** role toggle is selected (default) | Student button is highlighted |
| 1.3 | Fill in: Username=`test_student`, Password=`testpass123`, Full Name=`Test Student`, Age=`16`, Country=`Nigeria`, Class ID=`Grade_10`, Subjects=`Biology, Math` | All fields populated |
| 1.4 | Click **"Establish Context"** | Spinner → redirects to main app. No errors. |
| 1.5 | Check Supabase Dashboard → Table Editor → `users` | Row exists: username=`test_student`, role=`student`, all profile fields populated, `password_hash` is a `salt:hash` format |
| 1.6 | Check browser `localStorage` | `jwt_test_student` token exists, `current_user`=`test_student`, `current_role`=`student` |

---

## Phase 2: Authentication — Teacher Registration

| # | Action | Expected Result |
|---|---|---|
| 2.1 | Logout (click **"Exit"**) | Returns to Auth screen |
| 2.2 | Click **"Register Here."**, select **"Teacher"** role toggle | Teacher button highlighted. Class ID / Subjects fields disappear (student-only) |
| 2.3 | Fill in: Username=`test_teacher`, Password=`teacherpass1`, Full Name=`Professor Oak`, Age=`45`, Country=`UK` | All fields populated |
| 2.4 | Click **"Establish Context"** | Spinner → redirects. Should land on **Teacher Portal** view (Knowledge Curation Portal) |
| 2.5 | Check Supabase Dashboard → `users` table | Row exists: username=`test_teacher`, role=`teacher` |

---

## Phase 3: Authentication — Login Flow

| # | Action | Expected Result |
|---|---|---|
| 3.1 | Logout, return to Auth screen | "Sovereign Login" shown |
| 3.2 | Enter `test_student` / `testpass123`, click **"Authenticate"** | Redirects to student main app (Tutor view) |
| 3.3 | Verify **"Teacher Panel"** button is **NOT** visible in sidebar | Only "Exit" button shows (student role) |
| 3.4 | Logout, login as `test_teacher` / `teacherpass1` | Redirects to Teacher Portal |
| 3.5 | Verify **"Back to App"** and **"Logout"** buttons visible at top-right | Both present |

---

## Phase 4: Authentication — Negative Tests

| # | Action | Expected Result |
|---|---|---|
| 4.1 | Try login with `test_student` / `wrongpassword` | Error: "Invalid username or password." |
| 4.2 | Try registering `test_student` again (same username) | Error: "Username already exists." |
| 4.3 | Try registering with password `short` (< 8 chars) | Error: "Password must be at least 8 characters." |
| 4.4 | Try registering with empty username | Error: validation error |

---

## Phase 5: General Tutor — Chat

| # | Action | Expected Result |
|---|---|---|
| 5.1 | Login as `test_student` | Main app loads, "Student OS" sidebar visible |
| 5.2 | Verify the app is in **"Tutor"** mode (default) | "Tutor" tab is highlighted in mode toggle |
| 5.3 | Check the chat area | "Student OS Online" placeholder text visible |
| 5.4 | Type `"Hello, can you help me study Biology?"` → Send | AI responds with a relevant greeting/offer |
| 5.5 | Type `"Explain photosynthesis simply"` → Send | AI responds with a biology explanation |
| 5.6 | Verify messages render with **Markdown formatting** | Headers, bold, etc. render properly (not raw markdown text) |
| 5.7 | Verify auto-scroll | Chat scrolls to newest message automatically |

---

## Phase 6: General Tutor — Profile & Settings

| # | Action | Expected Result |
|---|---|---|
| 6.1 | Click **"⚙️ View Settings & Profile"** in sidebar | Modal opens showing profile fields |
| 6.2 | Verify profile data matches registration | Full Name=`Test Student`, Age=`16`, Country=`Nigeria`, Grade=`Grade_10` |
| 6.3 | Close modal | Modal dismisses cleanly |

---

## Phase 7: General Tutor — File Upload (General Context)

| # | Action | Expected Result |
|---|---|---|
| 7.1 | In sidebar, use **"Upload Study Material"** file input | File picker opens |
| 7.2 | Select a small `.txt` or `.pdf` file | "Processing vector logic..." spinner appears |
| 7.3 | Wait for completion | Alert: `"Upload complete: <summary>..."` |
| 7.4 | Ask a question about the uploaded file content | AI references the uploaded content in response |

---

## Phase 8: General Tutor — End Session (Learning Method Sync)

| # | Action | Expected Result |
|---|---|---|
| 8.1 | After several chat exchanges, click **"End Session & Sync Mind"** | Spinner activates |
| 8.2 | Wait for completion | Alert with learning methodology update (or "unchanged") |
| 8.3 | Verify a new conversation was auto-created | Chat resets, new empty conversation |
| 8.4 | Open Settings modal again | "Identified Learning Style" textarea visible with method text |
| 8.5 | Check Supabase → `users` → `test_student` | `learning_method` column is now populated |

---

## Phase 9: Notebook Oracle — Upload & Query

| # | Action | Expected Result |
|---|---|---|
| 9.1 | Switch to **"Notebook"** mode via mode toggle | Chat clears, "Active Subject" field appears in sidebar |
| 9.2 | Enter `Biology` in **"Active Subject"** | Field populated |
| 9.3 | Upload a biology notes file (.pdf or .txt) via sidebar | Alert: `"Notebook Context uploaded. Extracted X vector chunks."` |
| 9.4 | Check Supabase → `parent_chunks` table | New rows with `owner_id=test_student`, `role=student`, `source=<filename>` |
| 9.5 | Ask: `"What is mitosis?"` | Answer drawn **strictly from uploaded context** (ground truth, no hallucination) |
| 9.6 | Ask about something NOT in the document | Response: `"I cannot find this in your provided context."` |
| 9.7 | Verify response includes `context_sources` | Source filename visible in response |

---

## Phase 10: Teacher Portal — Global Knowledge Upload

| # | Action | Expected Result |
|---|---|---|
| 10.1 | Login as `test_teacher` | Lands on Teacher Portal |
| 10.2 | Fill in: Class=`Grade_10`, Subject=`Biology` | Fields populated |
| 10.3 | Select a biology textbook PDF | File selected |
| 10.4 | Click **"Ingest to Global Index"** | Spinner → Success toast: `"Ingested X chunks into Grade_10:Biology"` |
| 10.5 | Check Supabase → `parent_chunks` | Rows with `role=teacher`, `owner_id=test_teacher` |
| 10.6 | Check Pinecone dashboard → index | Vectors present with metadata `role=teacher`, `class_id=Grade_10`, `subject=Biology` |

---

## Phase 11: Revision Mode — Exam Generation

| # | Action | Expected Result |
|---|---|---|
| 11.1 | Logout, login as `test_student` | Student main app |
| 11.2 | Switch to **"Revision"** mode | Revision interface loads (different from chat) |
| 11.3 | Enter Subject=`Biology`, Class=`Grade_10` | Fields populated |
| 11.4 | Click **"Generate Exam"** (or equivalent button) | Spinner → Exam questions appear (MCQ + theory) |
| 11.5 | Verify questions are drawn from teacher-uploaded content | Questions relate to the biology textbook uploaded in Phase 10 |
| 11.6 | Answer the questions and submit | Spinner → Grading feedback returned |
| 11.7 | Verify feedback references student's learning method | Explanations tailored to the student's identified learning style |

---

## Phase 12: Cross-Role Security

| # | Action | Expected Result |
|---|---|---|
| 12.1 | While logged in as `test_student`, manually hit `POST /teacher/upload` via browser console or Swagger | HTTP 403: `"Forbidden: Teacher privileges required."` |
| 12.2 | Copy `test_student`'s JWT, use in Swagger for `/teacher/upload` | Same 403 rejection |

---

## Phase 13: Edge Cases & Resilience

| # | Action | Expected Result |
|---|---|---|
| 13.1 | Upload a file > 10MB | HTTP 413: `"File exceeds 10 MB limit"` |
| 13.2 | Upload an unsupported file type (`.exe`, `.zip`) | HTTP 415: `"Unsupported file type"` |
| 13.3 | Send an empty chat message | Send button is disabled / validation prevents it |
| 13.4 | Send a 5000-char message | Error: `"Message exceeds maximum length of 4000 characters."` |
| 13.5 | Rapidly click Send 25+ times in 1 minute | Rate limit kicks in (429 response after ~20) |
| 13.6 | Open app in a second browser tab (same user) | Both tabs work independently |

---

## Phase 14: Data Persistence Verification

| # | Action | Expected Result |
|---|---|---|
| 14.1 | Restart the backend (Ctrl+C → `fastapi dev main.py`) | Server restarts cleanly |
| 14.2 | Login as `test_student` | Login succeeds (JWT still valid if not expired) |
| 14.3 | Check Supabase → `conversations` table | Previous conversations exist with proper `user_id` |
| 14.4 | Verify learning method persists across restart | Settings modal still shows the learning method |
| 14.5 | Ask a Notebook question about previously uploaded content | Parent chunks retrieved from Supabase (cache miss → read-through) — answers still work |

---

## Cleanup

After testing, you can delete test users from Supabase Dashboard → `users` table → select rows → Delete.
The `ON DELETE CASCADE` will automatically wipe their conversations and orphan any related data.
