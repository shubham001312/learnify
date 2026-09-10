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

-- ──────────────────────────────────────────────────────────────────────────
-- LEARNIFY — SIH 2026 EXTENSION TABLES
-- ──────────────────────────────────────────────────────────────────────────

-- ───────────────────────── ROLES & ORGANIZATIONS ─────────────────────────
create table if not exists organizations (
    id uuid default gen_random_uuid() primary key,
    name text not null,
    type text not null default 'COMPANY',
    description text,
    website text,
    logo_url text,
    industry text,
    size text,
    location text,
    verified boolean default false,
    created_at timestamptz default now()
);

create table if not exists user_roles (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    role text not null default 'STUDENT',
    organization_id uuid references organizations(id),
    verified boolean default false,
    created_at timestamptz default now(),
    unique(user_id, role)
);
create index if not exists idx_user_roles_user on user_roles(user_id);
create index if not exists idx_user_roles_role on user_roles(role);

-- ───────────────────────── SKILL TAXONOMY ─────────────────────────
create table if not exists skill_categories (
    id uuid default gen_random_uuid() primary key,
    name text not null unique,
    description text,
    created_at timestamptz default now()
);

create table if not exists skills (
    id uuid default gen_random_uuid() primary key,
    name text not null unique,
    category_id uuid references skill_categories(id),
    parent_skill_id uuid references skills(id),
    description text,
    difficulty text default 'intermediate',
    demand_score real default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
create index if not exists idx_skills_name on skills(name);
create index if not exists idx_skills_category on skills(category_id);

create table if not exists skill_aliases (
    id uuid default gen_random_uuid() primary key,
    skill_id uuid not null references skills(id),
    alias text not null unique,
    created_at timestamptz default now()
);
create index if not exists idx_skill_aliases_alias on skill_aliases(alias);

-- ───────────────────────── STUDENT SKILL PROFILE ─────────────────────────
create table if not exists user_skills (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    skill_id uuid not null references skills(id),
    level real default 0,
    source text default 'SELF_REPORTED',
    verified boolean default false,
    confidence real default 0,
    last_assessed_at timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(user_id, skill_id)
);
create index if not exists idx_user_skills_user on user_skills(user_id);

-- ───────────────────────── ASSESSMENTS ─────────────────────────
create table if not exists assessments (
    id uuid default gen_random_uuid() primary key,
    title text not null,
    description text,
    category text not null default 'technical',
    duration_minutes int default 30,
    max_score int default 100,
    passing_score int default 60,
    cooldown_hours int default 24,
    is_active boolean default true,
    created_at timestamptz default now()
);

create table if not exists assessment_questions (
    id uuid default gen_random_uuid() primary key,
    assessment_id uuid not null references assessments(id),
    question_text text not null,
    question_type text default 'MCQ',
    difficulty text default 'medium',
    weight real default 1.0,
    explanation text,
    created_at timestamptz default now()
);
create index if not exists idx_aq_assessment on assessment_questions(assessment_id);

create table if not exists assessment_options (
    id uuid default gen_random_uuid() primary key,
    question_id uuid not null references assessment_questions(id),
    option_text text not null,
    is_correct boolean default false,
    sort_order int default 0
);
create index if not exists idx_ao_question on assessment_options(question_id);

create table if not exists question_skills (
    id uuid default gen_random_uuid() primary key,
    question_id uuid not null references assessment_questions(id),
    skill_id uuid not null references skills(id),
    weight real default 1.0
);

create table if not exists assessment_attempts (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    assessment_id uuid not null references assessments(id),
    score real default 0,
    max_score real default 0,
    percentage real default 0,
    started_at timestamptz default now(),
    completed_at timestamptz,
    status text default 'in_progress'
);
create index if not exists idx_aa_user on assessment_attempts(user_id);
create index if not exists idx_aa_assessment on assessment_attempts(assessment_id);

create table if not exists assessment_responses (
    id uuid default gen_random_uuid() primary key,
    attempt_id uuid not null references assessment_attempts(id),
    question_id uuid not null references assessment_questions(id),
    selected_option_id uuid references assessment_options(id),
    answer_text text,
    is_correct boolean default false,
    score real default 0,
    answered_at timestamptz default now()
);
create index if not exists idx_ar_attempt on assessment_responses(attempt_id);

-- ───────────────────────── CAREER ROLES ─────────────────────────
create table if not exists career_roles (
    id uuid default gen_random_uuid() primary key,
    title text not null,
    description text,
    category text,
    avg_salary_min int,
    avg_salary_max int,
    experience_required text,
    education_required text,
    is_active boolean default true,
    created_at timestamptz default now()
);

create table if not exists role_skills (
    id uuid default gen_random_uuid() primary key,
    role_id uuid not null references career_roles(id),
    skill_id uuid not null references skills(id),
    required_level real default 60,
    weight real default 1.0,
    is_required boolean default true,
    unique(role_id, skill_id)
);

-- ───────────────────────── OPPORTUNITIES ─────────────────────────
create table if not exists opportunities (
    id uuid default gen_random_uuid() primary key,
    organization_id uuid not null references organizations(id),
    created_by text not null,
    type text not null default 'INTERNSHIP',
    title text not null,
    description text,
    education_requirements text,
    experience_requirements text,
    location text,
    remote_allowed boolean default false,
    stipend text,
    salary_min int,
    salary_max int,
    duration text,
    deadline timestamptz,
    status text default 'ACTIVE',
    max_applicants int,
    screening_questions jsonb default '[]',
    version int default 1,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
create index if not exists idx_opp_type on opportunities(type);
create index if not exists idx_opp_status on opportunities(status);
create index if not exists idx_opp_deadline on opportunities(deadline);
create index if not exists idx_opp_org on opportunities(organization_id);

create table if not exists opportunity_skills (
    id uuid default gen_random_uuid() primary key,
    opportunity_id uuid not null references opportunities(id),
    skill_id uuid not null references skills(id),
    required_level real default 60,
    is_required boolean default true,
    unique(opportunity_id, skill_id)
);

-- ───────────────────────── APPLICATIONS ─────────────────────────
create table if not exists applications (
    id uuid default gen_random_uuid() primary key,
    student_id text not null,
    opportunity_id uuid not null references opportunities(id),
    status text default 'APPLIED',
    cover_letter text,
    screening_answers jsonb default '{}',
    match_score real,
    applied_at timestamptz default now(),
    updated_at timestamptz default now(),
    unique(student_id, opportunity_id)
);
create index if not exists idx_app_student on applications(student_id);
create index if not exists idx_app_opportunity on applications(opportunity_id);
create index if not exists idx_app_status on applications(status);

create table if not exists application_events (
    id uuid default gen_random_uuid() primary key,
    application_id uuid not null references applications(id),
    from_status text,
    to_status text not null,
    changed_by text,
    notes text,
    created_at timestamptz default now()
);

-- ───────────────────────── LEARNING RESOURCES ─────────────────────────
create table if not exists learning_resources (
    id uuid default gen_random_uuid() primary key,
    title text not null,
    description text,
    url text,
    type text,
    provider text,
    difficulty text,
    duration_hours real,
    is_free boolean default true,
    created_at timestamptz default now()
);

create table if not exists resource_skills (
    id uuid default gen_random_uuid() primary key,
    resource_id uuid not null references learning_resources(id),
    skill_id uuid not null references skills(id),
    relevance real default 1.0
);

create table if not exists learning_progress (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    resource_id uuid not null references learning_resources(id),
    status text default 'NOT_STARTED',
    progress_pct real default 0,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz default now(),
    unique(user_id, resource_id)
);

-- ───────────────────────── PORTFOLIO ─────────────────────────
create table if not exists portfolio_items (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    type text not null default 'PROJECT',
    title text not null,
    description text,
    url text,
    skills_used uuid[],
    verified boolean default false,
    verification_source text,
    created_at timestamptz default now()
);
create index if not exists idx_pi_user on portfolio_items(user_id);

-- ───────────────────────── VERIFICATION ─────────────────────────
create table if not exists verification_records (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    skill_id uuid not null references skills(id),
    evidence_type text not null,
    evidence_id uuid,
    status text default 'SELF_REPORTED',
    verified_by text,
    verified_at timestamptz,
    created_at timestamptz default now()
);

-- ───────────────────────── NOTIFICATIONS ─────────────────────────
create table if not exists notifications (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    type text not null,
    title text not null,
    message text,
    link text,
    read boolean default false,
    metadata jsonb default '{}',
    created_at timestamptz default now()
);
create index if not exists idx_notif_user on notifications(user_id);
create index if not exists idx_notif_read on notifications(user_id, read);

-- ───────────────────────── AUDIT LOG ─────────────────────────
create table if not exists audit_logs (
    id uuid default gen_random_uuid() primary key,
    actor_id text,
    action text not null,
    resource_type text,
    resource_id text,
    metadata jsonb default '{}',
    ip_address text,
    created_at timestamptz default now()
);
create index if not exists idx_audit_actor on audit_logs(actor_id);
create index if not exists idx_audit_action on audit_logs(action);

-- ───────────────────────── EXTEND EXISTING USERS TABLE ─────────────────────────
alter table users add column if not exists role text default 'STUDENT';
alter table users add column if not exists organization_id uuid references organizations(id);
alter table users add column if not exists avatar_url text;
alter table users add column if not exists bio text default '';
alter table users add column if not exists headline text default '';
alter table users add column if not exists career_goal text default '';
alter table users add column if not exists stream text default '';
alter table users add column if not exists profile_version int default 1;
alter table users add column if not exists skill_profile_version int default 1;

-- NOTE: enable RLS + policies later once the app is verified working. The
-- FastAPI backend uses the SERVICE ROLE key, which bypasses RLS server-side.

-- ───────────────────────── INTERNSHIPS ─────────────────────────
create table if not exists internships (
    id uuid default gen_random_uuid() primary key,
    application_id uuid not null references applications(id) unique,
    student_id text not null,
    organization_id uuid not null references organizations(id),
    opportunity_id uuid not null references opportunities(id),
    mentor_id text,
    title text not null,
    status text default 'ACTIVE',
    start_date timestamptz default now(),
    end_date timestamptz,
    completion_pct real default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
create index if not exists idx_intern_student on internships(student_id);
create index if not exists idx_intern_org on internships(organization_id);
create index if not exists idx_intern_mentor on internships(mentor_id);
create index if not exists idx_intern_status on internships(status);

-- ───────────────────────── MILESTONES ─────────────────────────
create table if not exists milestones (
    id uuid default gen_random_uuid() primary key,
    internship_id uuid not null references internships(id),
    title text not null,
    description text,
    start_date timestamptz,
    deadline timestamptz,
    status text default 'NOT_STARTED',
    completion_pct real default 0,
    weight real default 1.0,
    created_by text,
    reviewed_by text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
create index if not exists idx_milestone_intern on milestones(internship_id);

-- ───────────────────────── TASKS ─────────────────────────
create table if not exists internship_tasks (
    id uuid default gen_random_uuid() primary key,
    milestone_id uuid not null references milestones(id),
    title text not null,
    description text,
    deadline timestamptz,
    status text default 'NOT_STARTED',
    priority text default 'MEDIUM',
    assigned_to text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
create index if not exists idx_task_milestone on internship_tasks(milestone_id);

-- ───────────────────────── DELIVERABLES ─────────────────────────
create table if not exists deliverables (
    id uuid default gen_random_uuid() primary key,
    task_id uuid references internship_tasks(id),
    internship_id uuid not null references internships(id),
    title text not null,
    description text,
    submission_url text,
    submitted_at timestamptz,
    review_status text default 'PENDING',
    mentor_feedback text,
    reviewed_at timestamptz,
    created_at timestamptz default now()
);
create index if not exists idx_deliverable_intern on deliverables(internship_id);

-- ───────────────────────── MENTOR ASSIGNMENTS ─────────────────────────
create table if not exists mentor_assignments (
    id uuid default gen_random_uuid() primary key,
    mentor_id text not null,
    internship_id uuid not null references internships(id),
    mentor_type text default 'INDUSTRY',
    assigned_at timestamptz default now(),
    unique(mentor_id, internship_id)
);

-- ───────────────────────── MENTOR FEEDBACK ─────────────────────────
create table if not exists mentor_feedback (
    id uuid default gen_random_uuid() primary key,
    internship_id uuid not null references internships(id),
    mentor_id text not null,
    student_id text not null,
    technical_skills real default 0,
    problem_solving real default 0,
    communication real default 0,
    teamwork real default 0,
    professionalism real default 0,
    domain_knowledge real default 0,
    initiative real default 0,
    time_management real default 0,
    overall_rating real default 0,
    strengths text,
    areas_for_improvement text,
    recommended_actions text,
    comments text,
    created_at timestamptz default now()
);
create index if not exists idx_feedback_intern on mentor_feedback(internship_id);
create index if not exists idx_feedback_student on mentor_feedback(student_id);

-- ───────────────────────── EVALUATIONS ─────────────────────────
create table if not exists evaluations (
    id uuid default gen_random_uuid() primary key,
    internship_id uuid not null references internships(id),
    evaluator_id text not null,
    eval_type text not null default 'MID_TERM',
    scores jsonb default '{}',
    comments text,
    recommendations text,
    submitted_at timestamptz default now()
);
create index if not exists idx_eval_intern on evaluations(internship_id);

-- ───────────────────────── CREDENTIALS ─────────────────────────
create table if not exists credentials (
    id uuid default gen_random_uuid() primary key,
    user_id text not null,
    title text not null,
    issuing_org text,
    credential_url text,
    credential_id text,
    issued_at timestamptz,
    expires_at timestamptz,
    status text default 'SELF_REPORTED',
    verified boolean default false,
    verified_by text,
    verified_at timestamptz,
    created_at timestamptz default now()
);
create index if not exists idx_cred_user on credentials(user_id);

-- ───────────────────────── INSTITUTION SYNC ─────────────────────────
create table if not exists institution_sync_jobs (
    id uuid default gen_random_uuid() primary key,
    institution_id uuid not null references organizations(id),
    job_type text not null,
    status text default 'PENDING',
    started_at timestamptz,
    completed_at timestamptz,
    records_processed int default 0,
    records_created int default 0,
    records_updated int default 0,
    records_failed int default 0,
    error_summary text,
    created_at timestamptz default now()
);

-- ───────────────────────── COLLABORATION ─────────────────────────
create table if not exists collaboration_projects (
    id uuid default gen_random_uuid() primary key,
    title text not null,
    description text,
    institution_id uuid references organizations(id),
    industry_id uuid references organizations(id),
    project_type text default 'MENTORSHIP',
    status text default 'ACTIVE',
    start_date timestamptz,
    end_date timestamptz,
    created_at timestamptz default now()
);
create index if not exists idx_collab_institution on collaboration_projects(institution_id);
