# Learnify - Master Plan

## 1. Project Overview

**Learnify** is an AI-powered student platform for Indian students. It helps students discover the best college, career path, and stream through a personalized AI assistant called **Veda**, along with tools, college data, and scholarship/loan information.

### Core Mission
> Provide a single platform where Indian students can easily find the best college, stream, and career path — powered by AI, backed by real data, and personalized to each student.

---

## 2. Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Frontend** | Vanilla HTML/CSS/JS + TailwindCSS | Lightest possible, best looks, minimal design |
| **Backend** | Python FastAPI | Async-first, fast, auto OpenAPI docs |
| **Database** | Supabase (PostgreSQL + pgvector) | Free tier, auth + storage + vector DB in one |
| **AI** | OpenRouter (free models) | Llama 3.1 8B, Mistral, Nemotron — all free |
| **Auth** | Supabase Auth | Google OAuth + Email/Password, free tier |
| **Payments** | Razorpay | ₹5 trial/week → ₹37/month subscription |
| **Deploy** | Vercel | Free tier, instant deploys, edge network |
| **Context Memory** | Graphify + pgvector | Knowledge graph + vector similarity search |

---

## 3. Pages / Tabs

### 3.1 HOME
- Writing Enhancer (AI paraphrase/improve)
- College Quick Search
- Calculator & Unit Converter
- Resume Builder
- Scholarship Finder (quick)
- Quick Links to Veda, Career

### 3.2 VEDA (AI Chatbot)
- Login required
- Preset situational questions (MCQ + Descriptive + Situation-based)
- Max 10 questions for convenience
- Personalized responses based on:
  - User profile data
  - Uploaded documents (marksheets)
  - College database context
  - Career criteria data
- Multidimensional memory system (Graphify + pgvector)
- Two OpenRouter APIs: one for chat, one for analysis

### 3.3 CAREER
- College dropdown (All India — every college)
- NIRF Rankings (year-wise)
- Placement data (avg package, top recruiters)
- Government scholarships + eligibility
- Education loans (SBI, BoB, etc.)
- Minimum 12th marks criteria for top companies
- Student reviews (Google Reviews + other sources)
- Pro/Cons clearly distinguished
- Private/Govt tags on all colleges

### 3.4 PROFILE
- Basic details (name, address, qualification)
- Language preference (English/Hindi/Bengali)
- Document upload/management
- SGPA/CGPA tracking
- College/School selection from dropdown
- Premium badge display
- Document update from profile

---

## 4. Veda AI Architecture

### 4.1 Preset Questions System
- MCQ questions
- Descriptive (short answer)
- Situation-based scenarios
- Under 10 questions max for convenience
- Easy to feed — short, clear answers

### 4.2 RAG Pipeline
1. **Document Ingestion**: Upload → AI-generated check (ZeroGPT-style) → Extract data points
2. **Indexing**: Chunk → Embed → Store in pgvector
3. **Retrieval**: User query → Similarity search → Top-k context
4. **Generation**: Context + User data → Free LLM via OpenRouter → Response

### 4.3 Multidimensional Memory
- **Layer 1**: User personal data (profile, marksheets, SGPA/CGPA)
- **Layer 2**: College data (NIRF, placements, reviews)
- **Layer 3**: Career criteria (company requirements, scholarships)
- **Layer 4**: Conversation history (chat memory)
- **Graphify**: Knowledge graph for relational memory between concepts

### 4.4 Two OpenRouter APIs
- **API 1**: Chat/conversation (Llama 3.1 8B)
- **API 2**: Analysis/document processing (Mistral)

---

## 5. Authentication

- **Google OAuth** — one-click login via Supabase
- **Email/Password** — fallback option
- **Onboarding**: Name, preferred language, current grade
- **Language**: English (default), Hindi, Bengali
- **Footer language switcher** always available

---

## 6. College Database

### 6.1 Data Sources
- NIRF official rankings
- College placement cells
- Government scholarship portals
- Google Reviews (scraped/aggregated)
- Student review sites

### 6.2 Data Fields Per College
- Name, location, type (Private/Govt)
- Streams offered
- NIRF ranking (year-wise)
- Placement stats (percentage, avg salary, top companies)
- Scholarships available + eligibility
- Govt loan facilities + application process
- Minimum 12th marks requirements (TCS, Infosys, Wipro, etc.)
- Student reviews with pros/cons
- Google rating

### 6.3 Search
- Dropdown selection (All India)
- Type-ahead for fast selection
- Filter: private/govt, location, streams
- No college left out

---

## 7. Premium Features

### 7.1 Free Tier
- College search & basic info
- Veda AI chat (limited tokens/month)
- Basic profile setup
- 3 document uploads max
- Career criteria overview

### 7.2 Premium Tier (₹37/month)
- **First week trial: ₹5 (autopay)**
- ₹5 non-refundable
- Unlimited Veda chat tokens
- Unlimited document uploads
- Higher-priority LLM models
- Advanced profile analytics
- Personalized career roadmap
- Export profile data
- Priority support
- Premium badge + cool tag on profile

