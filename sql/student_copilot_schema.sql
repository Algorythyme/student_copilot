-- student_copilot schema on unified Pedagic Postgres (same instance as sms / teacher_copilot).
-- Apply: python scripts/apply_student_copilot_schema.py

CREATE SCHEMA IF NOT EXISTS student_copilot;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

SET search_path TO student_copilot;

-- Nest JWT `sub` is canonical identity (UUID). `username` kept for legacy standalone accounts.
CREATE TABLE IF NOT EXISTS users (
    user_id text PRIMARY KEY,
    username text UNIQUE,
    password_hash text,
    role text NOT NULL DEFAULT 'student',
    full_name text NOT NULL DEFAULT '',
    school_id text,
    age integer,
    country text,
    class_id text,
    subjects text,
    learning_method text DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title text DEFAULT 'Untitled Chat',
    profile_override jsonb DEFAULT '{}'::jsonb,
    summaries jsonb DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

CREATE TABLE IF NOT EXISTS parent_chunks (
    id text PRIMARY KEY,
    content text NOT NULL,
    owner_id text NOT NULL,
    source text DEFAULT '',
    role text NOT NULL DEFAULT 'student',
    created_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_parent_chunks_owner ON parent_chunks(owner_id);
