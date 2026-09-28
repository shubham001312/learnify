-- =============================================================================
--  Learnify — Digital Capacity Building & Learning Management Portal
--  Fresh LMS schema (replaces the Learnify schema entirely).
--
--  Roles:  SUPREME (admin) · MASTER (trainer) · ALPHA (trainee)
--  Ids:    app-level 7-char text ids (see backend/services/uid.py), matching
--          the existing `users.id` convention.
--
--  Applied via scripts/apply_lms_schema.py (Supabase PAT / SQL editor).
-- =============================================================================

create extension if not exists pgcrypto;

-- ─────────────────────────────────────────────────────────────────────────────
-- STORAGE BUCKETS (Supabase Storage)
-- Declared here so a fresh project gets every bucket the app writes to.
--   public buckets  -> {SUPABASE_URL}/storage/v1/object/public/<bucket>/<path>
--   private buckets -> read back through a signed URL (GET /library/files/sign)
-- Size and MIME limits are enforced server-side in
-- backend/routes/library.py::_check, not by the bucket definition.
-- ─────────────────────────────────────────────────────────────────────────────

-- Existing private buckets: `do nothing`, so re-applying never flips an
-- existing bucket's visibility.
insert into storage.buckets (id, name, public)
values ('trainer-library',    'trainer-library',    false),
       ('course-attachments', 'course-attachments', false)
on conflict (id) do nothing;

-- Public buckets: avatars and course cover thumbnails are rendered directly by
-- the browser, so they must always end up public (idempotently).
insert into storage.buckets (id, name, public)
values ('avatars',       'avatars',       true),
       ('course-covers', 'course-covers', true)
on conflict (id) do update set public = excluded.public;

-- ─────────────────────────────────────────────────────────────────────────────
-- IDENTITY
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists users (
    id                   text primary key,
    email                text not null unique,
    name                 text not null default '',
    role                 text not null default 'ALPHA'
                         check (role in ('SUPREME','MASTER','ALPHA')),
    -- PENDING is the approval state: a freshly registered Trainee or Trainer
    -- cannot read anything until an Administrator approves the account.
    -- Fail-closed default — a row written without an explicit status lands in
    -- the queue instead of silently becoming usable.
    status               text not null default 'PENDING'
                         check (status in ('PENDING','ACTIVE','SUSPENDED')),
    department           text not null default '',
    designation          text not null default '',
    headline             text not null default '',
    bio                  text not null default '',
    phone                text not null default '',
    avatar_url           text,
    must_change_password boolean not null default false,
    suspended_by         text references users(id),
    suspended_at         timestamptz,
    created_by           text references users(id),
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now()
);
create index if not exists idx_users_role   on users(role);
create index if not exists idx_users_status on users(status);

-- Professional profile: qualifications, work experience, interests, skills,
-- certificates (all maintained by the user from the profile page).
create table if not exists profiles (
    user_id       text primary key references users(id) on delete cascade,
    education     jsonb not null default '[]',   -- [{degree,institution,year,grade}]
    qualifications jsonb not null default '[]',  -- [{title,issuer,year}]
    experience    jsonb not null default '[]',   -- [{role,org,from,to,summary}]
    interests     jsonb not null default '[]',   -- ["Data","Security"]
    skills        jsonb not null default '[]',   -- [{name,level(0-100)}]
    certificates  jsonb not null default '[]',   -- [{name,issuer,year,url}]
    updated_at    timestamptz not null default now()
);

create table if not exists audit_logs (
    id            uuid primary key default gen_random_uuid(),
    actor_id      text references users(id),
    action        text not null,
    resource_type text,
    resource_id   text,
    metadata      jsonb not null default '{}',
    ip_address    text,
    created_at    timestamptz not null default now()
);
create index if not exists idx_audit_actor  on audit_logs(actor_id);
create index if not exists idx_audit_action on audit_logs(action);

