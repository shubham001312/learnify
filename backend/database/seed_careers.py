# Curated dataset of Indian career paths.
# Source of truth for the /api/careers endpoints and the Career tab pages.
# Each entry is self-contained so it renders richly without a DB dependency.

CAREERS = [
    {
        "id": "computer-science-engineering",
        "title": "Computer Science & Engineering",
        "category": "Engineering",
        "icon": "💻",
        "tagline": "Build the software, apps and systems that run the world.",
        "description": (
            "Computer Science & Engineering (CSE) is the study of computation, programming, "
            "algorithms, and computer systems. CSE graduates design everything from mobile "
            "apps and operating systems to large-scale cloud infrastructure. It is one of the "
            "most in-demand and versatile engineering branches in India."
        ),
        "exams": ["JEE Main", "JEE Advanced", "BITSAT", "State CET", "VITEEE"],
        "eligibility": "10+2 with Physics, Chemistry & Mathematics (PCM), min ~60% aggregate.",
        "top_colleges": [
            "IIT Bombay",
            "IIT Delhi",
            "IIT Madras",
            "IIIT Hyderabad",
            "NIT Trichy",
            "BITS Pilani",
            "IIT Kanpur",
            "Jadavpur University",
        ],
        "skills": [
            "Programming (C++, Java, Python)",
            "Data structures & algorithms",
            "Problem solving",
            "OS & networking basics",
            "Web/App development",
        ],
        "scope": (
            "Software engineer, backend/frontend developer, SDE, systems engineer, "
            "engineering manager, or founder of a tech startup."
        ),
        "salary": "₹6–35 LPA entry to mid; senior roles & international offers much higher.",
        "growth": "Highest hiring volume in India; strong long-term demand across every industry.",
        "roadmap": [
            "Take PCM in 10+2 and aim for JEE (Main + Advanced).",
            "Build strong DSA + one language (Python/Java/C++).",
            "Do internships and open-source / personal projects.",
            "Target on-campus placements or off-campus via contests (Codeforces, LeetCode).",
            "Keep learning: cloud, system design, and a specialization (AI, security, etc.).",
        ],
        "related": [
            "artificial-intelligence-ml",
            "data-science",
            "electronics-communication",
        ],
    },
    {
        "id": "artificial-intelligence-ml",
        "title": "Artificial Intelligence & Machine Learning",
        "category": "Engineering",
        "icon": "🤖",
        "tagline": "Teach machines to perceive, reason and decide.",
        "description": (
            "AI/ML engineering focuses on building intelligent systems — from recommendation "
            "engines and chatbots to computer vision and autonomous systems. It blends "
            "computer science, mathematics and statistics, and is among the fastest-growing "
            "tech careers globally."
        ),
        "exams": [
            "JEE Main",
            "JEE Advanced",
            "BITSAT",
            "State CET",
            "GATE (for M.Tech)",
        ],
        "eligibility": "10+2 PCM; strong maths aptitude. B.Tech AI/ML or CSE + AI electives.",
        "top_colleges": [
            "IIT Hyderabad",
            "IIT Bombay",
            "IIIT Hyderabad",
            "IISc Bengaluru",
            "BITS Pilani",
            "IIT Kharagpur",
            "NIT Surathkal",
        ],
        "skills": [
            "Python",
            "Linear algebra & statistics",
            "Deep learning frameworks (PyTorch/TF)",
            "Data handling",
            "MLOps",
        ],
        "scope": "ML engineer, AI researcher, data scientist, CV/NLP engineer, research scientist.",
        "salary": "₹8–40 LPA; top global AI roles cross ₹1 Cr for specialists.",
        "growth": "Explosive demand post-GenAI; skill shortage keeps salaries high.",
        "roadmap": [
            "Master mathematics (linear algebra, probability).",
            "Learn Python + core ML, then deep learning.",
            "Work on real datasets / Kaggle competitions.",
            "Pursue B.Tech AI or M.Tech/CS with AI specialization.",
            "Publish or ship production ML systems to stand out.",
        ],
        "related": ["computer-science-engineering", "data-science"],
    },
    {
        "id": "data-science",
        "title": "Data Science & Analytics",
        "category": "Engineering",
        "icon": "📊",
        "tagline": "Turn raw data into decisions that move businesses.",
        "description": (
            "Data scientists collect, clean and analyse data to find patterns and build "
            "predictive models. They sit at the intersection of statistics, programming and "
            "domain knowledge, helping companies make evidence-based decisions."
        ),
        "exams": ["JEE Main", "CUET", "State CET", "GATE", "ISI Admission Test"],
        "eligibility": "10+2 PCM/CS; B.Tech/CS/Stats or B.Sc Statistics + data skills.",
        "top_colleges": [
            "IIT Bombay",
            "IIT Madras",
            "ISI Kolkata",
            "IIM Calcutta (PGDBA)",
            "IIIT Bangalore",
            "BITS Pilani",
            "IIT Kharagpur",
        ],
        "skills": [
            "SQL & Python",
            "Statistics",
            "Visualization",
            "ML basics",
            "Business acumen",
        ],
        "scope": "Data analyst, data scientist, ML engineer, BI analyst, analytics consultant.",
        "salary": "₹6–30 LPA; senior analytics leads earn significantly more.",
        "growth": "Every company is data-driven now — steady, broad demand.",
        "roadmap": [
            "Build a strong stats + Python foundation.",
            "Learn SQL, pandas, visualization (Tableau/Power BI).",
            "Study ML and deploy a couple of end-to-end projects.",
            "Get a relevant degree (B.Tech/CS, B.Stat, or M.Sc Data Science).",
            "Intern in analytics; build a portfolio on GitHub.",
        ],
        "related": ["artificial-intelligence-ml", "computer-science-engineering"],
    },
    {
        "id": "mechanical-engineering",
        "title": "Mechanical Engineering",
        "category": "Engineering",
        "icon": "⚙️",
        "tagline": "Design and build machines that power industry.",
        "description": (
            "Mechanical engineering covers the design, manufacturing and operation of physical "
            "systems — from engines and robots to HVAC and aerospace components. It remains a "
            "core, evergreen branch with wide applicability."
        ),
        "exams": ["JEE Main", "JEE Advanced", "BITSAT", "State CET", "GATE"],
        "eligibility": "10+2 PCM.",
        "top_colleges": [
            "IIT Bombay",
            "IIT Madras",
            "IIT Kanpur",
            "IIT Kharagpur",
            "NIT Trichy",
            "BITS Pilani",
            "COEP Pune",
        ],
        "skills": [
            "Thermodynamics",
            "CAD/CAM",
            "Manufacturing",
            "Robotics",
            "Fluid mechanics",
        ],
        "scope": "Design engineer, production manager, automotive/R&D, PSU jobs, robotics.",
        "salary": "₹4–18 LPA; PSUs and MNCs offer stable, growing packages.",
        "growth": "Steady demand; strong in manufacturing, automotive and energy sectors.",
        "roadmap": [
            "Take PCM; prepare for JEE/GATE.",
            "Learn CAD tools (SolidWorks, AutoCAD) early.",
            "Do internships in manufacturing/automotive firms.",
            "Consider GATE for PSUs or M.Tech specialization.",
            "Add mechatronics/robotics skills for modern roles.",
        ],
        "related": [
            "civil-engineering",
            "electrical-engineering",
            "aerospace-engineering",
        ],
    },
    {
        "id": "civil-engineering",
        "title": "Civil Engineering",
        "category": "Engineering",
        "icon": "🏗️",
        "tagline": "Shape the infrastructure of cities and nations.",
        "description": (
            "Civil engineering involves planning, designing and constructing infrastructure such "
            "as buildings, bridges, roads, dams and water systems. It is essential for urban "
            "development and public infrastructure."
        ),
        "exams": ["JEE Main", "State CET", "GATE", "IES/ESE"],
        "eligibility": "10+2 PCM.",
        "top_colleges": [
            "IIT Bombay",
            "IIT Roorkee",
            "IIT Madras",
            "NIT Trichy",
            "IIT Kharagpur",
            "Jadavpur University",
            "COEP Pune",
        ],
        "skills": [
            "Structural analysis",
            "AutoCAD/STAAD",
            "Surveying",
            "Project management",
        ],
        "scope": "Structural engineer, site/construction manager, urban planner, PSU/Govt engineer.",
        "salary": "₹4–16 LPA; govt & PSU roles very stable with perks.",
        "growth": "Driven by infra spending; steady, location-flexible careers.",
        "roadmap": [
            "Take PCM; prepare for JEE/State CET.",
            "Learn AutoCAD, STAAD-Pro, surveying basics.",
            "Intern with construction/infra companies.",
            "Target GATE/ESE for PSU & govt engineering jobs.",
            "Specialize (structural/transport/environmental).",
        ],
        "related": ["mechanical-engineering", "architecture"],
    },
    {
        "id": "electrical-engineering",
        "title": "Electrical & Electronics Engineering",
        "category": "Engineering",
        "icon": "🔌",
        "tagline": "Power, circuits and the devices we use daily.",
        "description": (
            "Electrical engineering covers power generation, transmission, electronics and "
            "control systems. It underpins everything from the grid to consumer electronics "
            "and electric vehicles."
        ),
        "exams": ["JEE Main", "JEE Advanced", "BITSAT", "State CET", "GATE"],
        "eligibility": "10+2 PCM.",
        "top_colleges": [
            "IIT Bombay",
            "IIT Delhi",
            "IIT Madras",
            "IIT Kanpur",
            "NIT Trichy",
            "BITS Pilani",
            "Jadavpur University",
        ],
        "skills": [
            "Circuits & signals",
            "Power systems",
            "Control systems",
            "Embedded C",
        ],
        "scope": "Power engineer, electronics designer, EV/semiconductor, PSU, R&D.",
        "salary": "₹4–20 LPA; PSUs and core MNCs pay well.",
        "growth": "Strong with the EV, renewable energy and semiconductor push.",
        "roadmap": [
            "Take PCM; strong JEE prep.",
            "Build circuits & learn embedded systems as a hobby.",
            "Intern in power/electronics firms.",
            "GATE for PSUs or M.Tech (VLSI, power).",
            "Follow EV / renewable energy trends.",
        ],
        "related": ["electronics-communication", "mechanical-engineering"],
    },
    {
        "id": "electronics-communication",
        "title": "Electronics & Communication Engineering",
        "category": "Engineering",
        "icon": "📡",
        "tagline": "Connect the world through chips and signals.",
        "description": (
            "ECE blends electronics, communication systems, signal processing and embedded "
            "design. It powers mobile networks, IoT, satellites and consumer devices."
        ),
        "exams": ["JEE Main", "JEE Advanced", "BITSAT", "State CET", "GATE"],
        "eligibility": "10+2 PCM.",
        "top_colleges": [
            "IIT Madras",
            "IIT Kharagpur",
            "IIIT Hyderabad",
            "NIT Trichy",
            "IIT Roorkee",
            "BITS Pilani",
            "Jadavpur University",
        ],
        "skills": ["VLSI", "Embedded systems", "Signal processing", "Wireless comms"],
        "scope": "VLSI engineer, embedded developer, telecom/R&D, IoT, semiconductor.",
        "salary": "₹4–22 LPA; VLSI & semiconductor roles are booming.",
        "growth": "Huge demand from 5G, IoT and the India semiconductor mission.",
        "roadmap": [
            "Take PCM; prepare for JEE/GATE.",
            "Learn Verilog, embedded C, Arduino/Raspberry Pi.",
            "Intern in telecom/semiconductor firms.",
            "Specialize via M.Tech (VLSI / signal processing).",
            "Build hardware projects for a strong profile.",
        ],
        "related": ["electrical-engineering", "computer-science-engineering"],
    },
    {
        "id": "chemical-engineering",
        "title": "Chemical Engineering",
        "category": "Engineering",
        "icon": "🧪",
        "tagline": "Transform raw materials into useful products.",
        "description": (
            "Chemical engineering applies chemistry, physics and biology to design processes "
            "that produce fuels, plastics, pharmaceuticals, food and materials at scale."
        ),
        "exams": ["JEE Main", "JEE Advanced", "State CET", "GATE"],
        "eligibility": "10+2 PCM (sometimes with Chemistry focus).",
        "top_colleges": [
            "IIT Bombay",
            "IIT Delhi",
            "IIT Madras",
            "ICT Mumbai",
            "IIT Kanpur",
            "NIT Trichy",
            "Jadavpur University",
        ],
        "skills": [
            "Process design",
            "Thermodynamics",
            "Reaction engineering",
            "Safety",
        ],
        "scope": "Process engineer, petrochemical, pharma, paints, PSU (IOCL, ONGC).",
        "salary": "₹4–18 LPA; PSUs offer excellent packages + stability.",
        "growth": "Stable core sector; strong in pharma and energy.",
        "roadmap": [
            "Take PCM; prepare for JEE/GATE.",
            "Focus on chemistry & process fundamentals.",
            "Intern in pharma/petro/process industries.",
            "GATE for PSUs or M.Tech specialization.",
            "Learn process simulation tools (Aspen).",
        ],
        "related": ["mechanical-engineering", "civil-engineering"],
    },
    {
        "id": "aerospace-engineering",
        "title": "Aerospace Engineering",
        "category": "Engineering",
        "icon": "🚀",
        "tagline": "Design aircraft, rockets and space systems.",
        "description": (
            "Aerospace engineering covers the design, development and testing of aircraft and "
            "spacecraft, including aerodynamics, propulsion and structures. India's growing "
            "space program (ISRO) makes this an exciting field."
        ),
        "exams": ["JEE Main", "JEE Advanced", "State CET", "GATE"],
        "eligibility": "10+2 PCM with strong maths/physics.",
        "top_colleges": [
            "IIT Bombay",
            "IIT Madras",
            "IIT Kanpur",
            "IIT Kharagpur",
            "IIST Thiruvananthapuram",
            "NIT Trichy",
        ],
        "skills": ["Aerodynamics", "Propulsion", "Structures", "CFD", "Controls"],
        "scope": "Aerospace engineer (ISRO/DRDO/HAL), defence R&D, propulsion, research.",
        "salary": "₹5–20 LPA; govt space/defence roles prestigious + stable.",
        "growth": "Growing with ISRO privatization and defence manufacturing.",
        "roadmap": [
            "Take PCM; excel in JEE Advanced.",
            "Build models / participate in aero competitions (SUAV).",
            "Intern at HAL, DRDO or research labs.",
            "M.Tech/MS abroad for advanced research.",
            "Follow ISRO/space-tech startups for openings.",
        ],
        "related": ["mechanical-engineering", "electrical-engineering"],
    },
    {
        "id": "mbbs",
        "title": "MBBS & Medicine",
        "category": "Medical & Health",
        "icon": "🩺",
        "tagline": "Become a doctor and care for lives.",
        "description": (
            "MBBS is the primary medical degree to become a physician. After MBBS, graduates "
            "can specialize (MD/MS) in fields like medicine, surgery, pediatrics or radiology. "
            "It is demanding but one of the most respected professions."
        ),
        "exams": ["NEET UG", "NEET PG", "INICET"],
        "eligibility": "10+2 with Physics, Chemistry, Biology (PCB); qualify NEET UG.",
        "top_colleges": [
            "AIIMS Delhi",
            "CMC Vellore",
            "JIPMER Puducherry",
            "MAMC Delhi",
            "Kasturba Medical College",
            "Grant Medical College Mumbai",
        ],
        "skills": [
            "Clinical knowledge",
            "Diagnosis",
            "Empathy",
            "Stamina",
            "Communication",
        ],
        "scope": "Physician, specialist (surgeon/cardiologist), government doctor, researcher.",
        "salary": "₹6–20 LPA early; specialists earn ₹25 LPA+; private practice higher.",
        "growth": "Evergreen demand; India needs many more doctors per capita.",
        "roadmap": [
            "Take PCB; aim for NEET UG with top rank.",
            "Complete 5.5-year MBBS + internship.",
            "Clear NEET PG for specialization (MD/MS).",
            "Build clinical experience / senior residency.",
            "Optionally super-specialize (DM/MCh).",
        ],
        "related": ["bds", "pharmacy", "nursing", "physiotherapy"],
    },
    {
        "id": "bds",
        "title": "Dental Surgery (BDS)",
        "category": "Medical & Health",
        "icon": "🦷",
        "tagline": "Specialize in oral and dental health.",
        "description": (
            "BDS (Bachelor of Dental Surgery) trains students in dentistry, including diagnosis, "
            "orthodontics, oral surgery and prosthodontics. Dentists can run clinics or specialize."
        ),
        "exams": ["NEET UG", "NEET MDS"],
        "eligibility": "10+2 PCB; qualify NEET UG.",
        "top_colleges": [
            "Maulana Azad Institute Delhi",
            "Manipal College of Dental Sciences",
            "Government Dental College Mumbai",
            "SDM College of Dental Sciences",
        ],
        "skills": [
            "Clinical dentistry",
            "Orthodontics",
            "Hand-eye coordination",
            "Patient care",
        ],
        "scope": "Dental surgeon, orthodontist, clinic owner, hospital dentist.",
        "salary": "₹4–15 LPA; private practice scales with reputation.",
        "growth": "Steady demand; aesthetics/ortho particularly growing.",
        "roadmap": [
            "Take PCB; prepare for NEET UG.",
            "Complete 5-year BDS.",
            "Practice or set up a clinic.",
            "MDS for specialization (ortho, endo, surgery).",
            "Build local reputation for a thriving practice.",
        ],
        "related": ["mbbs", "physiotherapy"],
    },
    {
        "id": "pharmacy",
        "title": "Pharmacy (B.Pharm / D.Pharm)",
        "category": "Medical & Health",
        "icon": "💊",
        "tagline": "Bridge medicine and science for safer drugs.",
        "description": (
            "Pharmacy studies drug design, manufacture, regulation and patient counseling. "
            "B.Pharm graduates work in industry, retail, clinical research and regulatory affairs."
        ),
        "exams": ["NEET UG (some states)", "CUET", "State CET", "GPAT"],
        "eligibility": "10+2 PCB/PCM.",
        "top_colleges": [
            "ICT Mumbai",
            "BITS Pilani (Pharmacy)",
            "JAMIA Hamdard Delhi",
            "National Institute of Pharmaceutical Education & Research (NIPER)",
        ],
        "skills": [
            "Pharmaceutical chemistry",
            "Pharmacology",
            "Regulatory",
            "Quality control",
        ],
        "scope": "Industrial pharmacist, QA/QC, regulatory affairs, clinical research, retail.",
        "salary": "₹3–12 LPA; NIPER/MNC pharma pays more.",
        "growth": "Strong with India's pharma & CDMO export growth.",
        "roadmap": [
            "Take PCB/PCM; entrance via CUET/state CET.",
            "Complete B.Pharm (4 yrs).",
            "GPAT for M.Pharm / NIPER.",
            "Intern in pharma manufacturing/R&D.",
            "Specialize (regulatory, formulation, clinical research).",
        ],
        "related": ["mbbs", "chemical-engineering"],
    },
    {
        "id": "nursing",
        "title": "Nursing (B.Sc Nursing)",
        "category": "Medical & Health",
        "icon": "🏥",
        "tagline": "The backbone of patient care.",
        "description": (
            "Nursing prepares professionals for patient care across hospitals, community health "
            "and critical care. It is a high-demand, noble and globally mobile profession."
        ),
        "exams": ["NEET UG (some states)", "State nursing entrance", "AIIMS Nursing"],
        "eligibility": "10+2 PCB; English required.",
        "top_colleges": [
            "AIIMS Nursing Colleges",
            "CMC Vellore",
            "College of Nursing, PGIMER Chandigarh",
            "Rakhmabai College Mumbai",
        ],
        "skills": [
            "Patient care",
            "Clinical procedures",
            "Communication",
            "Compassion",
        ],
        "scope": "Staff nurse, critical-care nurse, community health, abroad (US/UK/AU).",
        "salary": "₹3–10 LPA in India; high abroad with licensing.",
        "growth": "Huge global demand; excellent overseas opportunities.",
        "roadmap": [
            "Take PCB; clear nursing entrance.",
            "Complete 4-year B.Sc Nursing.",
            "Register with state nursing council.",
            "Gain hospital experience.",
            "Pursue abroad licensing (NCLEX/OSCE) for global roles.",
        ],
        "related": ["mbbs", "physiotherapy"],
    },
    {
        "id": "physiotherapy",
        "title": "Physiotherapy (BPT)",
        "category": "Medical & Health",
        "icon": "🤸",
        "tagline": "Restore movement and relieve pain.",
        "description": (
            "Physiotherapy treats injury, disability and pain through movement, exercise and "
            "manual therapy. BPT graduates work in hospitals, sports and rehabilitation centers."
        ),
        "exams": ["NEET UG (some states)", "CUET", "State CET"],
        "eligibility": "10+2 PCB.",
        "top_colleges": [
            "Christian Medical College Vellore",
            "Seth GS Medical College Mumbai",
            "Manipal Academy of Higher Education",
            "Jamia Millia Islamia",
        ],
        "skills": [
            "Anatomy & kinesiology",
            "Rehab techniques",
            "Exercise prescription",
        ],
        "scope": "Physiotherapist, sports therapist, rehab specialist, private practice.",
        "salary": "₹3–10 LPA; sports & premium clinics pay more.",
        "growth": "Rising with fitness/aging population awareness.",
        "roadmap": [
            "Take PCB; clear entrance.",
            "Complete 4.5-year BPT.",
            "Internship in hospital/rehab set-up.",
            "Specialize (sports, neuro, paediatric).",
            "Set up clinic or join sports teams.",
        ],
        "related": ["mbbs", "nursing"],
    },
    {
        "id": "veterinary",
        "title": "Veterinary Science (BVSc)",
        "category": "Medical & Health",
        "icon": "🐾",
        "tagline": "Care for animals and public health.",
        "description": (
            "Veterinary science (BVSc & AH) trains doctors for animals — from pets and livestock "
            "to wildlife. It also plays a key role in food safety and zoonotic disease control."
        ),
        "exams": ["NEET UG", "State veterinary entrance"],
        "eligibility": "10+2 PCB.",
        "top_colleges": [
            "IVRI Bareilly",
            "Madras Veterinary College",
            "Bombay Veterinary College",
            "GADVASU Ludhiana",
        ],
        "skills": ["Animal anatomy", "Surgery", "Livestock management", "Diagnostics"],
        "scope": "Veterinary doctor, livestock officer, research, pet clinic owner.",
        "salary": "₹4–12 LPA; govt livestock roles stable.",
        "growth": "Growing pet-care market + livestock sector.",
        "roadmap": [
            "Take PCB; qualify NEET/state entrance.",
            "Complete 5-year BVSc & AH.",
            "Register with veterinary council.",
            "Practice or join govt livestock dept.",
            "Specialize (surgery, pathology, wildlife).",
        ],
        "related": ["mbbs", "agriculture"],
    },
    {
        "id": "bsc-pure-sciences",
        "title": "B.Sc Pure & Applied Sciences",
        "category": "Sciences",
        "icon": "🔬",
        "tagline": "Study physics, chemistry, maths or biology deeply.",
        "description": (
            "A B.Sc builds a strong foundation in core sciences (Physics, Chemistry, Maths, "
            "Biology, Biotechnology). It is the gateway to research, teaching and many "
            "specialized master's programs."
        ),
        "exams": ["CUET", "State CET", "IISER Aptitude Test (IAT)", "NEST"],
        "eligibility": "10+2 PCB/PCM depending on subject.",
        "top_colleges": [
            "IISc Bengaluru",
            "IISERs (Pune, Kolkata, Mohali)",
            "St. Stephen's Delhi",
            "Loyola College Chennai",
            "Hindu College Delhi",
        ],
        "skills": [
            "Analytical thinking",
            "Lab techniques",
            "Maths",
            "Scientific writing",
        ],
        "scope": "Research, teaching, MSc/PhD, data/analysis roles, civil services.",
        "salary": "₹3–10 LPA early; research/PhD unlocks higher tracks.",
        "growth": "Research & analytics expanding; good base for further study.",
        "roadmap": [
            "Choose PCM/PCB per interest.",
            "Enter via CUET/IISER/NEST.",
            "Excel in a core subject.",
            "Pursue MSc / integrated PhD (IISc/IISER).",
            "Research internships (IAS, TIFR, labs).",
        ],
        "related": ["research-scientist", "data-science"],
    },
    {
        "id": "research-scientist",
        "title": "Research Scientist",
        "category": "Sciences",
        "icon": "🧬",
        "tagline": "Push the boundaries of human knowledge.",
        "description": (
            "Research scientists work in academia, national labs and industry R&D to discover "
            "new knowledge and technologies — from materials and biotech to space and AI."
        ),
        "exams": ["GATE", "CSIR-NET", "UGC-NET", "JRF", "PhD entrances"],
        "eligibility": "B.Sc/M.Sc; PhD for independent research.",
        "top_colleges": [
            "IISc Bengaluru",
            "TIFR Mumbai",
            "IISERs",
            "IITs (MS/PhD)",
            "CSIR Labs",
            "NCBS Bengaluru",
        ],
        "skills": [
            "Deep domain expertise",
            "Experiment design",
            "Statistics",
            "Writing",
        ],
        "scope": "Scientist (CSIR/DRDO/ISRO), professor, R&D lead, policy advisor.",
        "salary": "₹6–25 LPA; senior scientists & professors higher.",
        "growth": "India ramping up R&D spending; strong long-term track.",
        "roadmap": [
            "Build a strong B.Sc/M.Sc base.",
            "Clear CSIR/UGC-NET JRF.",
            "Join a lab / PhD program.",
            "Publish and present research.",
            "Move to scientist/faculty positions.",
        ],
        "related": ["bsc-pure-sciences", "artificial-intelligence-ml"],
    },
    {
        "id": "chartered-accountancy",
        "title": "Chartered Accountancy (CA)",
        "category": "Commerce & Finance",
        "icon": "📒",
        "tagline": "The trusted experts of finance and audit.",
        "description": (
            "Chartered Accountancy is a prestigious professional course (via ICAI) covering "
            "accounting, auditing, taxation and finance. CAs are essential in every company."
        ),
        "exams": ["CA Foundation", "CA Intermediate", "CA Final"],
        "eligibility": "10+2 (any stream); Commerce preferred. Direct entry via graduation.",
        "top_colleges": [
            "ICAI (national)",
            "St. Xavier's Kolkata",
            "SRCC Delhi",
            "Loyola College Chennai",
            "Hindu College Delhi",
        ],
        "skills": [
            "Accounting",
            "Taxation",
            "Audit",
            "Finance law",
            "Analytical rigour",
        ],
        "scope": "CA in practice, auditor, CFO, consultant, investment/risk roles.",
        "salary": "₹6–25 LPA; partners in firms earn much more.",
        "growth": "Always in demand; backbone of compliance & finance.",
        "roadmap": [
            "Take Commerce in 10+2 (or any stream).",
            "Register for CA Foundation (or direct entry).",
            "Clear Intermediate + articleship (3 yrs).",
            "Pass CA Final.",
            "Join a firm, industry or start practice.",
        ],
        "related": ["bcom-finance", "mba"],
    },
    {
        "id": "bcom-finance",
        "title": "B.Com & Finance",
        "category": "Commerce & Finance",
        "icon": "💰",
        "tagline": "Foundations of business, banking and markets.",
        "description": (
            "B.Com (with finance/accounting specializations) is a versatile commerce degree "
            "leading to banking, accounting, MBA and financial services careers."
        ),
        "exams": ["CUET", "State CET", "DU ET", "IPMAT (for integrated MBA)"],
        "eligibility": "10+2 (any stream; Commerce preferred).",
        "top_colleges": [
            "SRCC Delhi",
            "St. Stephen's Delhi",
            "Loyola College Chennai",
            "Hindu College Delhi",
            "St. Xavier's Mumbai",
        ],
        "skills": ["Accounting", "Economics", "Banking", "Excel & finance tools"],
        "scope": "Banking, financial analyst, accountant, MBA, consulting.",
        "salary": "₹3–10 LPA early; MBA Finance boosts sharply.",
        "growth": "Stable; finance sector keeps hiring analysts.",
        "roadmap": [
            "Take Commerce in 10+2.",
            "Enter top college via CUET/ET.",
            "Learn Excel, Tally, markets basics.",
            "Intern in a bank / Big 4.",
            "Pursue MBA (CAT) or professional course (CA/CFA).",
        ],
        "related": ["chartered-accountancy", "mba"],
    },
    {
        "id": "mba",
        "title": "MBA & Management",
        "category": "Management",
        "icon": "📈",
        "tagline": "Lead teams, products and businesses.",
        "description": (
            "An MBA builds leadership, strategy, marketing and finance skills. Graduates lead "
            "functions across companies and are among the highest-paid in India."
        ),
        "exams": ["CAT", "XAT", "GMAT", "SNAP", "NMAT"],
        "eligibility": "Bachelor's degree (any stream); top B-schools prefer work experience.",
        "top_colleges": [
            "IIM Ahmedabad",
            "IIM Bangalore",
            "IIM Calcutta",
            "FMS Delhi",
            "ISB Hyderabad",
            "XLRI Jamshedpur",
            "IIT Bombay (SJMSOM)",
        ],
        "skills": [
            "Strategy",
            "Communication",
            "Leadership",
            "Analytics",
            "Networking",
        ],
        "scope": "Product manager, consultant, banker, founder, CXO track.",
        "salary": "₹12–35 LPA from top B-schools; global MBAs higher.",
        "growth": "Strong; management roles expand with the economy.",
        "roadmap": [
            "Graduate in any discipline.",
            "Build academics + extracurriculars.",
            "Prepare for CAT/GMAT; aim for top B-school.",
            "Get pre-MBA work experience if possible.",
            "Intern & recruit into consulting/PM/finance.",
        ],
        "related": ["bcom-finance", "chartered-accountancy"],
    },
    {
        "id": "law",
        "title": "Law (BA LLB / LLB)",
        "category": "Law",
        "icon": "⚖️",
        "tagline": "Uphold justice and advise the world.",
        "description": (
            "A 5-year integrated LLB (BA/BBALLB) or 3-year LLB prepares students for legal "
            "practice, judiciary, corporate law and public policy."
        ),
        "exams": ["CLAT", "AILET", "LSAT India", "State law CET"],
        "eligibility": "10+2 for 5-yr integrated; graduation for 3-yr LLB.",
        "top_colleges": [
            "NLSIU Bengaluru",
            "NALSAR Hyderabad",
            "NLU Delhi",
            "WBNUJS Kolkata",
            "Faculty of Law, DU",
        ],
        "skills": [
            "Legal reasoning",
            "Research",
            "Argumentation",
            "Drafting",
            "Ethics",
        ],
        "scope": "Litigation, corporate lawyer, judge (judiciary), legal consultant.",
        "salary": "₹5–20 LPA corporate; top firms & senior counsel much higher.",
        "growth": "Growing with business, startups and disputes.",
        "roadmap": [
            "Take any stream in 10+2 (humanities helpful).",
            "Crack CLAT/AILET for NLUs.",
            "Complete 5-year BA LLB.",
            "Intern with firms / chambers.",
            "Clear judiciary or join a law firm / corp.",
        ],
        "related": ["civil-services", "mba"],
    },
    {
        "id": "architecture",
        "title": "Architecture (B.Arch)",
        "category": "Design & Creative",
        "icon": "🏛️",
        "tagline": "Design spaces where life happens.",
        "description": (
            "Architecture blends art, engineering and sociology to design buildings and "
            "environments. B.Arch graduates become licensed architects or urban designers."
        ),
        "exams": ["NATA", "JEE Main (Paper 2)", "State architecture CET"],
        "eligibility": "10+2 PCM with Maths; qualify NATA/JEE Paper 2.",
        "top_colleges": [
            "SPA Delhi",
            "CEPT Ahmedabad",
            "IIT Roorkee (B.Arch)",
            "JJ College of Architecture Mumbai",
            "NIT Calicut",
        ],
        "skills": ["Design", "AutoCAD/Revit", "Visualization", "Structures basics"],
        "scope": "Architect, urban designer, interior designer, set designer.",
        "salary": "₹4–15 LPA; own practice scales over time.",
        "growth": "Steady with real-estate & smart-city projects.",
        "roadmap": [
            "Take PCM; build a design portfolio.",
            "Crack NATA / JEE Paper 2.",
            "Complete 5-year B.Arch.",
            "Intern with architecture studios.",
            "Register with COA; start practice or specialize.",
        ],
        "related": ["civil-engineering", "ux-design"],
    },
    {
        "id": "ux-design",
        "title": "UX / UI & Product Design",
        "category": "Design & Creative",
        "icon": "🎨",
        "tagline": "Craft products people love to use.",
        "description": (
            "UX/UI design focuses on how digital products feel and function — research, "
            "wireframing, prototyping and visual design. It is a fast-growing creative-tech field."
        ),
        "exams": [
            "UCEED",
            "NID DAT",
            "Portfolio-based hire",
            "Private university tests",
        ],
        "eligibility": "10+2 any stream; strong portfolio valued over exams.",
        "top_colleges": [
            "IIT Bombay (IDC)",
            "NID Ahmedabad",
            "IIIT Delhi",
            "Srishti Manipal",
            "NIFT (some programs)",
        ],
        "skills": ["User research", "Figma", "Prototyping", "Visual design", "Empathy"],
        "scope": "UX designer, product designer, UI designer, design lead.",
        "salary": "₹5–22 LPA; senior product designers earn more.",
        "growth": "Soaring demand as every company builds digital products.",
        "roadmap": [
            "Build a portfolio of app/website redesigns.",
            "Learn Figma, design systems, basics of UX research.",
            "Study design (UCEED/NID) or self-learn + bootcamp.",
            "Intern as a UX/UI designer.",
            "Specialize (product, research, interaction).",
        ],
        "related": ["architecture", "fashion-design", "computer-science-engineering"],
    },
    {
        "id": "fashion-design",
        "title": "Fashion Design",
        "category": "Design & Creative",
        "icon": "👗",
        "tagline": "Create the clothes and styles of tomorrow.",
        "description": (
            "Fashion design covers apparel, textiles and accessory design — from concept and "
            "sketching to production and brand building."
        ),
        "exams": ["NIFT Entrance", "NID DAT", "CED (Pearl/Amity tests)"],
        "eligibility": "10+2 any stream.",
        "top_colleges": [
            "NIFT Delhi/Mumbai/Bengaluru",
            "NID Ahmedabad",
            "Pearl Academy",
            "Symbiosis Institute of Design",
        ],
        "skills": [
            "Sketching",
            "Textiles",
            "Trend research",
            "Construction",
            "Branding",
        ],
        "scope": "Fashion designer, stylist, merchandiser, entrepreneur, costume designer.",
        "salary": "₹3–12 LPA; successful labels earn far more.",
        "growth": "Growing with Indian fashion & export market.",
        "roadmap": [
            "Build a portfolio of sketches/collections.",
            "Crack NIFT/NID entrance.",
            "Complete B.Des Fashion.",
            "Intern with brands / designers.",
            "Launch label or join a fashion house.",
        ],
        "related": ["ux-design", "architecture"],
    },
    {
        "id": "civil-services",
        "title": "Civil Services (UPSC / IAS)",
        "category": "Civil Services & Government",
        "icon": "🏛️",
        "tagline": "Serve the nation at the highest level.",
        "description": (
            "Civil services (IAS, IPS, IFS via UPSC CSE) offer prestigious roles in "
            "administration, policy and governance. It is one of the toughest yet most "
            "impactful careers in India."
        ),
        "exams": ["UPSC CSE (Prelims, Mains, Interview)", "State PSC"],
        "eligibility": "Graduation in any discipline.",
        "top_colleges": [
            "Any recognized university (no specific college); top prep hubs: Delhi",
            "St. Stephen's, Hindu College, LSR (common feeders)",
        ],
        "skills": [
            "General studies",
            "Essay writing",
            "Analytical thinking",
            "Ethics",
            "Stamina",
        ],
        "scope": "IAS/IPS/IFS officer, policy advisor, administrator, diplomat.",
        "salary": "₹10–25 LPA (pay + perks); high social prestige.",
        "growth": "Limited seats but unmatched stability & impact.",
        "roadmap": [
            "Graduate in any stream.",
            "Choose an optional subject early.",
            "Build newspaper + NCERT + standard-book habit.",
            "Attempt UPSC CSE with Mains answer-writing practice.",
            "Clear interview; join service / State PSC alternative.",
        ],
        "related": ["law", "mba"],
    },
    {
        "id": "defence",
        "title": "Defence & Armed Forces (NDA / CDS)",
        "category": "Defence",
        "icon": "🪖",
        "tagline": "Serve the nation in uniform.",
        "description": (
            "A career in the Army, Navy or Air Force via NDA (after 12th) or CDS/AFCAT "
            "(after graduation) offers adventure, discipline and honour."
        ),
        "exams": ["NDA", "CDS", "AFCAT", "INET"],
        "eligibility": "10+2 PCM for NDA (some branches); graduation for CDS.",
        "top_colleges": [
            "National Defence Academy (NDA) Khadakwasla",
            "IMA Dehradun",
            "OTA Chennai",
            "AFA Dundigal",
        ],
        "skills": ["Physical fitness", "Leadership", "Discipline", "Aptitude"],
        "scope": "Commissioned officer (Army/Navy/Air Force), pilot, engineer in forces.",
        "salary": "₹8–20 LPA + allowances; excellent facilities.",
        "growth": "Prestigious, stable; leadership-track career.",
        "roadmap": [
            "Stay fit; take PCM for technical branches.",
            "Crack NDA (written + SSB) after 12th.",
            "Or graduate and attempt CDS/AFCAT.",
            "Clear SSB interview + medical.",
            "Train at academy; get commissioned.",
        ],
        "related": ["civil-services", "aerospace-engineering"],
    },
    {
        "id": "agriculture",
        "title": "Agriculture & Agri-Tech (B.Sc Ag)",
        "category": "Agriculture",
        "icon": "🌾",
        "tagline": "Feed the nation with science and innovation.",
        "description": (
            "Agriculture science covers crop production, soil, agribusiness and modern "
            "agri-tech. With food security and tech-driven farming, it's a future-ready field."
        ),
        "exams": ["CUET", "ICAR AIEEA", "State agriculture CET"],
        "eligibility": "10+2 PCB/PCM/Agriculture.",
        "top_colleges": [
            "IARI Delhi",
            "NDRI Karnal",
            "GB Pant University",
            "TNAU Coimbatore",
            "PAU Ludhiana",
        ],
        "skills": [
            "Agronomy",
            "Soil science",
            "Biotech",
            "Agribusiness",
            "Data (agri-tech)",
        ],
        "scope": "Agronomist, agri-officer, agri-tech startup, research, extension services.",
        "salary": "₹4–12 LPA; agri-tech firms pay competitively.",
        "growth": "Rising with agri-tech, sustainability and exports.",
        "roadmap": [
            "Take PCB/PCM or Agriculture in 10+2.",
            "Enter via ICAR/CUET.",
            "Complete B.Sc (Hons) Agriculture.",
            "Intern with agri-tech / govt schemes.",
            "M.Sc / agribusiness or start a venture.",
        ],
        "related": ["veterinary", "bsc-pure-sciences"],
    },
    {
        "id": "mass-communication",
        "title": "Journalism & Mass Communication",
        "category": "Media & Communication",
        "icon": "🎙️",
        "tagline": "Tell stories that inform and inspire.",
        "description": (
            "Mass communication covers journalism, TV/radio, PR and digital media. Graduates "
            "work in news, content, broadcasting and corporate communications."
        ),
        "exams": ["CUET", "IIMC Entrance", "XIC Test", "Private university tests"],
        "eligibility": "10+2 any stream.",
        "top_colleges": [
            "IIMC Delhi",
            "Xavier Institute of Communication Mumbai",
            "Lady Shri Ram Delhi",
            "ACJ Chennai",
            "Symbiosis Pune",
        ],
        "skills": ["Writing", "Reporting", "Video/audio", "Social media", "Curiosity"],
        "scope": "Journalist, anchor, PR specialist, content creator, corporate comms.",
        "salary": "₹3–12 LPA; digital & PR roles growing fast.",
        "growth": "Strong in digital media, PR and content economy.",
        "roadmap": [
            "Take any stream; build writing/speaking skills.",
            "Crack IIMC/XIC/college entrance.",
            "Complete BJMC / MJMC.",
            "Intern with a newsroom / agency.",
            "Specialize (PR, broadcast, digital).",
        ],
        "related": ["ux-design", "mba"],
    },
    {
        "id": "hotel-management",
        "title": "Hotel & Hospitality Management",
        "category": "Hospitality & Sports",
        "icon": "🏨",
        "tagline": "Create world-class guest experiences.",
        "description": (
            "Hospitality management covers hotels, tourism, events and food service. It builds "
            "operations, service and leadership skills for a global industry."
        ),
        "exams": ["NCHM JEE", "CUET", "Private university tests"],
        "eligibility": "10+2 any stream.",
        "top_colleges": [
            "IHM Pusa Delhi",
            "IHM Mumbai",
            "Welcomgroup (WGSHA) Manipal",
            "IHM Bangalore",
            "Christ University",
        ],
        "skills": ["Operations", "Service", "Events", "Languages", "People management"],
        "scope": "Hotel manager, event planner, cruise/hospitality, tourism entrepreneur.",
        "salary": "₹3–12 LPA; international hospitality pays more.",
        "growth": "Recovering & growing with travel/tourism boom.",
        "roadmap": [
            "Take any stream in 10+2.",
            "Crack NCHM JEE for IHMs.",
            "Complete BHMCT (3–4 yrs) + industrial training.",
            "Work in top hotel chains.",
            "Move into management / entrepreneurship.",
        ],
        "related": ["mass-communication", "mba"],
    },
]

