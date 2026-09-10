"""
Seed demo opportunities with skill requirements.

Usage:
    python -m backend.database.seed_opportunities

Run seed_skills.py FIRST so skills and organizations exist.
"""

import os
from datetime import datetime, timedelta

from backend.database.client import db_available, get_client

# ─── Organizations ────────────────────────────────────────────────────────
ORGANIZATIONS = [
    {
        "name": "TechVista Solutions",
        "type": "COMPANY",
        "industry": "IT Services",
        "description": "Full-service IT consulting company specializing in enterprise solutions, cloud migration, and digital transformation.",
        "website": "https://techvista.example.com",
        "size": "201-500",
        "location": "Bangalore",
    },
    {
        "name": "DataFlow Analytics",
        "type": "COMPANY",
        "industry": "Data & Analytics",
        "description": "Data analytics and business intelligence firm helping enterprises make data-driven decisions.",
        "website": "https://dataflow.example.com",
        "size": "51-200",
        "location": "Hyderabad",
    },
    {
        "name": "CloudNexa Technologies",
        "type": "COMPANY",
        "industry": "Cloud & DevOps",
        "description": "Cloud infrastructure and DevOps automation company serving startups to enterprises.",
        "website": "https://cloudnexa.example.com",
        "size": "51-200",
        "location": "Pune",
    },
    {
        "name": "InnovateLabs AI",
        "type": "COMPANY",
        "industry": "AI/ML",
        "description": "AI-first product company building cutting-edge ML solutions for healthcare, finance, and retail.",
        "website": "https://innovatelabs.example.com",
        "size": "11-50",
        "location": "Mumbai",
    },
    {
        "name": "SecureNet Systems",
        "type": "COMPANY",
        "industry": "Cybersecurity",
        "description": "Cybersecurity firm providing SOC, penetration testing, and compliance services.",
        "website": "https://securenet.example.com",
        "size": "51-200",
        "location": "Delhi",
    },
]

# ─── Skill name → org-relative index mapping ──────────────────────────────
# This seed file assumes skill_skills.py has already seeded the taxonomy.
# We reference skill names; the seed function resolves them to IDs.