-- Administrator invitations.
--
-- Creating an account with role SUPREME is never public: an existing
-- Administrator mints one of these and shares the link. Registration with the
-- token consumes a use; an invalid, expired, revoked or exhausted token is
-- refused before anything is written.
--
-- `created_by` is nullable on purpose — the bootstrap admin is created by the
-- very first sign-up, before any Administrator exists to own an invite, and a
-- test harness provisions its own row. The token is the only credential here,
-- so it is stored as-is (a row no one can read is a row no one can revoke).
create table if not exists admin_invites (
    token       text primary key,
    email       text not null default '',   -- '' = any address
    note        text not null default '',
    created_by  text references users(id) on delete set null,
    created_at  timestamptz not null default now(),
    expires_at  timestamptz not null default now() + interval '7 days',
    max_uses    int not null default 1 check (max_uses > 0),
    used_count  int not null default 0 check (used_count >= 0),
    revoked_at  timestamptz
);
create index if not exists idx_admin_invites_creator on admin_invites(created_by);
create index if not exists idx_admin_invites_expiry   on admin_invites(expires_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- SUBJECTS · TOPICS · COMPETENCY  (competency mapping + report benchmarks)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists subjects (
    id          uuid primary key default gen_random_uuid(),
    code        text not null unique,
    name        text not null,
    category    text not null default '',
    description text not null default '',
    is_active   boolean not null default true,
    created_at  timestamptz not null default now()
);
create index if not exists idx_subjects_active on subjects(is_active);
-- Subject names are a human key: the wizard, reports and seeds look subjects
-- up by name, so the same name must never exist twice (case-insensitive).
create unique index if not exists subjects_name_uk on subjects (lower(name));

-- Curated topic list per subject — powers weak-point analysis and reports.
create table if not exists subject_topics (
    id          uuid primary key default gen_random_uuid(),
    subject_id  uuid not null references subjects(id) on delete cascade,
    name        text not null,
    description text not null default '',
    sort_order  int  not null default 0,
    unique (subject_id, name)
);
create index if not exists idx_topics_subject on subject_topics(subject_id);

-- Granular competencies used to rank trainers per subject.
create table if not exists competencies (
    id          uuid primary key default gen_random_uuid(),
    name        text not null unique,
    description text not null default '',
    created_at  timestamptz not null default now()
);

create table if not exists subject_competencies (
    subject_id     uuid not null references subjects(id) on delete cascade,
    competency_id  uuid not null references competencies(id) on delete cascade,
    required_weight numeric not null default 1.0 check (required_weight > 0),
    primary key (subject_id, competency_id)
);

create table if not exists trainer_competencies (
    trainer_id   text not null references users(id) on delete cascade,
    competency_id uuid not null references competencies(id) on delete cascade,
    proficiency  numeric not null default 50 check (proficiency between 0 and 100),
    evidence     text not null default '',
    verified_by  text references users(id),
    verified_at  timestamptz,
    updated_at   timestamptz not null default now(),
    primary key (trainer_id, competency_id)
);
create index if not exists idx_tc_trainer on trainer_competencies(trainer_id);

-- Curated industry-standard benchmarks per subject/topic, used verbatim in
-- Veda reports and personalised by the AI layer.
create table if not exists subject_benchmarks (
    id                   uuid primary key default gen_random_uuid(),
    subject_id           uuid not null references subjects(id) on delete cascade,
    topic_id             uuid references subject_topics(id) on delete cascade,
    industry_standard    text not null default '',
    expected_proficiency int not null default 60 check (expected_proficiency between 0 and 100),
    related_topics       text[] not null default '{}',
    notes                text not null default '',
    unique (subject_id, topic_id)
);
create index if not exists idx_bench_subject on subject_benchmarks(subject_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- COURSES · CURRICULUM · SLOTS · PROGRESS
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists courses (
    id              uuid primary key default gen_random_uuid(),
    code            text not null unique,
    title           text not null,
    description     text not null default '',
    subject_id      uuid references subjects(id),
    trainer_id      text not null references users(id),
    level           text not null default 'Beginner',
    duration_hours  numeric not null default 0,
    cover_image_url text,
    status          text not null default 'DRAFT'
                    check (status in ('DRAFT','IN_PROGRESS','PENDING_RELEASE',
                                      'PUBLISHED','ARCHIVED')),
    draft_step      int not null default 1 check (draft_step between 1 and 5),
    released_by     text references users(id),
    released_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);
create index if not exists idx_courses_trainer on courses(trainer_id);
create index if not exists idx_courses_status  on courses(status);
create index if not exists idx_courses_subject on courses(subject_id);

create table if not exists course_modules (
    id          uuid primary key default gen_random_uuid(),
    course_id   uuid not null references courses(id) on delete cascade,
    title       text not null,
    description text not null default '',
    sort_order  int not null default 0
);
create index if not exists idx_modules_course on course_modules(course_id);

-- A slot is one lesson: video + text + attachments + optional linked test.
create table if not exists course_slots (
    id               uuid primary key default gen_random_uuid(),
    module_id        uuid not null references course_modules(id) on delete cascade,
    title            text not null,
    kind             text not null default 'VIDEO'
                     check (kind in ('VIDEO','READING','LINK','TEST')),
    sort_order       int not null default 0,
    video_source     text check (video_source in ('UPLOAD','YOUTUBE')),
    storage_path     text,          -- Supabase object path when UPLOAD
    youtube_id       text,          -- parsed id when YOUTUBE
    youtube_url      text,
    poster_path      text,
    duration_seconds int not null default 0,
    body             text not null default '',
    linked_test_type text check (linked_test_type in ('QUESTIONNAIRE','ASSESSMENT')),
    linked_test_id   uuid,
    is_preview       boolean not null default false,
    created_at       timestamptz not null default now()
);
create index if not exists idx_slots_module on course_slots(module_id);
-- A slot has at most one video source; enforced by app + partial unique lookups.

create table if not exists slot_attachments (
    id              uuid primary key default gen_random_uuid(),
    slot_id         uuid not null references course_slots(id) on delete cascade,
    library_item_id uuid,
    storage_path    text not null,
    filename        text not null,
    mime            text not null default '',
    size_bytes      bigint not null default 0,
    created_at      timestamptz not null default now()
);
create index if not exists idx_attach_slot on slot_attachments(slot_id);

-- Per-trainee watch progress → resume + 90% completion rule.
create table if not exists slot_progress (
    id                   uuid primary key default gen_random_uuid(),
    slot_id              uuid not null references course_slots(id) on delete cascade,
    trainee_id           text not null references users(id) on delete cascade,
    watch_seconds        int not null default 0,
    progress_pct         numeric not null default 0 check (progress_pct between 0 and 100),
    last_position_seconds int not null default 0,
    completed            boolean not null default false,
    completed_at         timestamptz,
    updated_at           timestamptz not null default now(),
    unique (slot_id, trainee_id)
);
create index if not exists idx_progress_trainee on slot_progress(trainee_id);

create table if not exists enrollments (
    id           uuid primary key default gen_random_uuid(),
    course_id    uuid not null references courses(id) on delete cascade,
    trainee_id   text not null references users(id) on delete cascade,
    status       text not null default 'ENROLLED'
                 check (status in ('ENROLLED','IN_PROGRESS','COMPLETED','DROPPED')),
    progress_pct numeric not null default 0 check (progress_pct between 0 and 100),
    enrolled_at  timestamptz not null default now(),
    completed_at timestamptz,
    unique (course_id, trainee_id)
);
create index if not exists idx_enroll_trainee on enrollments(trainee_id);
create index if not exists idx_enroll_course  on enrollments(course_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- TRAINER LIBRARY  (recorded lectures · presentations · study materials)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists library_items (
    id           uuid primary key default gen_random_uuid(),
    trainer_id   text not null references users(id) on delete cascade,
    subject_id   uuid references subjects(id),
    title        text not null,
    description  text not null default '',
    file_type    text not null
                 check (file_type in ('RECORDED_LECTURE','PRESENTATION','STUDY_MATERIAL')),
    storage_path text not null,
    bucket       text not null default 'trainer-library',
    mime         text not null default '',
    size_bytes   bigint not null default 0,
    duration_seconds int not null default 0,
    youtube_id   text,
    created_at   timestamptz not null default now()
);
create index if not exists idx_lib_trainer on library_items(trainer_id);
create index if not exists idx_lib_type    on library_items(file_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- QUESTIONNAIRE  (practice with deadline)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists questionnaires (
    id             uuid primary key default gen_random_uuid(),
    title          text not null,
    description    text not null default '',
    subject_id     uuid references subjects(id),
    topic_id       uuid references subject_topics(id),
    course_id      uuid references courses(id) on delete set null,
    trainer_id     text not null references users(id),
    deadline_at    timestamptz,
    duration_minutes int not null default 30,
    max_attempts   int not null default 1,
    status         text not null default 'DRAFT'
                   check (status in ('DRAFT','PENDING_RELEASE','PUBLISHED',
                                     'ENDED','ARCHIVED')),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists idx_qnr_trainer on questionnaires(trainer_id);
create index if not exists idx_qnr_status  on questionnaires(status);
create index if not exists idx_qnr_deadline on questionnaires(deadline_at);

create table if not exists questionnaire_questions (
    id              uuid primary key default gen_random_uuid(),
    questionnaire_id uuid not null references questionnaires(id) on delete cascade,
    text            text not null,
    explanation     text not null default '',
    difficulty      text not null default 'medium'
                    check (difficulty in ('easy','medium','hard')),
    topic_id        uuid references subject_topics(id),
    sort_order      int not null default 0,
    points          numeric not null default 1
);
create index if not exists idx_qq_questionnaire on questionnaire_questions(questionnaire_id);
create index if not exists idx_qq_topic on questionnaire_questions(topic_id);

create table if not exists questionnaire_options (
    id          uuid primary key default gen_random_uuid(),
    question_id uuid not null references questionnaire_questions(id) on delete cascade,
    text        text not null,
    is_correct  boolean not null default false,
    sort_order  int not null default 0
);
create index if not exists idx_qo_question on questionnaire_options(question_id);

create table if not exists questionnaire_attempts (
    id               uuid primary key default gen_random_uuid(),
    questionnaire_id uuid not null references questionnaires(id) on delete cascade,
    trainee_id       text not null references users(id) on delete cascade,
    attempt_no       int not null default 1,
    started_at       timestamptz not null default now(),
    submitted_at     timestamptz,
    score            numeric not null default 0,
    max_score        numeric not null default 0,
    percentage       numeric not null default 0,
    status           text not null default 'IN_PROGRESS'
                     check (status in ('IN_PROGRESS','SUBMITTED','VOIDED','EXPIRED')),
    ended_by         text references users(id),
    responses        jsonb not null default '[]',  -- [{question_id, option_id, is_correct}]
    unique (questionnaire_id, trainee_id, attempt_no)
);
create index if not exists idx_qa_trainee on questionnaire_attempts(trainee_id);
create index if not exists idx_qa_status  on questionnaire_attempts(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- ASSESSMENT  (formal subject-wise MCQ exam → certificate)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists assessments (
    id             uuid primary key default gen_random_uuid(),
    title          text not null,
    description    text not null default '',
    subject_id     uuid references subjects(id),
    course_id      uuid references courses(id) on delete set null,
    trainer_id     text not null references users(id),
    duration_minutes int not null default 30,
    max_score      int not null default 100,
    passing_score  int not null default 60,
    deadline_at    timestamptz,
    status         text not null default 'DRAFT'
                   check (status in ('DRAFT','PENDING_RELEASE','PUBLISHED',
                                     'ENDED','ARCHIVED')),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists idx_asm_trainer on assessments(trainer_id);
create index if not exists idx_asm_status  on assessments(status);
create index if not exists idx_asm_deadline on assessments(deadline_at);

create table if not exists assessment_questions (
    id            uuid primary key default gen_random_uuid(),
    assessment_id uuid not null references assessments(id) on delete cascade,
    text          text not null,
    explanation   text not null default '',
    difficulty    text not null default 'medium'
                  check (difficulty in ('easy','medium','hard')),
    topic_id      uuid references subject_topics(id),
    sort_order    int not null default 0,
    points        numeric not null default 1
);
create index if not exists idx_aq_assessment on assessment_questions(assessment_id);
create index if not exists idx_aq_topic on assessment_questions(topic_id);

create table if not exists assessment_options (
    id          uuid primary key default gen_random_uuid(),
    question_id uuid not null references assessment_questions(id) on delete cascade,
    text        text not null,
    is_correct  boolean not null default false,
    sort_order  int not null default 0
);
create index if not exists idx_ao_question on assessment_options(question_id);

create table if not exists assessment_attempts (
    id            uuid primary key default gen_random_uuid(),
    assessment_id uuid not null references assessments(id) on delete cascade,
    trainee_id    text not null references users(id) on delete cascade,
    attempt_no    int not null default 1,
    started_at    timestamptz not null default now(),
    submitted_at  timestamptz,
    score         numeric not null default 0,
    max_score     numeric not null default 0,
    percentage    numeric not null default 0,
    passed        boolean not null default false,
    status        text not null default 'IN_PROGRESS'
                  check (status in ('IN_PROGRESS','SUBMITTED','VOIDED','EXPIRED')),
    ended_by      text references users(id),
    unique (assessment_id, trainee_id, attempt_no)
);
create index if not exists idx_asa_trainee on assessment_attempts(trainee_id);
create index if not exists idx_asa_status  on assessment_attempts(status);

create table if not exists assessment_responses (
    id           uuid primary key default gen_random_uuid(),
    attempt_id   uuid not null references assessment_attempts(id) on delete cascade,
    question_id  uuid not null references assessment_questions(id) on delete cascade,
    option_id    uuid references assessment_options(id),
    is_correct   boolean not null default false,
    answered_at  timestamptz not null default now(),
    unique (attempt_id, question_id)
);
create index if not exists idx_ar_attempt on assessment_responses(attempt_id);

-- Auto-issued when an Alpha passes an assessment.
create table if not exists certificates (
    id            uuid primary key default gen_random_uuid(),
    code          text not null unique,
    trainee_id    text not null references users(id) on delete cascade,
    assessment_id uuid references assessments(id) on delete set null,
    attempt_id    uuid references assessment_attempts(id) on delete set null,
    title         text not null,
    subject_id    uuid references subjects(id),
    score         numeric not null default 0,
    percentage    numeric not null default 0,
    issued_by     text not null default 'AUTO'
                  check (issued_by in ('AUTO','MASTER','SUPREME')),
    issued_at     timestamptz not null default now(),
    status        text not null default 'VALID'
                  check (status in ('VALID','REVOKED'))
);
create index if not exists idx_cert_trainee on certificates(trainee_id);
create index if not exists idx_cert_status  on certificates(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- AI DRAFT QUESTIONS  (Groq output → edit → publish; never visible to Alpha)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists draft_questions (
    id           uuid primary key default gen_random_uuid(),
    owner_id     text not null references users(id) on delete cascade,
    target_type  text not null check (target_type in ('QUESTIONNAIRE','ASSESSMENT')),
    target_id    uuid,
    text         text not null,
    choices      jsonb not null default '[]',
    correct_index int not null default 0,
    explanation  text not null default '',
    difficulty   text not null default 'medium'
                 check (difficulty in ('easy','medium','hard')),
    topic_id     uuid references subject_topics(id),
    source       text not null default 'AI' check (source in ('AI','MANUAL')),
    status       text not null default 'DRAFT'
                 check (status in ('DRAFT','PUBLISHED','DISCARDED')),
    sort_order   int not null default 0,
    created_at   timestamptz not null default now()
);
create index if not exists idx_draft_owner on draft_questions(owner_id, target_type, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- FEEDBACK
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists course_feedback (
    id         uuid primary key default gen_random_uuid(),
    course_id  uuid not null references courses(id) on delete cascade,
    trainee_id text not null references users(id) on delete cascade,
    rating     int not null check (rating between 1 and 5),
    comment    text not null default '',
    created_at timestamptz not null default now(),
    unique (course_id, trainee_id)
);
create index if not exists idx_cf_course on course_feedback(course_id);

create table if not exists content_feedback (
    id           uuid primary key default gen_random_uuid(),
    trainee_id   text not null references users(id) on delete cascade,
    content_type text not null check (content_type in ('SLOT','LIBRARY')),
    content_id   uuid not null,
    rating       int not null check (rating between 1 and 5),
    comment      text not null default '',
    created_at   timestamptz not null default now(),
    unique (trainee_id, content_type, content_id)
);
create index if not exists idx_cfb_content on content_feedback(content_type, content_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- HOME FEED · NOTIFICATIONS · PARTICIPATION
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists home_posts (
    id           uuid primary key default gen_random_uuid(),
    type         text not null
                 check (type in ('NOTIFICATION','ANNOUNCEMENT','ACHIEVEMENT','NEW_CONTENT')),
    title        text not null,
    body         text not null default '',
    link         text,
    image_url    text,
    target_roles text[] not null default '{SUPREME,MASTER,ALPHA}',
    pinned       boolean not null default false,
    published    boolean not null default true,
    published_by text references users(id),
    published_at timestamptz not null default now()
);
create index if not exists idx_posts_type on home_posts(type);
create index if not exists idx_posts_published on home_posts(published, published_at desc);

create table if not exists notifications (
    id         uuid primary key default gen_random_uuid(),
    user_id    text references users(id) on delete cascade,
    type       text not null default 'SYSTEM',
    title      text not null,
    message    text not null default '',
    link       text,
    read       boolean not null default false,
    metadata   jsonb not null default '{}',
    created_at timestamptz not null default now()
);
create index if not exists idx_notif_user on notifications(user_id, read);

create table if not exists participation_logs (
    id         uuid primary key default gen_random_uuid(),
    user_id    text not null references users(id) on delete cascade,
    item_type  text not null,
    item_id    uuid,
    action     text not null,
    duration_seconds int not null default 0,
    metadata   jsonb not null default '{}',
    created_at timestamptz not null default now()
);
create index if not exists idx_part_user on participation_logs(user_id);
create index if not exists idx_part_item on participation_logs(item_type, item_id);
create index if not exists idx_part_time on participation_logs(created_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- VEDA PERFORMANCE REPORTS  (deterministic base + AI insights)
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists performance_reports (
    id             uuid primary key default gen_random_uuid(),
    attempt_id     uuid not null,
    attempt_kind   text not null check (attempt_kind in ('ASSESSMENT','QUESTIONNAIRE')),
    trainee_id     text not null references users(id) on delete cascade,
    subject_id     uuid references subjects(id),
    score          numeric not null default 0,
    percentage     numeric not null default 0,
    passed         boolean not null default false,
    weak_topics    jsonb not null default '[]',  -- [{topic,correct,total,pct}]
    strong_topics  jsonb not null default '[]',
    difficulty_breakdown jsonb not null default '{}',
    benchmark      jsonb not null default '{}',
    ai_insights    jsonb not null default '{}',  -- {weak_points, improve, industry, learn_next, suggestions}
    ai_model       text,
    ai_generated   boolean not null default false,
    generated_at   timestamptz not null default now(),
    unique (attempt_id, attempt_kind)
);
create index if not exists idx_rep_trainee on performance_reports(trainee_id);
create index if not exists idx_rep_subject on performance_reports(subject_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- USERS TABLE EXTENSIONS for existing auth flow compatibility
--
-- `language` survives because the register and profile routes still carry it
-- (the product is English-only, so it never varies). The old `premium`
-- column went with the Razorpay feature and nothing reads it any more.
-- ─────────────────────────────────────────────────────────────────────────────

alter table users add column if not exists language text not null default 'English';

-- Account approval state.
--
-- `create table if not exists` never re-runs against a live database, so the
-- widened CHECK and the fail-closed default have to be re-stated as ALTERs.
-- Both are no-ops on a database created from the definition above: the
-- constraint Postgres auto-names for an inline check on users.status is
-- `users_status_check`, so this drops the identical constraint and puts the
-- identical one straight back.
alter table users drop constraint if exists users_status_check;
alter table users add constraint users_status_check
    check (status in ('PENDING','ACTIVE','SUSPENDED'));
alter table users alter column status set default 'PENDING';