# Maps each career category to the academic context it relates to. Used to power
# class / stream / domain filtering without hand-editing every career entry.
CATEGORY_META = {
    "Engineering": {
        "classes": ["12th", "Graduation"],
        "streams": ["PCM", "PCMB", "PCMc"],
        "domain": "Engineering & Technology",
    },
    "Medical & Health": {
        "classes": ["12th", "Graduation"],
        "streams": ["PCMB"],
        "domain": "Healthcare & Medicine",
    },
    "Sciences": {
        "classes": ["12th", "Graduation"],
        "streams": ["PCM", "PCMB"],
        "domain": "Pure & Applied Sciences",
    },
    "Commerce & Finance": {
        "classes": ["12th", "Graduation"],
        "streams": ["Commerce"],
        "domain": "Commerce, Finance & Accounting",
    },
    "Management": {
        "classes": ["Graduation"],
        "streams": [],
        "domain": "Management & Business Administration",
    },
    "Law": {
        "classes": ["12th", "Graduation"],
        "streams": [],
        "domain": "Law & Legal Studies",
    },
    "Design & Creative": {
        "classes": ["12th", "Graduation"],
        "streams": [],
        "domain": "Design & Creative Arts",
    },
    "Civil Services & Government": {
        "classes": ["Graduation", "12th"],
        "streams": [],
        "domain": "Civil Services & Public Administration",
    },
    "Defence": {
        "classes": ["12th", "Graduation"],
        "streams": ["PCM"],
        "domain": "Defence & Armed Forces",
    },
    "Agriculture": {
        "classes": ["12th", "Graduation"],
        "streams": ["PCM", "PCMB"],
        "domain": "Agriculture & Agri-Tech",
    },
    "Media & Communication": {
        "classes": ["12th", "Graduation"],
        "streams": [],
        "domain": "Media, Journalism & Communication",
    },
    "Hospitality & Sports": {
        "classes": ["12th", "Graduation"],
        "streams": [],
        "domain": "Hospitality, Travel & Sports",
    },
}


