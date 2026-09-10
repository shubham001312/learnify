# Learnify — Master Plan (SIH 2026 · Problem SIH26044)

> **Academia–Industry Skill Mapping, Internship & Placement Platform**

---

## 1. Product Vision

Learnify is a **continuous skill-intelligence platform** connecting students, academia, and industry through measurable skills rather than resumes alone.

### Core Product Loop

```
Student Profile
  → Skill Assessment
    → Skill Profile
      → Industry Role Requirements
        → Skill Gap Analysis
          → Personalized Learning Roadmap
            → Skill Improvement
              → Opportunity Matching
                → Application
                  → Experience + Verification
                    → Digital Portfolio
                      → Better Matching
```

### Core Differentiators

1. **Skill-first matching** — validated skill profiles, not resume keywords
2. **Explainable matching** — every score has reasons, not a black box
3. **Gap closure** — platform tells you what's missing and how to acquire it
4. **Verification** — separate claimed skills from verified skills
5. **Continuous readiness** — career readiness evolves as students learn, assess, build, and complete internships

---

## 2. Tech Stack (PRESERVED)

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | Vanilla HTML/CSS/JS | SPA with tab/fullpage navigation, no build system |
| **Backend** | Python FastAPI | REST API, auto OpenAPI docs |
| **Database** | Supabase (PostgreSQL + pgvector) | SQLite fallback, seed data fallback |
| **AI** | Groq via OpenRouter | Chat, vision, JSON mode |
| **Auth** | Supabase Auth + custom HMAC tokens | 7-day signed tokens |
| **Payments** | Razorpay | ₹5 trial → ₹37/month |
| **Deploy** | Vercel serverless | `api/index.py` entry point |

No technology changes. All new features extend the existing stack.

---

## 3. User Roles (RBAC)

| Role | Description | Dashboard |
|------|------------|-----------|
| `STUDENT` | Default role. Takes assessments, applies to opportunities, builds portfolio. | Student Dashboard |
| `INDUSTRY` | Company recruiter. Posts opportunities, shortlists candidates. | Industry Dashboard |
| `ACADEMICIAN` | Faculty member. Mentors students, participates in industry programs. | Academician Dashboard |
| `INSTITUTION_ADMIN` | College admin. Monitors skill development, placement readiness. | Institution Dashboard |
| `SUPER_ADMIN` | Platform admin. Manages users, skills, assessments, content. | Admin Dashboard |

### RBAC Matrix

| Action | STUDENT | INDUSTRY | ACADEMICIAN | INST_ADMIN | SUPER_ADMIN |
|--------|---------|----------|-------------|------------|-------------|
| Take assessment | ✅ | ❌ | ❌ | ❌ | ❌ |
| View own skill profile | ✅ | ❌ | ❌ | ❌ | ❌ |
| View matched candidates | ❌ | ✅ | ❌ | ✅ | ✅ |
| Post opportunity | ❌ | ✅ | ❌ | ❌ | ✅ |
| Shortlist candidate | ❌ | ✅ | ❌ | ❌ | ✅ |
| View institution analytics | ❌ | ❌ | ❌ | ✅ | ✅ |
| Manage skills taxonomy | ❌ | ❌ | ❌ | ❌ | ✅ |
| Mentor students | ❌ | ✅ | ✅ | ❌ | ❌ |

---

## 4. Database Schema

### 4.1 New Tables (added to existing schema)

