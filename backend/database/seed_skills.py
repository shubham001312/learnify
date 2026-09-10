"""
Seed canonical skill taxonomy with hierarchy, aliases, and categories.

Usage:
    python -m backend.database.seed_skills

Runs against Supabase when SUPABASE_URL is set, otherwise prints to stdout.
"""

from backend.database.client import db_available, get_client

# ─── Skill Categories ────────────────────────────────────────────────────
CATEGORIES = [
    {
        "name": "Programming",
        "description": "General-purpose and systems programming languages",
    },
    {
        "name": "Web Development",
        "description": "Frontend, backend, and full-stack web technologies",
    },
    {
        "name": "Data Science",
        "description": "Data analysis, statistics, and data engineering",
    },
    {
        "name": "Machine Learning & AI",
        "description": "ML, deep learning, NLP, computer vision, and LLMs",
    },
    {
        "name": "Cloud & DevOps",
        "description": "Cloud platforms, CI/CD, containers, and infrastructure",
    },
    {
        "name": "Cybersecurity",
        "description": "Security, networking, and threat detection",
    },
    {
        "name": "Design & UX",
        "description": "UI/UX design, prototyping, and visual design",
    },
    {
        "name": "Soft Skills",
        "description": "Communication, leadership, teamwork, and problem-solving",
    },
    {"name": "Database", "description": "Relational and NoSQL database technologies"},
    {
        "name": "Mobile Development",
        "description": "Native and cross-platform mobile app development",
    },
    {
        "name": "Quality Assurance",
        "description": "Testing, automation, and quality assurance",
    },
    {
        "name": "Blockchain & Web3",
        "description": "Decentralized apps, smart contracts, and crypto",
    },
]