# ─── Opportunities ────────────────────────────────────────────────────────
OPPORTUNITIES = [
    # TechVista Solutions (org index 0)
    {
        "org_idx": 0,
        "type": "INTERNSHIP",
        "title": "Full Stack Web Development Intern",
        "description": "Work on building and maintaining enterprise web applications using React and Node.js. You will collaborate with senior developers on real client projects.",
        "education_requirements": "B.Tech/B.Sc CS or equivalent",
        "experience_requirements": "fresher",
        "location": "Bangalore",
        "remote_allowed": True,
        "stipend": "₹15,000/month",
        "duration": "6 months",
        "deadline_days": 30,
        "skills": {
            "JavaScript": 70,
            "React": 60,
            "Node.js": 50,
            "HTML": 70,
            "CSS": 60,
            "SQL": 40,
        },
    },
    {
        "org_idx": 0,
        "type": "JOB",
        "title": "Junior Backend Developer",
        "description": "Join our backend team to build scalable APIs and microservices. Work with Python/Django and PostgreSQL.",
        "education_requirements": "B.Tech CS",
        "experience_requirements": "0-1 years",
        "location": "Bangalore",
        "remote_allowed": False,
        "salary_min": 400000,
        "salary_max": 700000,
        "skills": {
            "Python": 70,
            "Django": 50,
            "SQL": 60,
            "REST API": 50,
            "Docker": 30,
        },
    },
    {
        "org_idx": 0,
        "type": "TRAINING",
        "title": "Cloud Computing Bootcamp",
        "description": "Intensive 4-week training on AWS fundamentals, Docker, and CI/CD. Includes hands-on labs and certification prep.",
        "education_requirements": "Any graduate",
        "experience_requirements": "fresher",
        "location": "Bangalore",
        "remote_allowed": True,
        "stipend": "Free",
        "duration": "4 weeks",
        "deadline_days": 20,
        "skills": {
            "AWS": 40,
            "Docker": 40,
            "Linux": 50,
            "CI/CD": 30,
        },
    },
    # DataFlow Analytics (org index 1)
    {
        "org_idx": 1,
        "type": "INTERNSHIP",
        "title": "Data Analytics Intern",
        "description": "Analyze real-world datasets, build dashboards, and support business intelligence projects using Python and SQL.",
        "education_requirements": "B.Sc/B.Tech with statistics/data science background",
        "experience_requirements": "fresher",
        "location": "Hyderabad",
        "remote_allowed": True,
        "stipend": "₹12,000/month",
        "duration": "3 months",
        "deadline_days": 25,
        "skills": {
            "Python": 60,
            "SQL": 70,
            "Pandas": 50,
            "Excel": 60,
            "Data Visualization": 40,
            "Statistics": 50,
        },
    },
    {
        "org_idx": 1,
        "type": "JOB",
        "title": "Junior Data Analyst",
        "description": "Build reports, dashboards, and analytical models to drive business decisions. Work with large datasets and BI tools.",
        "education_requirements": "B.Sc Statistics/Math or B.Tech",
        "experience_requirements": "0-2 years",
        "location": "Hyderabad",
        "remote_allowed": False,
        "salary_min": 350000,
        "salary_max": 600000,
        "skills": {
            "SQL": 80,
            "Python": 60,
            "Tableau": 50,
            "Statistics": 60,
            "Data Analysis": 70,
            "Excel": 50,
        },
    },
    {
        "org_idx": 1,
        "type": "LIVE_PROJECT",
        "title": "Customer Churn Prediction Project",
        "description": "Work with our data science team on a live project predicting customer churn using ML models on real business data.",
        "education_requirements": "B.Tech/B.Sc with ML exposure",
        "experience_requirements": "fresher",
        "location": "Hyderabad",
        "remote_allowed": True,
        "stipend": "₹10,000",
        "duration": "2 months",
        "deadline_days": 15,
        "skills": {
            "Python": 70,
            "Machine Learning": 60,
            "Pandas": 60,
            "Statistics": 50,
            "SQL": 40,
        },
    },
    # CloudNexa Technologies (org index 2)
    {
        "org_idx": 2,
        "type": "INTERNSHIP",
        "title": "DevOps Engineering Intern",
        "description": "Learn and work on CI/CD pipelines, Docker containerization, Kubernetes deployments, and cloud infrastructure.",
        "education_requirements": "B.Tech CS/IT",
        "experience_requirements": "fresher",
        "location": "Pune",
        "remote_allowed": True,
        "stipend": "₹18,000/month",
        "duration": "6 months",
        "deadline_days": 30,
        "skills": {
            "Docker": 50,
            "Linux": 60,
            "AWS": 40,
            "CI/CD": 40,
            "Python": 40,
            "Kubernetes": 20,
        },
    },
    {
        "org_idx": 2,
        "type": "JOB",
        "title": "Cloud Engineer",
        "description": "Design, deploy, and manage cloud infrastructure on AWS/Azure. Automate infrastructure with Terraform and Ansible.",
        "education_requirements": "B.Tech with cloud certification preferred",
        "experience_requirements": "1-3 years",
        "location": "Pune",
        "remote_allowed": True,
        "salary_min": 500000,
        "salary_max": 900000,
        "skills": {
            "AWS": 70,
            "Docker": 60,
            "Kubernetes": 50,
            "Terraform": 40,
            "Linux": 70,
            "CI/CD": 60,
        },
    },
    {
        "org_idx": 2,
        "type": "WORKSHOP",
        "title": "Kubernetes Masterclass",
        "description": "Hands-on workshop covering K8s fundamentals, deployments, services, and Helm charts. Led by industry practitioners.",
        "education_requirements": "Any graduate with Linux basics",
        "experience_requirements": "fresher",
        "location": "Pune",
        "remote_allowed": True,
        "stipend": "Free",
        "duration": "2 days",
        "deadline_days": 10,
        "skills": {
            "Kubernetes": 30,
            "Docker": 40,
            "Linux": 30,
        },
    },
    # InnovateLabs AI (org index 3)
    {
        "org_idx": 3,
        "type": "INTERNSHIP",
        "title": "ML Engineering Intern",
        "description": "Build and train ML models for real-world applications. Work with PyTorch, TensorFlow, and production ML pipelines.",
        "education_requirements": "B.Tech/MSc CS with ML coursework",
        "experience_requirements": "fresher",
        "location": "Mumbai",
        "remote_allowed": True,
        "stipend": "₹20,000/month",
        "duration": "6 months",
        "deadline_days": 20,
        "skills": {
            "Python": 80,
            "Machine Learning": 60,
            "PyTorch": 40,
            "TensorFlow": 40,
            "NumPy": 50,
            "Pandas": 50,
        },
    },
    {
        "org_idx": 3,
        "type": "JOB",
        "title": "Junior ML Engineer",
        "description": "Deploy ML models to production, optimize inference, and build data pipelines. Work with cutting-edge AI products.",
        "education_requirements": "B.Tech/MSc with strong ML portfolio",
        "experience_requirements": "0-2 years",
        "location": "Mumbai",
        "remote_allowed": False,
        "salary_min": 600000,
        "salary_max": 1200000,
        "skills": {
            "Python": 80,
            "Machine Learning": 70,
            "Deep Learning": 50,
            "PyTorch": 60,
            "SQL": 40,
            "Docker": 30,
        },
    },
    {
        "org_idx": 3,
        "type": "LIVE_PROJECT",
        "title": "NLP Chatbot Development",
        "description": "Build an NLP-powered chatbot for customer support using transformers and fine-tuning techniques.",
        "education_requirements": "B.Tech/MSc with NLP interest",
        "experience_requirements": "fresher",
        "location": "Mumbai",
        "remote_allowed": True,
        "stipend": "₹15,000",
        "duration": "3 months",
        "deadline_days": 15,
        "skills": {
            "Python": 70,
            "Natural Language Processing": 50,
            "Machine Learning": 50,
            "PyTorch": 40,
        },
    },
    {
        "org_idx": 3,
        "type": "MENTORSHIP",
        "title": "AI Career Mentorship Program",
        "description": "1-on-1 mentorship with AI researchers. Get guidance on ML career paths, portfolio building, and interview prep.",
        "education_requirements": "CS students or recent graduates",
        "experience_requirements": "fresher",
        "location": "Mumbai",
        "remote_allowed": True,
        "stipend": "Free",
        "duration": "1 month",
        "deadline_days": 10,
        "skills": {
            "Machine Learning": 30,
            "Python": 30,
        },
    },
    # SecureNet Systems (org index 4)
    {
        "org_idx": 4,
        "type": "INTERNSHIP",
        "title": "Cybersecurity Intern",
        "description": "Assist the SOC team with threat monitoring, vulnerability scanning, and security incident analysis.",
        "education_requirements": "B.Tech CS with cybersecurity interest",
        "experience_requirements": "fresher",
        "location": "Delhi",
        "remote_allowed": False,
        "stipend": "₹15,000/month",
        "duration": "6 months",
        "deadline_days": 25,
        "skills": {
            "Cybersecurity": 40,
            "Linux": 50,
            "Networking": 50,
            "Python": 40,
        },
    },
    {
        "org_idx": 4,
        "type": "JOB",
        "title": "Security Analyst",
        "description": "Monitor security events, investigate incidents, and conduct vulnerability assessments for enterprise clients.",
        "education_requirements": "B.Tech CS/Security certifications preferred",
        "experience_requirements": "1-3 years",
        "location": "Delhi",
        "remote_allowed": False,
        "salary_min": 450000,
        "salary_max": 800000,
        "skills": {
            "Cybersecurity": 70,
            "Networking": 60,
            "Linux": 60,
            "Ethical Hacking": 50,
            "Python": 50,
        },
    },
    {
        "org_idx": 4,
        "type": "TRAINING",
        "title": "Ethical Hacking Fundamentals",
        "description": "Learn penetration testing, vulnerability assessment, and security tool usage in a hands-on lab environment.",
        "education_requirements": "Any graduate with IT basics",
        "experience_requirements": "fresher",
        "location": "Delhi",
        "remote_allowed": True,
        "stipend": "₹5,000",
        "duration": "3 weeks",
        "deadline_days": 15,
        "skills": {
            "Ethical Hacking": 30,
            "Linux": 40,
            "Networking": 40,
            "Cybersecurity": 30,
        },
    },
]