```sql
-- ───────────────────────── ROLES & ORGANIZATIONS ─────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'COMPANY' | 'INSTITUTION'
    description TEXT,
    website TEXT,
    logo_url TEXT,
    industry TEXT,
    size TEXT, -- '1-10', '11-50', '51-200', '201-500', '500+'
    location TEXT,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_roles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    role TEXT NOT NULL, -- 'STUDENT' | 'INDUSTRY' | 'ACADEMICIAN' | 'INSTITUTION_ADMIN' | 'SUPER_ADMIN'
    organization_id UUID REFERENCES organizations(id),
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, role)
);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);

-- ───────────────────────── SKILL TAXONOMY ─────────────────────────
CREATE TABLE IF NOT EXISTS skill_categories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    category_id UUID REFERENCES skill_categories(id),
    parent_skill_id UUID REFERENCES skills(id),
    description TEXT,
    difficulty TEXT DEFAULT 'intermediate', -- 'beginner' | 'intermediate' | 'advanced' | 'expert'
    demand_score REAL DEFAULT 0, -- 0-100, updated from opportunity data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name)
);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category_id);

CREATE TABLE IF NOT EXISTS skill_aliases (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    skill_id UUID NOT NULL REFERENCES skills(id),
    alias TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_skill_aliases_alias ON skill_aliases(alias);

-- ───────────────────────── STUDENT SKILL PROFILE ─────────────────────────
CREATE TABLE IF NOT EXISTS user_skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    level REAL DEFAULT 0, -- 0-100
    source TEXT DEFAULT 'SELF_REPORTED', -- 'SELF_REPORTED' | 'ASSESSMENT' | 'CERTIFICATE' | 'INTERNSHIP' | 'PROJECT'
    verified BOOLEAN DEFAULT FALSE,
    confidence REAL DEFAULT 0, -- 0-1, how confident we are in this level
    last_assessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_user_skills_user ON user_skills(user_id);

-- ───────────────────────── ASSESSMENTS ─────────────────────────
CREATE TABLE IF NOT EXISTS assessments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL, -- 'technical' | 'aptitude' | 'communication' | 'problem_solving' | 'domain' | 'soft_skills'
    duration_minutes INT DEFAULT 30,
    max_score INT DEFAULT 100,
    passing_score INT DEFAULT 60,
    cooldown_hours INT DEFAULT 24,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assessment_questions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    assessment_id UUID NOT NULL REFERENCES assessments(id),
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'MCQ', -- 'MCQ' | 'SHORT_ANSWER' | 'CODING'
    difficulty TEXT DEFAULT 'medium', -- 'easy' | 'medium' | 'hard'
    weight REAL DEFAULT 1.0,
    explanation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_aq_assessment ON assessment_questions(assessment_id);

CREATE TABLE IF NOT EXISTS assessment_options (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    question_id UUID NOT NULL REFERENCES assessment_questions(id),
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE,
    sort_order INT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ao_question ON assessment_options(question_id);

CREATE TABLE IF NOT EXISTS question_skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    question_id UUID NOT NULL REFERENCES assessment_questions(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    weight REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    assessment_id UUID NOT NULL REFERENCES assessments(id),
    score REAL DEFAULT 0,
    max_score REAL DEFAULT 0,
    percentage REAL DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'in_progress' -- 'in_progress' | 'completed' | 'abandoned'
);
CREATE INDEX IF NOT EXISTS idx_aa_user ON assessment_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_aa_assessment ON assessment_attempts(assessment_id);

CREATE TABLE IF NOT EXISTS assessment_responses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    attempt_id UUID NOT NULL REFERENCES assessment_attempts(id),
    question_id UUID NOT NULL REFERENCES assessment_questions(id),
    selected_option_id UUID REFERENCES assessment_options(id),
    answer_text TEXT,
    is_correct BOOLEAN DEFAULT FALSE,
    score REAL DEFAULT 0,
    answered_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ar_attempt ON assessment_responses(attempt_id);

-- ───────────────────────── CAREER ROLES ─────────────────────────
CREATE TABLE IF NOT EXISTS career_roles (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    avg_salary_min INT,
    avg_salary_max INT,
    experience_required TEXT, -- 'fresher' | '1-3 years' | '3-5 years' | '5+ years'
    education_required TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS role_skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    role_id UUID NOT NULL REFERENCES career_roles(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    required_level REAL DEFAULT 60, -- minimum level needed (0-100)
    weight REAL DEFAULT 1.0, -- importance weight
    is_required BOOLEAN DEFAULT TRUE, -- TRUE = must-have, FALSE = nice-to-have
    UNIQUE(role_id, skill_id)
);

-- ───────────────────────── OPPORTUNITIES ─────────────────────────
CREATE TABLE IF NOT EXISTS opportunities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL, -- 'INTERNSHIP' | 'JOB' | 'APPRENTICESHIP' | 'LIVE_PROJECT' | 'TRAINING' | 'WORKSHOP' | 'MENTORSHIP'
    title TEXT NOT NULL,
    description TEXT,
    education_requirements TEXT,
    experience_requirements TEXT,
    location TEXT,
    remote_allowed BOOLEAN DEFAULT FALSE,
    stipend TEXT,
    salary_min INT,
    salary_max INT,
    duration TEXT,
    deadline TIMESTAMPTZ,
    status TEXT DEFAULT 'ACTIVE', -- 'DRAFT' | 'ACTIVE' | 'CLOSED' | 'EXPIRED'
    max_applicants INT,
    screening_questions JSONB DEFAULT '[]',
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_opp_type ON opportunities(type);
CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opp_deadline ON opportunities(deadline);
CREATE INDEX IF NOT EXISTS idx_opp_org ON opportunities(organization_id);

CREATE TABLE IF NOT EXISTS opportunity_skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    opportunity_id UUID NOT NULL REFERENCES opportunities(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    required_level REAL DEFAULT 60,
    is_required BOOLEAN DEFAULT TRUE, -- TRUE = required, FALSE = preferred
    UNIQUE(opportunity_id, skill_id)
);

-- ───────────────────────── APPLICATIONS ─────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES users(id),
    opportunity_id UUID NOT NULL REFERENCES opportunities(id),
    status TEXT DEFAULT 'APPLIED', -- 'SAVED' | 'APPLIED' | 'UNDER_REVIEW' | 'SHORTLISTED' | 'INTERVIEW' | 'SELECTED' | 'REJECTED'
    cover_letter TEXT,
    screening_answers JSONB DEFAULT '{}',
    match_score REAL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(student_id, opportunity_id)
);
CREATE INDEX IF NOT EXISTS idx_app_student ON applications(student_id);
CREATE INDEX IF NOT EXISTS idx_app_opportunity ON applications(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status);

CREATE TABLE IF NOT EXISTS application_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    application_id UUID NOT NULL REFERENCES applications(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    changed_by TEXT REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ───────────────────────── LEARNING RESOURCES ─────────────────────────
CREATE TABLE IF NOT EXISTS learning_resources (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT,
    type TEXT, -- 'course' | 'article' | 'video' | 'book' | 'project' | 'practice'
    provider TEXT, -- 'NPTEL' | 'Coursera' | 'freeCodeCamp' | 'YouTube' | etc.
    difficulty TEXT, -- 'beginner' | 'intermediate' | 'advanced'
    duration_hours REAL,
    is_free BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resource_skills (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    resource_id UUID NOT NULL REFERENCES learning_resources(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    relevance REAL DEFAULT 1.0 -- 0-1, how well this resource teaches this skill
);

CREATE TABLE IF NOT EXISTS learning_progress (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    resource_id UUID NOT NULL REFERENCES learning_resources(id),
    status TEXT DEFAULT 'NOT_STARTED', -- 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'
    progress_pct REAL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, resource_id)
);

-- ───────────────────────── PORTFOLIO & VERIFICATION ─────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_items (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL, -- 'PROJECT' | 'CERTIFICATION' | 'INTERNSHIP' | 'ACHIEVEMENT' | 'ASSESSMENT'
    title TEXT NOT NULL,
    description TEXT,
    url TEXT,
    skills_used UUID[], -- array of skill IDs
    verified BOOLEAN DEFAULT FALSE,
    verification_source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pi_user ON portfolio_items(user_id);

CREATE TABLE IF NOT EXISTS verification_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    evidence_type TEXT NOT NULL, -- 'ASSESSMENT' | 'CERTIFICATE' | 'INSTITUTION' | 'EMPLOYER' | 'PROJECT' | 'INTERNSHIP'
    evidence_id UUID, -- references the assessment/certificate/etc.
    status TEXT DEFAULT 'PENDING', -- 'SELF_REPORTED' | 'PENDING' | 'VERIFIED' | 'REJECTED' | 'EXPIRED'
    verified_by TEXT REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ───────────────────────── NOTIFICATIONS ─────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL, -- 'MATCH' | 'APPLICATION_STATUS' | 'ASSESSMENT' | 'DEADLINE' | 'MENTOR' | 'SYSTEM'
    title TEXT NOT NULL,
    message TEXT,
    link TEXT,
    read BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(user_id, read);

-- ───────────────────────── AUDIT LOG ─────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    actor_id TEXT REFERENCES users(id),
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    metadata JSONB DEFAULT '{}',
    ip_address TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
```

