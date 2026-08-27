# Learnify

AI-powered study companion for Indian students — college discovery, career guidance, scholarships, and a personalized AI chatbot (**Veda**).

## Stack
- **Frontend:** Vanilla HTML/CSS/JS (ES modules), no build step
- **Backend:** Python FastAPI
- **AI:** OpenRouter (two keys — chat + document analysis) on a single free model `nvidia/nemotron-3.5-lightning:free`
- **Auth / DB:** Supabase (PostgreSQL) — *configure to enable login & persistence*
- **Payments:** Razorpay — *configure to enable the premium upgrade*

## Run locally
```bash
# 1. Backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in Supabase / Razorpay (OpenRouter keys already set)
uvicorn backend.main:app --port 8000

# 2. Frontend — open public/index.html via the running backend
#    visit http://127.0.0.1:8000/   (root serves the SPA)
```

## What works now
- **Home** — Writing Enhancer, Calculator & Unit Converter, Resume Builder (modals); quick links to Colleges / Scholarships.
- **Veda** — real AI chat (login required); uses your OpenRouter key.
- **Career** — 9 seeded colleges (NIRF, packages, recruiters, min 12th %), 4 scholarships, education loans, student reviews; govt/private filters.
- **Profile** — real `/auth/me`, document upload with synthetic-content detection, language preference, logout.
- **Auth** — login / sign-up modal wired to Supabase.
- **Premium** — Razorpay checkout modal; shows a clear message when keys are absent (no fake success).

## API
`/api/auth/*` (register, login, me) · `/api/veda/chat` · `/api/colleges`, `/api/colleges/{id}`, `/api/scholarships` · `/api/documents/upload`, `/api/documents` · `/api/premium/checkout`, `/api/premium/webhook` · `/health`

## Notes
- Without Supabase keys, auth returns `503` and colleges/scholarships fall back to the seeded dataset.
- Without Razorpay keys, the premium checkout returns `503` (no mock orders).
- Apply `backend/database/schema.sql` in Supabase, then `python -m backend.database.seed` to load colleges & scholarships.