# ─── Skills (with parent hierarchy) ──────────────────────────────────────
# Format: (name, category_name, parent_name_or_None, difficulty, aliases)
SKILLS = [
    # Programming
    ("Python", "Programming", None, "beginner", ["python3", "py"]),
    ("Java", "Programming", None, "beginner", []),
    ("JavaScript", "Programming", None, "beginner", ["js", "ecmascript"]),
    ("TypeScript", "Programming", None, "intermediate", ["ts"]),
    ("C", "Programming", None, "intermediate", ["ansi c"]),
    ("C++", "Programming", None, "intermediate", ["cpp", "c plus plus"]),
    ("C#", "Programming", None, "intermediate", ["csharp", "c sharp"]),
    ("Go", "Programming", None, "intermediate", ["golang"]),
    ("Rust", "Programming", None, "advanced", []),
    ("Ruby", "Programming", None, "intermediate", ["ruby on rails"]),
    ("PHP", "Programming", None, "beginner", []),
    ("Kotlin", "Programming", None, "intermediate", ["kt"]),
    ("Swift", "Programming", None, "intermediate", ["swiftui"]),
    ("R", "Programming", None, "intermediate", ["rlang"]),
    ("MATLAB", "Programming", None, "intermediate", []),
    ("Scala", "Programming", None, "advanced", []),
    ("Lua", "Programming", None, "beginner", []),
    ("Perl", "Programming", None, "intermediate", []),
    ("Shell Scripting", "Programming", None, "beginner", ["bash", "shell", "zsh"]),
    # Web Development
    ("HTML", "Web Development", None, "beginner", ["html5"]),
    ("CSS", "Web Development", None, "beginner", ["css3", "scss", "sass", "less"]),
    ("React", "Web Development", None, "intermediate", ["reactjs", "react.js"]),
    ("Next.js", "Web Development", "React", "advanced", ["nextjs"]),
    ("Vue.js", "Web Development", None, "intermediate", ["vue", "vuejs"]),
    ("Angular", "Web Development", None, "intermediate", ["angularjs"]),
    ("Node.js", "Web Development", None, "intermediate", ["nodejs", "node"]),
    (
        "Express.js",
        "Web Development",
        "Node.js",
        "intermediate",
        ["express", "expressjs"],
    ),
    ("Django", "Web Development", None, "intermediate", []),
    ("Flask", "Web Development", None, "beginner", []),
    ("FastAPI", "Web Development", None, "intermediate", ["fast api"]),
    ("Spring Boot", "Web Development", None, "advanced", ["springboot", "spring"]),
    ("Laravel", "Web Development", None, "intermediate", []),
    ("Ruby on Rails", "Web Development", None, "intermediate", ["rails"]),
    ("ASP.NET", "Web Development", None, "advanced", ["aspnet", "dotnet"]),
    (
        "REST API",
        "Web Development",
        None,
        "intermediate",
        ["rest", "restful api", "rest apis"],
    ),
    ("GraphQL", "Web Development", None, "advanced", ["gql"]),
    ("WebSockets", "Web Development", None, "advanced", ["websocket"]),
    ("Tailwind CSS", "Web Development", None, "beginner", ["tailwind"]),
    ("Bootstrap", "Web Development", None, "beginner", []),
    # Data Science
    ("SQL", "Database", None, "beginner", ["mysql", "postgresql", "sqlite", "plsql"]),
    ("Pandas", "Data Science", None, "intermediate", []),
    ("NumPy", "Data Science", None, "intermediate", ["numpy"]),
    ("Data Analysis", "Data Science", None, "beginner", ["data analytics"]),
    ("Statistics", "Data Science", None, "intermediate", ["stat"]),
    ("Data Visualization", "Data Science", None, "beginner", ["data viz"]),
    ("Tableau", "Data Science", None, "beginner", []),
    ("Power BI", "Data Science", None, "beginner", ["powerbi"]),
    ("Excel", "Data Science", None, "beginner", ["microsoft excel", "spreadsheet"]),
    ("Apache Spark", "Data Science", None, "advanced", ["spark", "pyspark"]),
    ("ETL", "Data Science", None, "intermediate", ["extract transform load"]),
    ("Data Modeling", "Data Science", None, "intermediate", []),
    ("Apache Airflow", "Data Science", None, "advanced", ["airflow"]),
    ("Kafka", "Data Science", None, "advanced", ["apache kafka"]),
    ("Big Data", "Data Science", None, "advanced", ["hadoop"]),
    ("PowerShell", "Data Science", None, "intermediate", []),
    # Machine Learning & AI
    ("Machine Learning", "Machine Learning & AI", None, "intermediate", ["ml"]),
    ("Deep Learning", "Machine Learning & AI", None, "advanced", ["dl"]),
    ("TensorFlow", "Machine Learning & AI", None, "advanced", ["tf"]),
    ("PyTorch", "Machine Learning & AI", None, "advanced", ["pytorch"]),
    ("Natural Language Processing", "Machine Learning & AI", None, "advanced", ["nlp"]),
    ("Computer Vision", "Machine Learning & AI", None, "advanced", ["cv"]),
    ("Reinforcement Learning", "Machine Learning & AI", None, "advanced", ["rl"]),
    ("Generative AI", "Machine Learning & AI", None, "advanced", ["genai", "gen ai"]),
    (
        "Large Language Models",
        "Machine Learning & AI",
        None,
        "advanced",
        ["llm", "llms"],
    ),
    ("Hugging Face", "Machine Learning & AI", None, "advanced", ["huggingface"]),
    ("Scikit-learn", "Machine Learning & AI", None, "intermediate", ["sklearn"]),
    ("OpenCV", "Machine Learning & AI", None, "intermediate", []),
    (
        "Neural Networks",
        "Machine Learning & AI",
        None,
        "advanced",
        ["ann", "cnn", "rnn", "lstm"],
    ),
    # Cloud & DevOps
    ("AWS", "Cloud & DevOps", None, "intermediate", ["amazon web services"]),
    ("Azure", "Cloud & DevOps", None, "intermediate", ["microsoft azure"]),
    (
        "GCP",
        "Cloud & DevOps",
        None,
        "intermediate",
        ["google cloud", "google cloud platform"],
    ),
    ("Docker", "Cloud & DevOps", None, "intermediate", []),
    ("Kubernetes", "Cloud & DevOps", None, "advanced", ["k8s"]),
    (
        "CI/CD",
        "Cloud & DevOps",
        None,
        "intermediate",
        ["continuous integration", "continuous deployment"],
    ),
    ("Jenkins", "Cloud & DevOps", None, "intermediate", []),
    ("GitHub Actions", "Cloud & DevOps", None, "intermediate", ["gh actions"]),
    ("Terraform", "Cloud & DevOps", None, "advanced", []),
    ("Linux", "Cloud & DevOps", None, "beginner", ["linux administration"]),
    ("Nginx", "Cloud & DevOps", None, "intermediate", []),
    ("Ansible", "Cloud & DevOps", None, "advanced", []),
    # Cybersecurity
    (
        "Cybersecurity",
        "Cybersecurity",
        None,
        "intermediate",
        ["infosec", "information security"],
    ),
    (
        "Ethical Hacking",
        "Cybersecurity",
        None,
        "advanced",
        ["penetration testing", "pentest"],
    ),
    ("Network Security", "Cybersecurity", None, "intermediate", ["netsec"]),
    ("Cloud Security", "Cybersecurity", None, "advanced", []),
    ("Cryptography", "Cybersecurity", None, "advanced", ["crypto"]),
    ("OWASP", "Cybersecurity", None, "intermediate", []),
    # Design & UX
    ("Figma", "Design & UX", None, "beginner", []),
    ("UI Design", "Design & UX", None, "beginner", ["user interface", "ui"]),
    ("UX Design", "Design & UX", None, "intermediate", ["user experience", "ux"]),
    ("Prototyping", "Design & UX", None, "beginner", []),
    ("User Research", "Design & UX", None, "intermediate", ["ux research"]),
    ("Wireframing", "Design & UX", None, "beginner", []),
    ("Adobe XD", "Design & UX", None, "beginner", []),
    ("Photoshop", "Design & UX", None, "beginner", ["adobe photoshop"]),
    ("Illustrator", "Design & UX", None, "beginner", ["adobe illustrator"]),
    # Soft Skills
    (
        "Communication",
        "Soft Skills",
        None,
        "beginner",
        ["verbal communication", "written communication"],
    ),
    ("Teamwork", "Soft Skills", None, "beginner", ["collaboration"]),
    ("Leadership", "Soft Skills", None, "intermediate", []),
    ("Problem Solving", "Soft Skills", None, "beginner", ["problem-solving"]),
    ("Time Management", "Soft Skills", None, "beginner", []),
    ("Critical Thinking", "Soft Skills", None, "intermediate", []),
    ("Presentation", "Soft Skills", None, "beginner", ["public speaking"]),
    ("Negotiation", "Soft Skills", None, "intermediate", []),
    # Database
    ("PostgreSQL", "Database", None, "intermediate", ["postgres", "psql"]),
    ("MySQL", "Database", None, "intermediate", []),
    ("MongoDB", "Database", None, "intermediate", ["mongo"]),
    ("Redis", "Database", None, "intermediate", []),
    ("Elasticsearch", "Database", None, "advanced", ["elastic"]),
    ("Cassandra", "Database", None, "advanced", []),
    ("DynamoDB", "Database", None, "advanced", []),
    ("Supabase", "Database", None, "intermediate", []),
    ("Firebase", "Database", None, "intermediate", []),
    # Mobile Development
    ("React Native", "Mobile Development", None, "intermediate", ["reactnative"]),
    ("Flutter", "Mobile Development", None, "intermediate", ["dart"]),
    ("iOS Development", "Mobile Development", None, "advanced", ["ios"]),
    ("Android Development", "Mobile Development", None, "intermediate", ["android"]),
    ("Expo", "Mobile Development", None, "intermediate", []),
    # Quality Assurance
    ("Testing", "Quality Assurance", None, "beginner", ["qa", "quality assurance"]),
    ("Unit Testing", "Quality Assurance", None, "beginner", []),
    ("Integration Testing", "Quality Assurance", None, "intermediate", []),
    ("E2E Testing", "Quality Assurance", None, "advanced", ["end to end testing"]),
    ("Selenium", "Quality Assurance", None, "intermediate", []),
    ("Playwright", "Quality Assurance", None, "advanced", []),
    ("Jest", "Quality Assurance", None, "intermediate", []),
    # Blockchain & Web3
    ("Blockchain", "Blockchain & Web3", None, "advanced", []),
    ("Solidity", "Blockchain & Web3", None, "advanced", []),
    ("Smart Contracts", "Blockchain & Web3", None, "advanced", []),
    ("Web3", "Blockchain & Web3", None, "advanced", ["web 3"]),
    ("DeFi", "Blockchain & Web3", None, "advanced", ["decentralized finance"]),
]