### 4.2 Existing Table Modifications

```sql
-- Add role and organization to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'STUDENT';
ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS headline TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS career_goal TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS stream TEXT DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_version INT DEFAULT 1;
ALTER TABLE users ADD COLUMN IF NOT EXISTS skill_profile_version INT DEFAULT 1;
```

---

## 5. API Architecture

### 5.1 Route Structure

```
/api/auth/*                    — EXISTING (extend with role support)
/api/veda/*                    — EXISTING (preserve as-is)
/api/colleges/*                — EXISTING (preserve as-is)
/api/scholarships              — EXISTING (preserve as-is)
/api/careers/*                 — EXISTING (preserve as-is)
/api/documents/*               — EXISTING (preserve as-is)
/api/premium/*                 — EXISTING (preserve as-is)
/api/search/*                  — EXISTING (preserve as-is)
/api/scanned/*                 — EXISTING (preserve as-is)

/api/v1/skills                 — NEW: canonical skill taxonomy
/api/v1/students/skill-profile — NEW: student skill profile
/api/v1/assessments            — NEW: assessment engine
/api/v1/career-intelligence    — NEW: skill gap, readiness, roadmap
/api/v1/opportunities          — NEW: opportunity system
/api/v1/applications           — NEW: application tracking
/api/v1/portfolio              — NEW: digital portfolio
/api/v1/verification           — NEW: skill verification
/api/v1/learning               — NEW: learning recommendations
/api/v1/industry               — NEW: industry portal endpoints
/api/v1/institution            — NEW: institution dashboard
/api/v1/notifications          — NEW: notification system
```