def _enrich():
    for c in CAREERS:
        meta = CATEGORY_META.get(
            c["category"],
            {"classes": ["12th", "Graduation"], "streams": [], "domain": c["category"]},
        )
        c["classes"] = meta["classes"]
        c["streams"] = meta["streams"]
        c["domains"] = [meta["domain"]]


_enrich()


def list_careers(category=None, cls=None, stream=None, domain=None, q=None):
    out = CAREERS
    if category:
        out = [c for c in out if c["category"].lower() == str(category).lower()]
    if cls:
        out = [c for c in out if cls in c.get("classes", [])]
    if stream:
        out = [
            c for c in out if (not c.get("streams")) or (stream in c.get("streams", []))
        ]
    if domain:
        out = [c for c in out if domain in c.get("domains", [])]
    if q:
        ql = str(q).lower()
        out = [
            c
            for c in out
            if ql in c["title"].lower()
            or ql in c["category"].lower()
            or ql in c.get("tagline", "").lower()
            or any(ql in d.lower() for d in c.get("domains", []))
        ]
    return out


def get_career(career_id):
    for c in CAREERS:
        if c["id"] == career_id:
            return c
    return None


def list_categories():
    seen = []
    for c in CAREERS:
        if c["category"] not in seen:
            seen.append(c["category"])
    return seen


def list_domains():
    seen = []
    for c in CAREERS:
        for d in c.get("domains", []):
            if d not in seen:
                seen.append(d)
    return seen


def list_streams():
    seen = []
    for c in CAREERS:
        for s in c.get("streams", []):
            if s not in seen:
                seen.append(s)
    return seen


def list_classes():
    return ["10th", "12th", "Diploma", "Graduation"]