def seed():
    if not db_available():
        print("[seed_opportunities] Supabase not configured — printing seed data only.")
        print(f"Organizations: {len(ORGANIZATIONS)}")
        print(f"Opportunities: {len(OPPORTUNITIES)}")
        return

    client = get_client()

    # 1. Upsert organizations
    org_ids = {}
    for org in ORGANIZATIONS:
        try:
            existing = (
                client.table("organizations")
                .select("id")
                .eq("name", org["name"])
                .limit(1)
                .execute()
            )
            if existing.data:
                org_ids[org["name"]] = existing.data[0]["id"]
            else:
                res = client.table("organizations").insert(org).execute()
                org_ids[org["name"]] = res.data[0]["id"]
        except Exception as e:
            print(f"[seed_opportunities] org '{org['name']}' error: {e}")
    print(f"[seed_opportunities] {len(org_ids)} organizations upserted")

    # 2. Build skill name → id map
    skill_map = {}
    try:
        res = client.table("skills").select("id, name").execute()
        for row in res.data or []:
            skill_map[row["name"]] = row["id"]
    except Exception as e:
        print(f"[seed_opportunities] could not load skills: {e}")
        print("Run seed_skills.py first!")
        return

    # 3. Create demo user for created_by
    demo_user_id = "demo001"

    # 4. Upsert opportunities
    opp_count = 0
    for opp in OPPORTUNITIES:
        org_name = list(ORGANIZATIONS)[opp["org_idx"]]["name"]
        org_id = org_ids.get(org_name)
        if not org_id:
            continue

        title = opp["title"]
        try:
            existing = (
                client.table("opportunities")
                .select("id")
                .eq("title", title)
                .eq("organization_id", org_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue
        except Exception:
            pass

        deadline = (
            datetime.utcnow() + timedelta(days=opp.get("deadline_days", 30))
        ).isoformat()

        opp_row = {
            "organization_id": org_id,
            "created_by": demo_user_id,
            "type": opp["type"],
            "title": title,
            "description": opp["description"],
            "education_requirements": opp.get("education_requirements", ""),
            "experience_requirements": opp.get("experience_requirements", ""),
            "location": opp.get("location", ""),
            "remote_allowed": opp.get("remote_allowed", False),
            "stipend": opp.get("stipend", ""),
            "salary_min": opp.get("salary_min"),
            "salary_max": opp.get("salary_max"),
            "duration": opp.get("duration", ""),
            "deadline": deadline,
            "status": "ACTIVE",
        }

        try:
            res = client.table("opportunities").insert(opp_row).execute()
            opp_id = res.data[0]["id"]
            opp_count += 1

            # Link skills
            for skill_name, level in opp.get("skills", {}).items():
                skill_id = skill_map.get(skill_name)
                if skill_id:
                    client.table("opportunity_skills").insert(
                        {
                            "opportunity_id": opp_id,
                            "skill_id": skill_id,
                            "required_level": level,
                            "is_required": level >= 50,
                        }
                    ).execute()
        except Exception as e:
            print(f"[seed_opportunities] opp '{title}' error: {e}")

    print(f"[seed_opportunities] {opp_count} new opportunities seeded")


if __name__ == "__main__":
    seed()