### 5.2 Response Envelope

All new endpoints return:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": { "page": 1, "limit": 20, "total": 247, "totalPages": 13 }
}
```

### 5.3 New Backend Files

```
backend/
├── routes/
│   ├── skills.py              — skill taxonomy CRUD
│   ├── assessments.py         — assessment engine
│   ├── career_intelligence.py — gap analysis, readiness, roadmap
│   ├── opportunities.py       — opportunity CRUD + matching
│   ├── applications.py        — application tracking
│   ├── portfolio.py           — portfolio + verification
│   ├── learning.py            — learning resources + progress
│   ├── industry.py            — industry portal endpoints
│   ├── institution.py         — institution dashboard
│   └── notifications.py       — notification CRUD
├── services/
│   ├── skill_matching.py      — deterministic matching engine
│   ├── skill_scoring.py       — assessment → skill score calculation
│   ├── gap_analysis.py        — skill gap computation
│   ├── career_readiness.py    — readiness score calculation
│   └── cache.py               — caching layer
└── middleware/
    └── rbac.py                — role-based access control
```

---

## 6. Matching Algorithm

### 6.1 Deterministic Weighted Scoring

```
skill_compatibility = Σ(student_level[i] / required_level[i] × weight[i]) / Σ(weight[i])
eligibility = education AND experience AND location
readiness = 0.6 × skill_compatibility + 0.15 × eligibility + 0.1 × career_interest + 0.1 × experience_score + 0.05 × location_match
```

### 6.2 Configurable Weights

```python
MATCH_WEIGHTS = {
    "skill_compatibility": 0.60,
    "eligibility": 0.15,
    "career_interest": 0.10,
    "experience": 0.10,
    "location_preference": 0.05
}
```

### 6.3 Explainable Output

Every match score produces:
- Per-skill match status (MATCHED / PARTIAL / MISSING)
- Eligibility breakdown (education / experience / location)
- Missing skills with severity + recommended learning
- Overall confidence level

---

## 7. Frontend Architecture

### 7.1 Navigation (Student)

New tabs added to existing tab bar + fullpage sections:

```
[Home] [Skills] [Opportunities] [Applications] [Veda] [Profile]
```

Fullpage sections:
- `#page-skill-profile` — skill radar, assessment history, verification badges
- `#page-assessments` — take assessments, view results
- `#page-career-intelligence` — target role, gap analysis, roadmap
- `#page-opportunities` — search, filter, match-explain, apply
- `#page-applications` — pipeline tracker
- `#page-portfolio` — public portfolio view
- `#page-industry-dashboard` — industry portal
- `#page-institution-dashboard` — institution analytics

### 7.2 Navigation (Industry)

Bottom tab dock:
```
[Dashboard] [Post] [Candidates] [Applications] [Messages]
```

### 7.3 Navigation (Institution)