### 7.3 Payment Flow
- Razorpay checkout (₹5 trial)
- Auto-renew at ₹37/month after 7 days
- Subscription management in profile
- Payment page: https://rzp.io/rzp/Mk9iZLn

---

## 8. Document Processing

### 8.1 Upload Flow
1. User uploads document (PDF/image) via profile
2. Server receives → metadata scan (AI-generated detection)
3. If flagged synthetic → notify user to re-upload
4. If clean → extract data points (SGPA, CGPA, stream, marks)
5. Store extracted data (not raw text) in PostgreSQL
6. Vectorize for RAG context

### 8.2 AI-Generated Detection
- Metadata analysis (ZeroGPT-style checks)
- Document type validation (PDF/JPG/PNG)
- File size limits (2MB default)
- No synthetic/altereds accepted

### 8.3 User Actions
- Upload from profile tab
- Update documents anytime
- Notification if issue detected
- Re-upload with proper document

---

## 9. Error Handling

- **Per-action error boundaries**: Each page/component has try/catch
- **User-friendly popups**: Only for actual issues, not every small thing
- **Never crash**: Graceful degradation — if AI fails, show basic info
- **Validation errors**: Clear inline messages
- **Network awareness**: Offline/online detection
- **Logging**: Server-side silent, user-visible only when critical

---

## 10. Multilingual Support

- **Languages**: English (default), Hindi, Bengali
- **Signup question**: "Select your preferred language"
- **Footer language switch**: Always available
- **AI responses**: System prompt includes user language preference
- **College data**: English names, translations optional

---

## 11. Subscription Model

| Feature | Free | Premium |
|---------|------|---------|
| College Search | ✅ | ✅ |
| Veda Chat | Limited tokens | Unlimited |
| Document Uploads | 3 max | Unlimited |
| Career Roadmap | Basic | Advanced |
| Profile Analytics | Basic | Advanced |
| Export Data | ❌ | ✅ |
| Priority Support | ❌ | ✅ |
| Premium Badge | ❌ | ✅ |
| Price | ₹0 | ₹5 trial/week → ₹37/month |

---

## 12. Development Roadmap

### Phase 1: Foundation (Week 1-2)
- [x] Project setup & structure
- [ ] Frontend HTML/CSS design (4 tabs)
- [ ] Auth (Google OAuth + Email/Password)
- [ ] Basic college database

### Phase 2: Core Features (Week 3-4)
- [ ] Veda AI chat with preset questions
- [ ] College dropdown with data
- [ ] NIRF rankings integration
- [ ] Profile management

### Phase 3: Advanced Features (Week 5-6)
- [ ] RAG pipeline for Veda
- [ ] Document upload & processing
- [ ] AI-generated detection
- [ ] Multidimensional memory system

### Phase 4: Premium & Polish (Week 7-8)
- [ ] Razorpay integration
- [ ] Premium features unlock
- [ ] Error handling & crash prevention
- [ ] Multilingual support (Hindi/Bengali)
- [ ] Student reviews integration
- [ ] Scholarship & loan data

### Phase 5: Deploy & Launch (Week 9)
- [ ] Vercel deployment
- [ ] Testing & QA
- [ ] Performance optimization
- [ ] Launch

---

## 13. File Structure

```
Learnify/
├── logo.jpeg
├── MASTER_PLAN.md
├── public/
│   ├── index.html          # Main entry point
│   ├── styles.css          # Custom styles
│   └── assets/
│       └── logo.jpeg
├── src/
│   ├── app.js              # Main app logic
│   ├── auth.js             # Authentication
│   ├── veda.js             # Veda AI chat
│   ├── career.js           # Career/College data
│   ├── profile.js          # Profile management
│   ├── premium.js          # Premium/Subscription
│   └── utils.js            # Helpers
├── backend/
│   ├── main.py             # FastAPI entry
│   ├── routes/
│   │   ├── auth.py
│   │   ├── veda.py
│   │   ├── colleges.py
│   │   ├── documents.py
│   │   └── premium.py
│   ├── services/
│   │   ├── ai.py           # OpenRouter integration
│   │   ├── rag.py          # RAG pipeline
│   │   ├── memory.py       # Multidimensional memory
│   │   └── detector.py     # AI-generated doc detection
│   └── database/
│       ├── schema.sql
│       └── seed.py         # College data seeding
├── requirements.txt
├── package.json
└── .env.example
```

---

## 14. Environment Variables (.env)

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_key

# OpenRouter (Two APIs)
OPENROUTER_API_KEY_1=sk-or-...  # For chat
OPENROUTER_API_KEY_2=sk-or-...  # For analysis

# Razorpay
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...

# App
APP_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

---

## 15. Key Design Principles

1. **Minimal & Clean**: Dark theme, shadcn/ui style, minimal clutter
2. **Mobile-First**: Responsive on all devices
3. **Fast**: No heavy frameworks, lightweight vanilla JS + TailwindCSS
4. **Error-Safe**: Every action has error handling, site never crashes
5. **Personalized**: AI adapts to each user's data and preferences
6. **Data-Backed**: Real college data, real reviews, real rankings
7. **India-First**: All Indian colleges, scholarships, loans, criteria
