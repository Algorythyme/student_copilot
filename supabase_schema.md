```sql
-- schema.sql
-- Run this script in your Supabase SQL Editor to initialize the sovereign context DB.
-- IMPORTANT: Backend MUST connect using the service_role key (bypasses RLS).
-- RLS policies below exist solely to lock out the anon key from direct client abuse.

-- 1. Users Table (Core Identity)
CREATE TABLE IF NOT EXISTS public.users (
    username text PRIMARY KEY,
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'student',
    full_name text NOT NULL,
    age integer,
    country text,
    class_id text,
    subjects text,
    learning_method text DEFAULT '',
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- RLS: Lock down the anon key completely. All mutations go through the backend (service_role).
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Anon key can read (needed if you ever expose a public leaderboard, etc). Deny everything else.
CREATE POLICY "anon_read_users" ON public.users FOR SELECT USING (true);
-- No INSERT, UPDATE, or DELETE policies = anon key is fully blocked from mutations.
-- The service_role key bypasses RLS entirely, so the backend operates unrestricted.

-- 2. Conversations Table (Replaces SESSIONS dict)
CREATE TABLE IF NOT EXISTS public.conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL REFERENCES public.users(username) ON DELETE CASCADE,
    title text DEFAULT 'Untitled Chat',
    profile_override jsonb DEFAULT '{}'::jsonb,
    summaries jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Index for fast user conversation lookups
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations(user_id);

-- RLS: Same principle. Anon key gets read-only. Backend (service_role) handles all writes.
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_conversations" ON public.conversations FOR SELECT USING (true);
-- No INSERT, UPDATE, or DELETE policies for anon. Service_role bypasses RLS.

-- 3. Parent Chunks Table (Persistent two-tier RAG context)
-- Redis serves as hot cache; Supabase is the durable source of truth.
CREATE TABLE IF NOT EXISTS public.parent_chunks (
    id text PRIMARY KEY,
    content text NOT NULL,
    owner_id text NOT NULL,
    source text DEFAULT '',
    role text NOT NULL DEFAULT 'student',
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_parent_chunks_owner ON public.parent_chunks(owner_id);

ALTER TABLE public.parent_chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_parent_chunks" ON public.parent_chunks FOR SELECT USING (true);

-- Optional: Supabase realtime configuration for future multi-device sync
ALTER PUBLICATION supabase_realtime ADD TABLE public.users;
ALTER PUBLICATION supabase_realtime ADD TABLE public.conversations;
```