Bottom tab dock:
```
[Dashboard] [Students] [Analytics] [Internships] [Reports]
```

### 7.4 New Frontend Files

```
public/src/
├── skills.js           — skill profile UI, radar chart
├── assessments.js      — assessment taking, results
├── career_intel.js     — gap analysis, readiness, roadmap
├── opportunities.js    — opportunity search, match display
├── applications.js     — application tracker
├── portfolio.js        — portfolio view
├── industry.js         — industry dashboard
├── institution.js      — institution dashboard
├── notifications.js    — EXTEND existing
└── charts.js           — chart rendering (CSS-based, no library)
```

### 7.5 Charts (No External Library)

CSS-based bar charts, progress rings, and radar displays using existing CSS variables:

```css
.skill-bar { /* horizontal bar chart */ }
.skill-ring { /* circular progress ring via conic-gradient */ }
.skill-radar { /* CSS polygon radar chart */ }
.stat-card { /* dashboard stat card */ }
```

---

## 8. Caching Strategy

### 8.1 Cache Layers

| Layer | What | TTL | Key Format |
|-------|------|-----|-----------|
| CDN/Browser | Static assets, skill taxonomy | 1 hour | `learnify:skills:all:v{version}` |
| API | Opportunity search | 60-300s | `learnify:opp-search:{hash}` |
| User | Profile, skill profile | On version change | `learnify:user:{id}:skills:v{version}` |
| AI | Career explanations, roadmaps | 1 hour | `learnify:ai:{type}:{hash}` |

### 8.2 Invalidation

```
Student changes skill → profile_version++ → invalidate:
  - skill profile cache
  - career readiness cache
  - recommendation cache
  - opportunity match cache

Assessment completed → skill_profile_version++ → invalidate:
  - skill profile cache
  - career readiness cache
  - recommendation cache

Opportunity updated → opportunity_version++ → invalidate:
  - affected match caches
  - opportunity search cache
```

### 8.3 Implementation

```python
# backend/services/cache.py
import json, hashlib, time

_cache = {}  # In-memory for serverless; replace with Redis for persistent

def get(key): ...
def set(key, value, ttl_seconds): ...
def invalidate_pattern(pattern): ...
def user_cache_key(user_id, resource, version): ...
```

---

## 9. Notification System

### 9.1 Events

| Event | Type | Recipients |
|-------|------|-----------|
| New matching opportunity | `MATCH` | Student |
| Application status changed | `APPLICATION_STATUS` | Student + Industry |
| Assessment completed | `ASSESSMENT` | Student |
| Skill gap changed | `DEVELOPMENT` | Student |
| Interview scheduled | `INTERVIEW` | Student + Industry |
| Certificate verified | `VERIFICATION` | Student |
| Deadline approaching | `DEADLINE` | Student |

### 9.2 Delivery

- **In-app**: Notification table + badge in topbar
- **Email**: Future extension (not MVP)
- **Push**: Future extension (not MVP)

---

## 10. AI Architecture

### 10.1 Deterministic Logic (No LLM)

- Skill scoring from assessment responses
- Skill gap computation
- Career readiness calculation
- Opportunity matching score
- Eligibility checking
- Application status transitions
- Analytics aggregation

### 10.2 LLM Usage (Groq via OpenRouter)

- Career path explanations
- Learning roadmap generation
- Resume improvement suggestions
- Interview preparation tips
- Semantic skill alias resolution
- Natural language career guidance (Veda)

### 10.3 Cost Control

- Cache deterministic results
- Don't call LLM for every page load
- Use LLM only when user explicitly requests explanation
- Background processing for non-blocking operations

---

## 11. Security

- Password hashing via Supabase Auth
- Custom HMAC token signing (existing)
- RBAC middleware on all protected endpoints
- Server-side authorization (never trust frontend)
- Input validation via Pydantic models
- Rate limiting on auth, AI, assessment endpoints
- Audit logging for sensitive actions
- CSRF protection via SameSite cookies
- Secure file upload validation (MIME, size)
- No secrets in frontend code

---

## 12. SIH Demo Seed Data

### 12.1 Students (10)

