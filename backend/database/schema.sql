-- Learnify — Supabase schema (run ONCE in Supabase SQL Editor, then: python -m backend.seed_supabase)
create extension if not exists vector;

-- ───────────────────────── users ─────────────────────────
create table if not exists users (
    id text primary key,
    email text unique,
    name text,
    language text default 'English',
    grade text,
    premium bool default false,
    created_at timestamptz default now()
);

-- ───────────────────────── colleges ─────────────────────────
create table if not exists colleges (
    id bigint primary key,
    name text not null,
    state text,
    city text,
    district text,
    pin_code text,
    address text,
    type text,
    nirf_rank integer,
    nirf_year integer default 2024,
    avg_package real,
    placement_pct integer,
    rating real,
    streams text[],
    top_recruiters text[],
    min_12th_marks integer,
    website text,
    affiliation text,
    founded text,
    description text,
    pros text[],
    cons text[],
    featured boolean default false,
    created_at timestamptz default now()
);
create index if not exists idx_colleges_state on colleges (state);
create index if not exists idx_colleges_type on colleges (type);
create index if not exists idx_colleges_nirf on colleges (nirf_rank);
create index if not exists idx_colleges_featured on colleges (featured);

-- ───────────────────────── scholarships ─────────────────────────
create table if not exists scholarships (
    id bigint primary key,
    name text not null,
    amount text,
    eligibility text,
    deadline text,
    category text,
    state text,
    documents text[],
    colleges text[],
    provider text,
    link text,
    description text
);
create index if not exists idx_scholarships_state on scholarships (state);
create index if not exists idx_scholarships_category on scholarships (category);

-- ───────────────────────── reviews ─────────────────────────
create table if not exists college_reviews (
    id bigint generated always as identity primary key,
    college_id bigint not null,
    author text default 'Anonymous',
    rating real default 0,
    text text,
    pros text,
    cons text,
    created_at timestamptz default now()
);
create index if not exists idx_reviews_college on college_reviews (college_id);

-- ───────────────────────── scanned data (per user) ─────────────────────────
-- Generic store for anything a user "scans" (notes, docs, OCR, quick captures).
-- Keyed by user_id + indexed for fast per-user retrieval.
create table if not exists scanned_data (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    data_type text default 'note',
    title text,
    content text,
    source text,
    meta jsonb,
    created_at timestamptz default now()
);
create index if not exists idx_scanned_user on scanned_data (user_id);
create index if not exists idx_scanned_user_created on scanned_data (user_id, created_at desc);

-- ───────────────────────── documents / rag ─────────────────────────
create table if not exists documents (
    id uuid default gen_random_uuid() primary key,
    user_id uuid,
    filename text,
    is_synthetic bool default false,
    extracted jsonb,
    created_at timestamptz default now()
);
create table if not exists doc_chunks (
    id serial primary key,
    user_id uuid,
    namespace text,
    content text,
    embedding vector(384),
    created_at timestamptz default now()
);
create index if not exists idx_documents_user_id on documents (user_id);
create index if not exists idx_doc_chunks_user_id on doc_chunks (user_id);
create index if not exists idx_doc_chunks_embedding
    on doc_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ───────────────────────── conversations / memory ─────────────────────────
create table if not exists conversations (
    id serial primary key,
    user_id uuid,
    role text,
    content text,
    created_at timestamptz default now()
);
create table if not exists memory (
    id serial primary key,
    user_id uuid,
    layer int,
    kind text,
    content text,
    created_at timestamptz default now()
);

-- ───────────────────────── subscriptions / sgpa / plans ─────────────────────────
create table if not exists subscriptions (
    id serial primary key,
    user_id uuid,
    plan text,
    status text,
    razorpay_order_id text,
    created_at timestamptz default now()
);
create table if not exists sgpa_entries (
    id serial primary key,
    user_id uuid,
    semester text,
    sgpa numeric,
    created_at timestamptz default now()
);
create index if not exists idx_sgpa_user_id on sgpa_entries (user_id);
create table if not exists user_profiles (
    id uuid default gen_random_uuid() primary key,
    user_id uuid unique,
    board text,
    target_exam text,
    target_year int,
    phone text,
    updated_at timestamptz default now()
);
create table if not exists study_plans (
    id uuid default gen_random_uuid() primary key,
    user_id uuid,
    title text,
    exam_date date,
    hours_per_day int,
    subjects jsonb,
    plan jsonb,
    created_at timestamptz default now()
);
create index if not exists idx_study_plans_user_id on study_plans (user_id);

-- NOTE: enable RLS + policies later once the app is verified working. The
-- FastAPI backend uses the SERVICE ROLE key, which bypasses RLS server-side.