# ─── Seed Function ────────────────────────────────────────────────────────


def seed():
    if not db_available():
        print("[seed_skills] Supabase not configured — printing seed data only.")
        print(f"Categories: {len(CATEGORIES)}")
        print(f"Skills: {len(SKILLS)}")
        return

    client = get_client()

    # 1. Upsert categories
    cat_map = {}
    for cat in CATEGORIES:
        try:
            existing = (
                client.table("skill_categories")
                .select("id")
                .eq("name", cat["name"])
                .limit(1)
                .execute()
            )
            if existing.data:
                cat_id = existing.data[0]["id"]
            else:
                res = client.table("skill_categories").insert(cat).execute()
                cat_id = res.data[0]["id"]
            cat_map[cat["name"]] = cat_id
        except Exception as e:
            print(f"[seed_skills] category '{cat['name']}' error: {e}")
    print(f"[seed_skills] {len(cat_map)} categories upserted")

    # 2. Upsert skills + aliases
    skill_map = {}  # name -> id
    skill_count = 0
    alias_count = 0

    for name, cat_name, parent_name, difficulty, aliases in SKILLS:
        cat_id = cat_map.get(cat_name)
        parent_id = skill_map.get(parent_name) if parent_name else None

        row = {
            "name": name,
            "category_id": cat_id,
            "difficulty": difficulty,
        }
        if parent_id:
            row["parent_skill_id"] = parent_id

        try:
            existing = (
                client.table("skills").select("id").eq("name", name).limit(1).execute()
            )
            if existing.data:
                skill_id = existing.data[0]["id"]
            else:
                res = client.table("skills").insert(row).execute()
                skill_id = res.data[0]["id"]
                skill_count += 1

            skill_map[name] = skill_id

            # Aliases
            for alias in aliases:
                try:
                    client.table("skill_aliases").upsert(
                        {"skill_id": skill_id, "alias": alias},
                        on_conflict="alias",
                    ).execute()
                    alias_count += 1
                except Exception:
                    pass
        except Exception as e:
            print(f"[seed_skills] skill '{name}' error: {e}")

    print(f"[seed_skills] {skill_count} new skills, {alias_count} aliases upserted")
    print(f"[seed_skills] Total skill map: {len(skill_map)} skills")


if __name__ == "__main__":
    seed()