```yaml
- name: Rahul Sharma
  skills: {Python: 92, SQL: 78, Machine_Learning: 85, Pandas: 88, NumPy: 82, Deep_Learning: 45, PyTorch: 30}
  target_role: AI/ML Engineer
  education: B.Tech CSE, IIT Delhi

- name: Priya Patel
  skills: {React: 88, JavaScript: 90, Node_js: 75, TypeScript: 70, CSS: 85, SQL: 55}
  target_role: Frontend Developer
  education: B.Tech IT, NIT Trichy

- name: Amit Kumar
  skills: {Java: 85, Spring_Boot: 72, SQL: 80, Microservices: 65, Docker: 50, AWS: 40}
  target_role: Backend Developer
  education: B.Tech CSE,BITS Pilani

- name: Sneha Reddy
  skills: {Python: 70, Data_Analysis: 82, SQL: 88, Tableau: 75, Statistics: 80, Excel: 90}
  target_role: Data Analyst
  education: B.Sc Statistics, Delhi University

- name: Vikram Singh
  skills: {JavaScript: 85, React: 80, Python: 65, AWS: 55, Docker: 60, Kubernetes: 35}
  target_role: DevOps Engineer
  education: B.Tech CSE, VIT Vellore

- name: Ananya Das
  skills: {Figma: 90, UI_Design: 88, CSS: 85, HTML: 92, Prototyping: 82, User_Research: 70}
  target_role: UI/UX Designer
  education: B.Des, NID Ahmedabad

- name: Karthik Menon
  skills: {Python: 88, TensorFlow: 75, NLP: 70, Computer_Vision: 65, Statistics: 80, Linear_Algebra: 85}
  target_role: ML Engineer
  education: M.Tech AI, IIT Madras

- name: Deepa Nair
  skills: {SQL: 92, Python: 75, ETL: 80, AWS_Redshift: 65, Spark: 55, Airflow: 50}
  target_role: Data Engineer
  education: B.Tech CSE, NIT Calicut

- name: Rohan Joshi
  skills: {Cybersecurity: 78, Networking: 85, Linux: 80, Python: 70, Cloud_Security: 55, Ethical_Hacking: 72}
  target_role: Security Analyst
  education: B.Tech CSE, Pune University

- name: Meera Gupta
  skills: {Product_Management: 82, SQL: 70, Analytics: 78, Wireframing: 85, Market_Research: 80, Communication: 88}
  target_role: Product Manager
  education: MBA, IIM Bangalore
```

### 12.2 Companies (5)

```yaml
- name: TechVista Solutions
  industry: IT Services
  opportunities: 5

- name: DataFlow Analytics
  industry: Data & Analytics
  opportunities: 4

- name: CloudNexa Technologies
  industry: Cloud & DevOps
  opportunities: 3

- name: InnovateLabs AI
  industry: AI/ML
  opportunities: 4

- name: SecureNet Systems
  industry: Cybersecurity
  opportunities: 3
```

### 12.3 Opportunities (20)

Mix of internships, jobs, live projects, and training programs requiring different skill combinations to demonstrate matching.

### 12.4 Assessments (5)

```yaml
- title: Python Programming Fundamentals
  skills: [Python, Data_Structures, Problem_Solving]
  questions: 15

- title: SQL & Database Design
  skills: [SQL, Database_Design, Query_Optimization]
  questions: 12

- title: Machine Learning Basics
  skills: [Machine_Learning, Statistics, Python]
  questions: 15

- title: Web Development Fundamentals
  skills: [HTML, CSS, JavaScript, React]
  questions: 12

- title: Data Analysis with Python
  skills: [Python, Pandas, NumPy, Data_Visualization]
  questions: 12
```

### 12.5 Learning Resources (10)

Map to skills for gap-closure recommendations.

---

## 13. E2E Demo Flow (SIH Judging)

### Step 1: Student Login
- Login as `rahul@demo.com` / `demo123456`

### Step 2: Skill Assessment
- Open Assessments → Take "Python Programming Fundamentals"
- Complete 15 questions → See skill-level scores

### Step 3: Skill Profile
- View skill radar chart showing Python 92%, SQL 78%, ML 85%, etc.

### Step 4: Career Intelligence
- Select "AI/ML Engineer" as target role
- See: Career Readiness 78/100
- See: Skill Gaps — PyTorch (30%), Deep Learning (45%)

### Step 5: Opportunity Matching
- Browse opportunities → "AI/ML Intern at InnovateLabs AI" — 87% match
- Click to see explainable match:
  - Python ✓ Required / Strong
  - ML ✓ Required / Strong
  - Pandas ✓ Required / Strong
  - SQL △ Required / Developing
  - PyTorch ✗ Required / Missing
- See recommended learning resources for PyTorch

### Step 6: Apply
- Click Apply → Application tracked

### Step 7: Industry View
- Login as industry recruiter
- See recommended candidates — Rahul appears at 87%
- Click to see full skill profile + match explanation
- Shortlist Rahul

### Step 8: Institution View
- Login as institution admin
- Dashboard shows:
  - 85% students have Python skill
  - Top skill gap: Cloud Computing (44%)
  - 12 internships active
  - Placement readiness: 62% ready

---

## 14. Existing Features Preserved

| Feature | Status | Notes |
|---------|--------|-------|
| Veda AI Chatbot | ✅ PRESERVED | Streaming, history, profile extraction |
| College Explorer | ✅ PRESERVED | 700+ colleges, filters, reviews |
| Career Paths | ✅ PRESERVED | 107+ careers, 12 domains, quiz |
| Scholarship Finder | ✅ PRESERVED | Seed + live web search |
| Resume Builder | ✅ PRESERVED | AI-powered |
| Study Planner | ✅ PRESERVED | Subject/week tracker |
| Calculator | ✅ PRESERVED | Standard calc + converter |
| Writing Enhancer | ✅ PRESERVED | AI paraphrase |
| Quiz Generator | ✅ PRESERVED | AI-generated MCQs |
| Multilingual | ✅ PRESERVED | EN/HI/BN/TA |
| Premium/Razorpay | ✅ PRESERVED | ₹5 trial → ₹37/month |
| Document Upload | ✅ PRESERVED | Marksheet OCR |
| Global Search | ✅ PRESERVED | Careers, colleges, companies |
| Notifications | ✅ PRESERVED | In-app |
| Profile Management | ✅ PRESERVED | SGPA tracker, academic records |

---

## 15. Implementation Phases

### Phase 1: Database Schema + Skill Taxonomy
- Extend schema.sql with all new tables
- Create skills.py route
- Seed 30+ canonical skills with hierarchy and aliases
- Test: CRUD skills via API

### Phase 2: Auth + RBAC
- Add role field to users
- Create user_roles table
- Add RBAC middleware
- Extend auth.py with role support
- Frontend: role-based navigation rendering

### Phase 3: Student Skill Profile
- Create user_skills CRUD
- Skill profile aggregation logic
- Skill radar chart (CSS-based)
- Profile version tracking

### Phase 4: Assessment Engine
- Assessment CRUD
- Question → skill mapping
- Attempt management
- Per-skill scoring algorithm
- Assessment UI with timer

### Phase 5: Skill Gap + Career Intelligence
- Career role + role_skills tables
- Gap analysis algorithm
- Career readiness scoring
- Explainable output format
- Career intelligence page

### Phase 6: Opportunity System
- Opportunity CRUD
- Opportunity → skill mapping
- Explainable matching engine
- Opportunity search with filters
- Opportunity detail with match explanation

### Phase 7: Application Tracking
- Application CRUD with idempotency
- Status pipeline with events
- Application timeline UI
- Industry: candidate recommendation view

### Phase 8: Industry Portal
- Industry dashboard
- Post opportunity wizard
- Candidate matching view
- Shortlist/reject actions

### Phase 9: Portfolio + Verification
- Portfolio item CRUD
- Verification request flow
- Public portfolio page
- Verification badges

### Phase 10: Learning Resources
- Resource CRUD
- Resource → skill mapping
- Learning progress tracking
- Gap → resource recommendation

### Phase 11: Institution Dashboard
- Analytics aggregation
- Skill readiness distribution
- Department comparison
- Industry demand from opportunity data

### Phase 12: Notifications
- Notification CRUD
- Event-driven creation
- Badge counter
- Mark as read

### Phase 13: Caching + Performance
- Cache layer implementation
- TTL-based caching
- Version-based invalidation
- Pagination on all list endpoints

### Phase 14: SIH Demo Data
- Seed all demo data
- Create demo accounts
- Test full E2E flow

### Phase 15: Testing + Security
- Unit tests for scoring algorithms
- Integration tests for key flows
- RBAC enforcement testing
- Input validation hardening

### Phase 16: Deployment
- Vercel deployment verification
- Environment variable documentation
- Migration instructions
- Rollback plan

---

## 16. Known Limitations (MVP)

1. No real-time WebSocket notifications (in-app polling instead)
2. No email notifications (in-app only)
3. No push notifications
4. No vector similarity matching (deterministic weighted scoring only)
5. No background job queue (synchronous processing)
6. No Redis caching (in-memory only, resets on cold start)
7. No file antivirus scanning
8. No signed URLs for private documents (auth-gated API)
9. Charts are CSS-based, not interactive
10. No PWA offline support for new features

---

## 17. File Structure (After Transformation)

```
Learnify/
├── MASTER_PLAN.md
├── package.json
├── requirements.txt
├── .env.example
├── public/
│   ├── index.html              — EXTENDED with new sections
│   ├── styles.css              — EXTENDED with new components
│   ├── assets/
│   └── src/
│       ├── app.js              — EXTENDED (role-based nav)
│       ├── auth.js             — PRESERVED
│       ├── veda.js             — PRESERVED
│       ├── career.js           — PRESERVED
│       ├── careers.js          — PRESERVED
│       ├── profile.js          — EXTENDED (role display)
│       ├── premium.js          — PRESERVED
│       ├── notifications.js    — EXTENDED
│       ├── tools.js            — PRESERVED
│       ├── i18n.js             — EXTENDED (new keys)
│       ├── icons.js            — PRESERVED
│       ├── sound.js            — PRESERVED
│       ├── utils.js            — EXTENDED (role helpers)
│       ├── skills.js           — NEW
│       ├── assessments.js      — NEW
│       ├── career_intel.js     — NEW
│       ├── opportunities.js    — NEW
│       ├── applications.js     — NEW
│       ├── portfolio.js        — NEW
│       ├── industry.js         — NEW
│       ├── institution.js      — NEW
│       └── charts.js           — NEW
├── backend/
│   ├── main.py                 — EXTENDED (new routers)
│   ├── routes/
│   │   ├── auth.py             — EXTENDED (role support)
│   │   ├── veda.py             — PRESERVED
│   │   ├── colleges.py         — PRESERVED
│   │   ├── careers.py          — PRESERVED
│   │   ├── documents.py        — PRESERVED
│   │   ├── premium.py          — PRESERVED
│   │   ├── search.py           — PRESERVED
│   │   ├── scanned.py          — PRESERVED
│   │   ├── skills.py           — NEW
│   │   ├── assessments.py      — NEW
│   │   ├── career_intelligence.py — NEW
│   │   ├── opportunities.py    — NEW
│   │   ├── applications.py     — NEW
│   │   ├── portfolio.py        — NEW
│   │   ├── learning.py         — NEW
│   │   ├── industry.py         — NEW
│   │   ├── institution.py      — NEW
│   │   └── notifications.py    — NEW
│   ├── services/
│   │   ├── ai.py               — PRESERVED
│   │   ├── rag.py              — PRESERVED
│   │   ├── memory.py           — PRESERVED
│   │   ├── detector.py         — PRESERVED
│   │   ├── search.py           — PRESERVED
│   │   ├── web.py              — PRESERVED
│   │   ├── uid.py              — PRESERVED
│   │   ├── local_auth.py       — PRESERVED
│   │   ├── skill_matching.py   — NEW
│   │   ├── skill_scoring.py    — NEW
│   │   ├── gap_analysis.py     — NEW
│   │   ├── career_readiness.py — NEW
│   │   └── cache.py            — NEW
│   ├── middleware/
│   │   └── rbac.py             — NEW
│   └── database/
│       ├── client.py           — PRESERVED
│       ├── schema.sql          — EXTENDED
│       ├── seed.py             — PRESERVED
│       ├── seed_careers.py     — PRESERVED
│       ├── seed_companies.py   — PRESERVED
│       ├── seed_skills.py      — NEW
│       ├── seed_assessments.py — NEW
│       ├── seed_opportunities.py — NEW
│       ├── supabase_db.py      — PRESERVED
│       └── local_db.py         — PRESERVED
└── api/
    └── index.py                — PRESERVED (Vercel entry)
```

---

*This plan is the single source of truth for the Learnify SIH transformation. All implementation decisions must reference this document.*
