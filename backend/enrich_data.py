import re, json

PATH = "backend/database/seed.py"
src = open(PATH, encoding="utf-8").read()

# ---------- 1. College NIRF / package corrections ----------
college_fixes = {
    "IIT Kharagpur": (6, "18.5"),
    "Jadavpur University": (34, "9.0"),
    "IIEST Shibpur": (None, "8.2"),
    "NIT Durgapur": (None, "7.6"),
    "NIT Trichy": (10, "11.2"),
    "BITS Pilani": (20, "18.0"),
    "Delhi University": (36, "7.0"),
    "Anna University": (14, "8.0"),
    "VIT Vellore": (None, "6.0"),
    "IIT Bombay": (3, "22.0"),
    "IIT Delhi": (4, "20.0"),
    "Jawaharlal Nehru University": (9, "9.0"),
    "Banaras Hindu University": (35, "7.5"),
    "SRM Institute of Science & Technology": (None, "5.0"),
    "Manipal Academy of Higher Education": (None, "7.0"),
    "Amrita Vishwa Vidyapeetham": (None, "6.0"),
    "University of Calcutta": (None, "5.5"),
    "IISc Bangalore": (2, "16.0"),
    "IIT Madras": (1, "20.0"),
    "IIT Kanpur": (5, "19.0"),
    "IIT Roorkee": (7, "17.0"),
    "IIT Guwahati": (8, "15.0"),
    "IIT Hyderabad": (11, "19.0"),
    "IIT (BHU) Varanasi": (13, "15.0"),
    "IIT Indore": (16, "19.0"),
    "IIT Ropar": (19, "15.0"),
    "IIT Gandhinagar": (18, "14.0"),
    "IIT Bhubaneswar": (23, "12.0"),
    "IIT Patna": (21, "14.0"),
    "IIT Jodhpur": (22, "13.0"),
    "IIT (ISM) Dhanbad": (17, "13.0"),
    "NIT Surathkal": (12, "12.0"),
    "NIT Warangal": (24, "12.0"),
    "NIT Rourkela": (15, "11.0"),
    "NIT Calicut": (25, "10.0"),
    "NIT Jaipur": (26, "9.0"),
    "NIT Nagpur": (27, "9.0"),
    "SVNIT Surat": (28, "8.5"),
    "MNNIT Allahabad": (29, "9.0"),
    "MANIT Bhopal": (30, "8.5"),
    "NIT Kurukshetra": (31, "9.0"),
    "NIT Jamshedpur": (32, "8.0"),
    "NIT Silchar": (33, "7.5"),
    "IIIT Hyderabad": (None, "24.0"),
    "IIIT Delhi": (None, "16.0"),
    "DTU Delhi": (None, "12.0"),
    "NSUT Delhi": (None, "13.0"),
    "COEP Pune": (None, "10.0"),
    "PSG College of Technology": (None, "6.0"),
    "Thapar Institute": (None, "8.0"),
    "BIT Mesra": (None, "7.0"),
    "Lovely Professional University": (None, "5.0"),
    "Amity University": (None, "4.5"),
    "Ashoka University": (None, "8.0"),
    "Shiv Nadar University": (None, "7.0"),
    "IIM Ahmedabad": (None, "33.0"),
    "IIM Bangalore": (None, "32.0"),
    "IIM Calcutta": (None, "31.0"),
    "IIM Lucknow": (None, "28.0"),
    "IIM Indore": (None, "25.0"),
    "IIM Kozhikode": (None, "26.0"),
    "FMS Delhi": (None, "34.0"),
    "AIIMS Delhi": (None, "12.0"),
    "AIIMS Bhubaneswar": (None, "11.0"),
    "AIIMS Jodhpur": (None, "11.0"),
    "AIIMS Bhopal": (None, "11.0"),
    "IISER Pune": (None, "9.0"),
    "IISER Kolkata": (None, "9.0"),
    "IISER Bhopal": (None, "9.0"),
    "NLSIU Bangalore": (None, "12.0"),
    "NID Ahmedabad": (None, "8.0"),
    "Presidency University Kolkata": (None, "5.0"),
    "ISI Kolkata": (None, "12.0"),
    "St. Stephen's College": (None, "6.0"),
    "BIT Sindri": (None, "6.0"),
}

# ---------- 2. College enrichment (real, accurate) ----------
ENRICH = {
    "IIT Kharagpur": (
        "iitkgp.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1951",
        "India's first IIT and among its largest, known for research, fests and alumni.",
        [
            "Huge alumni & research network",
            "Excellent placements & brand",
            "Vibrant campus life (Spring Fest, Kshitij)",
        ],
        ["Remote location (Kharagpur)", "Very large, spread-out campus"],
    ),
    "Jadavpur University": (
        "jaduniv.edu.in",
        "State University, Govt. of West Bengal",
        "1955",
        "Premier public university in Kolkata with strong engineering, arts & science.",
        [
            "Very low fees, high ROI",
            "Strong faculty & research",
            "Excellent CSE/ECE placements",
        ],
        ["Aging infrastructure", "Admission highly competitive"],
    ),
    "IIEST Shibpur": (
        "iiests.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1856",
        "One of India's oldest engineering institutions, now an INI near Kolkata.",
        [
            "Historic, well-regarded brand",
            "Good core-engineering placements",
            "Government-funded, low fees",
        ],
        ["Smaller campus", "Fewer CS/IT recruiters than IITs"],
    ),
    "NIT Durgapur": (
        "nitdgp.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1960",
        "Leading NIT in West Bengal with solid engineering programs.",
        [
            "National brand, low fees",
            "Decent core & IT placements",
            "Active student clubs",
        ],
        ["Limited higher-end packages", "Smaller than metro campuses"],
    ),
    "NIT Trichy": (
        "nitt.edu",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1964",
        "Consistently India's top NIT, excellent placements across branches.",
        [
            "Top NIRF rank among NITs",
            "Outstanding placements & infrastructure",
            "Strong alumni network",
        ],
        ["Highly competitive", "Large batch sizes"],
    ),
    "BITS Pilani": (
        "bits-pilani.ac.in",
        "Deemed University (Private)",
        "1964",
        "Prestigious private institute famed for freedom, entrepreneurship & placements.",
        [
            "No attendance policy",
            "Excellent peer group & recruiters",
            "Strong startup culture",
        ],
        ["High tuition fees", "Competitive academics"],
    ),
    "Delhi University": (
        "du.ac.in",
        "Central University, GoI",
        "1922",
        "India's largest & most prestigious public university with top colleges.",
        [
            "Iconic brand & alumni",
            "Very low fees",
            "Great arts/commerce/science colleges",
        ],
        [
            "North Campus most sought-after",
            "Limited central placements for some courses",
        ],
    ),
    "Anna University": (
        "annauniv.edu",
        "State University, Govt. of Tamil Nadu",
        "1978",
        "Tamil Nadu's apex technical university; top engineering admissions.",
        [
            "Strong regional brand",
            "Good placements in South India",
            "Research-oriented",
        ],
        ["Affiliated-college quality varies", "Large bureaucracy"],
    ),
    "VIT Vellore": (
        "vit.ac.in",
        "Deemed University (Private)",
        "1984",
        "Large private university known for smooth placements & global tie-ups.",
        [
            "Very high placement volume",
            "Good infrastructure",
            "Category-based admission",
        ],
        ["Strict rules & heavy fees", "Large student population"],
    ),
    "IIT Bombay": (
        "iitb.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1958",
        "India's top IIT for technology, entrepreneurship and research.",
        [
            "Best brand for tech/startups",
            "Outstanding packages & alumni",
            "Mumbai location",
        ],
        ["Extremely competitive", "Costly city, demanding workload"],
    ),
    "IIT Delhi": (
        "iitd.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "Premier IIT in the capital with elite research & placements.",
        [
            "Top recruiters & research",
            "Delhi location & network",
            "Strong entrepreneurial ecosystem",
        ],
        ["High competition", "Dense, fast-paced campus"],
    ),
    "Jawaharlal Nehru University": (
        "jnu.ac.in",
        "Central University, GoI",
        "1969",
        "Renowned for social sciences, languages and a vibrant intellectual culture.",
        [
            "Low fees, rich academics",
            "Excellent for humanities/social sciences",
            "Iconic campus life",
        ],
        ["Limited engineering/placement focus", "Occasional campus disruptions"],
    ),
    "Banaras Hindu University": (
        "bhu.ac.in",
        "Central University, GoI",
        "1916",
        "Historic central university in Varanasi with diverse programs.",
        [
            "Vast, green campus",
            "Low fees, broad offerings",
            "Strong medical & sciences",
        ],
        ["Slow administrative processes", "Placements uneven outside top branches"],
    ),
    "SRM Institute of Science & Technology": (
        "srmist.edu.in",
        "Deemed University (Private)",
        "1985",
        "Major private university with large campuses and decent placements.",
        ["Good IT placements", "Modern infrastructure", "Multiple campuses"],
        ["High fees", "Variable branch quality"],
    ),
    "Manipal Academy of Higher Education": (
        "manipal.edu",
        "Deemed University (Private)",
        "1953",
        "Well-known private deemed university with strong health sciences.",
        [
            "Excellent medical & engineering",
            "Picturesque campus",
            "Good international exposure",
        ],
        ["High tuition", "Competitive for top branches"],
    ),
    "Amrita Vishwa Vidyapeetham": (
        "amrita.edu",
        "Deemed University (Private)",
        "1994",
        "Values-based private university strong in engineering & health.",
        [
            "Good placements & discipline",
            "Strong research centers",
            "Multi-state campuses",
        ],
        ["Strict rules", "High fees"],
    ),
    "University of Calcutta": (
        "caluniv.ac.in",
        "State University, Govt. of West Bengal",
        "1857",
        "One of India's oldest universities; affiliates many Kolkata colleges.",
        ["Historic prestige", "Very low fees", "Strong science & arts"],
        ["Affiliated-college dependence", "Limited central placements"],
    ),
    "IISc Bangalore": (
        "iisc.ac.in",
        "Ministry of Science & Technology, GoI",
        "1909",
        "India's foremost institute for advanced scientific research.",
        ["World-class research", "Best for MS/PhD & science", "Excellent faculty"],
        ["Research-focused, fewer UG seats", "Highly selective"],
    ),
    "IIT Madras": (
        "iitm.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1959",
        "India's #1 ranked IIT for several years; superb research & placements.",
        [
            "Top NIRF ranking",
            "Excellent CS & core placements",
            "Strong incubation/startups",
        ],
        ["Competitive, demanding", "Chennai heat (minor)"],
    ),
    "IIT Kanpur": (
        "iitk.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1959",
        "Pioneering IIT known for academics, aerospace and entrepreneurship.",
        ["Excellent academics & labs", "Strong alumni network", "Good placements"],
        ["Demanding coursework", "Smaller town"],
    ),
    "IIT Roorkee": (
        "iitr.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1847",
        "Asia's oldest technical institution; strong civil & engineering.",
        ["Historic legacy", "Excellent core engineering", "Good placements"],
        ["Smaller town (Roorkee)", "Cold winters"],
    ),
    "IIT Guwahati": (
        "iitg.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1994",
        "Scenic, fast-rising IIT in Northeast India.",
        ["Beautiful campus", "Growing placements & research", "Modern infrastructure"],
        ["Remote location", "Fewer recruiters than older IITs"],
    ),
    "IIT Hyderabad": (
        "iith.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "Young, research-intensive IIT with strong industry collaboration.",
        [
            "Excellent new-age curriculum",
            "Great CS placements",
            "Proximity to Hyderabad tech hub",
        ],
        ["Younger alumni network", "Still expanding"],
    ),
    "IIT (BHU) Varanasi": (
        "iitbhu.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1919",
        "Historic IIT in Varanasi with growing placements.",
        ["Old campus & brand", "Good core & CS placements", "Low fees"],
        ["Administrative legacy issues", "Smaller than top IITs"],
    ),
    "IIT Indore": (
        "iiti.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2009",
        "Fast-rising IIT with modern campus and strong research.",
        ["Excellent new campus", "Strong placements & research", "Discipline-focused"],
        ["Younger alumni base", "Smaller cohort"],
    ),
    "IIT Ropar": (
        "iitrpr.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "Compact, research-led IIT in Punjab.",
        ["Good faculty-to-student ratio", "Solid placements", "Modern labs"],
        ["Small campus", "Limited city exposure"],
    ),
    "IIT Gandhinagar": (
        "iitgn.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "Liberal-arts-influenced IIT with innovative pedagogy.",
        ["Unique holistic curriculum", "Strong international links", "Good placements"],
        ["Small, still growing", "Newer brand"],
    ),
    "IIT Bhubaneswar": (
        "iitbbs.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "Young IIT in Odisha with developing infrastructure.",
        ["Good faculty", "Growing placements", "Government-funded"],
        ["Under-construction campus", "Smaller recruiter pool"],
    ),
    "IIT Patna": (
        "iitp.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "Emerging IIT with improving placements.",
        ["Low fees, good academics", "Rising CS placements", "Modern campus"],
        ["Young institution", "Limited legacy network"],
    ),
    "IIT Jodhpur": (
        "iitj.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "New-generation IIT in Rajasthan.",
        ["Modern interdisciplinary focus", "Good placements", "New campus"],
        ["Younger brand", "Small cohort"],
    ),
    "IIT (ISM) Dhanbad": (
        "iitism.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1926",
        "Legacy mining institute, now a top IIT with broad branches.",
        [
            "Strong earth-sciences & mining",
            "Good core placements",
            "Old institutional trust",
        ],
        ["Specialised reputation", "Smaller town"],
    ),
    "NIT Surathkal": (
        "nitk.edu.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1960",
        "Top NIT in Karnataka with beachside campus.",
        ["Excellent placements", "Beautiful campus near sea", "Strong alumni"],
        ["Highly competitive", "Large batches"],
    ),
    "NIT Warangal": (
        "nitw.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1959",
        "Among the oldest & best NITs in South India.",
        ["Strong brand & placements", "Good infrastructure", "Active fests"],
        ["Competitive entry", "Big batches"],
    ),
    "NIT Rourkela": (
        "nitrkl.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "Large, well-ranked NIT in Odisha.",
        ["Excellent campus & labs", "Strong placements", "Research-active"],
        ["Remote location", "Large cohort"],
    ),
    "NIT Calicut": (
        "nitc.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "Leading NIT in Kerala with solid academics.",
        ["Good placements & faculty", "Scenic campus", "Strong CS/EC"],
        ["Remote (Kozhikode outskirts)", "Smaller recruiter pool than top NITs"],
    ),
    "NIT Jaipur": (
        "mnit.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1963",
        "Reputed NIT in Rajasthan's capital.",
        ["Good placements", "Jaipur location", "Modern campus"],
        ["Growing but competitive", "Large batches"],
    ),
    "NIT Nagpur": (
        "vnit.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1960",
        "Established NIT in Maharashtra.",
        ["Strong core & IT placements", "Good alumni", "Central India location"],
        ["Administrative slowness", "Big batches"],
    ),
    "SVNIT Surat": (
        "svnit.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "NIT in Gujarat with decent placements.",
        ["Good industry links (Surat)", "Low fees", "Solid academics"],
        ["Smaller brand than top NITs", "Limited high-end packages"],
    ),
    "MNNIT Allahabad": (
        "mnnit.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "Historic NIT in Prayagraj, strong in CS.",
        ["Excellent CS placements", "Low fees", "Good alumni"],
        ["Tier-2 city", "Large batches"],
    ),
    "MANIT Bhopal": (
        "manit.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1960",
        "NIT in Madhya Pradesh's capital.",
        ["Decent placements", "Central location", "Low fees"],
        ["Infrastructure gaps", "Competitive entry"],
    ),
    "NIT Kurukshetra": (
        "nitkkr.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1963",
        "Well-known NIT in Haryana.",
        ["Good placements", "Proximity to Delhi NCR", "Low fees"],
        ["Large batches", "Tier-2 city"],
    ),
    "NIT Jamshedpur": (
        "nitjsr.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1960",
        "NIT in Jharkhand's industrial city.",
        ["Industry proximity (Jamshedpur)", "Good core placements", "Low fees"],
        ["Smaller campus", "Tier-2 city"],
    ),
    "NIT Silchar": (
        "nits.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1967",
        "NIT serving Northeast India.",
        ["Government-funded, low fees", "Growing placements", "Regional importance"],
        ["Remote location", "Smaller recruiter pool"],
    ),
    "IIIT Hyderabad": (
        "iiit.ac.in",
        "Deemed University (Public-Private Partnership)",
        "1998",
        "Elite research-focused institute, among India's best for CS.",
        [
            "Outstanding CS research & placements",
            "Strong industry collaboration",
            "Excellent faculty",
        ],
        ["High fees for private model", "Extremely competitive"],
    ),
    "IIIT Delhi": (
        "iiitd.ac.in",
        "State University, Govt. of NCT Delhi",
        "2008",
        "Research-intensive state university strong in CS/ECE.",
        ["Great CS placements & research", "Delhi location", "Modern curriculum"],
        ["Demanding coursework", "Smaller than IITs"],
    ),
    "DTU Delhi": (
        "dtu.ac.in",
        "State University, Govt. of NCT Delhi",
        "1941",
        "Historic technical university in Delhi with strong placements.",
        ["Excellent Delhi location & alumni", "Good core & IT placements", "Low fees"],
        ["Large batches", "Some aging infrastructure"],
    ),
    "NSUT Delhi": (
        "nsut.ac.in",
        "State University, Govt. of NCT Delhi",
        "1983",
        "Top Delhi state university with great tech placements.",
        ["Strong CS/IT placements", "Delhi network", "Low fees"],
        ["Competitive entry", "Growing campus"],
    ),
    "COEP Pune": (
        "coep.ac.in",
        "Autonomous, affiliated to Savitribai Phule Pune University",
        "1854",
        "Maharashtra's premier government engineering college.",
        ["Historic brand & alumni", "Excellent Pune location", "Strong placements"],
        ["Affiliation constraints", "Highly competitive"],
    ),
    "PSG College of Technology": (
        "psgtech.edu.in",
        "Autonomous, affiliated to Anna University",
        "1951",
        "Top private-aided engineering college in Tamil Nadu.",
        ["Excellent placements", "Strong industry ties", "Reputed brand"],
        ["Strict discipline", "High cutoff"],
    ),
    "Thapar Institute": (
        "thapar.edu",
        "Deemed University (Private)",
        "1956",
        "Long-established private institute in Punjab.",
        ["Good placements & alumni", "Modern campus", "Strong academics"],
        ["High fees", "Competitive for top branches"],
    ),
    "BIT Mesra": (
        "bitmesra.ac.in",
        "Deemed University (Private)",
        "1955",
        "Reputed private deemed university in Ranchi.",
        ["Good placements & alumni", "Established brand", "Multiple campuses"],
        ["High fees", "Tier-2 city (Ranchi)"],
    ),
    "Lovely Professional University": (
        "lpu.in",
        "Private University (Punjab)",
        "2005",
        "Very large private university with massive placement drives.",
        ["Huge placement volume", "Modern infrastructure", "Diverse programs"],
        ["High fees", "Variable branch quality"],
    ),
    "Amity University": (
        "amity.edu",
        "Private University",
        "2005",
        "Large private university with pan-India campuses.",
        [
            "Good infrastructure",
            "Decent placements for top branches",
            "Industry exposure",
        ],
        ["High fees", "Variable academic rigour"],
    ),
    "Ashoka University": (
        "ashoka.edu.in",
        "Private University (Haryana)",
        "2014",
        "India's leading liberal-arts university.",
        [
            "Excellent liberal-arts education",
            "Great faculty & exposure",
            "Strong peer group",
        ],
        ["Very high fees", "Limited engineering/tech focus"],
    ),
    "Shiv Nadar University": (
        "snu.edu.in",
        "Private University (Uttar Pradesh)",
        "2011",
        "Research-oriented private university near Delhi NCR.",
        ["Good faculty & infrastructure", "Growing placements", "Multidisciplinary"],
        ["Young institution", "High fees"],
    ),
    "IIM Ahmedabad": (
        "iima.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "India's top business school with global repute.",
        [
            "Best B-school brand in India",
            "Exceptional placements",
            "World-class faculty",
        ],
        ["Extremely competitive", "Very high fees"],
    ),
    "IIM Bangalore": (
        "iimb.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1973",
        "Elite B-school known for finance, consulting & research.",
        ["Top placements & alumni", "Bengaluru location", "Excellent faculty"],
        ["High fees", "Highly competitive"],
    ),
    "IIM Calcutta": (
        "iimcal.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1961",
        "India's first IIM; strong in finance & analytics.",
        ["Pioneer IIM brand", "Great finance placements", "Strong alumni"],
        ["High fees", "Competitive"],
    ),
    "IIM Lucknow": (
        "iiml.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1984",
        "Top-tier IIM with strong general-management placements.",
        ["Excellent placements", "Strong brand", "Good campus"],
        ["High fees", "Competitive"],
    ),
    "IIM Indore": (
        "iimidr.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1996",
        "Fast-rising IIM with large integrated programs.",
        ["Strong placements & brand", "Modern campus", "IPM program"],
        ["High fees", "Competitive"],
    ),
    "IIM Kozhikode": (
        "iimk.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "1996",
        "Top IIM known for diverse, inclusive cohorts.",
        ["Good placements & culture", "Scenic campus", "Strong brand"],
        ["High fees", "Competitive"],
    ),
    "FMS Delhi": (
        "fms.edu",
        "Constituent of University of Delhi",
        "1954",
        "Top public B-school with unbeatable ROI.",
        [
            "Extremely low fees, high ROI",
            "Excellent placements",
            "Delhi University brand",
        ],
        ["No hostel for all", "Highly competitive"],
    ),
    "AIIMS Delhi": (
        "aiims.edu",
        "Ministry of Health & Family Welfare, GoI (Institute of National Importance)",
        "1956",
        "India's premier medical institute and hospital.",
        [
            "Top medical education & research",
            "Huge clinical exposure",
            "National brand",
        ],
        ["Extremely competitive (NEET)", "Demanding training"],
    ),
    "AIIMS Bhubaneswar": (
        "aiimsbhubaneswar.edu.in",
        "Ministry of Health & Family Welfare, GoI (Institute of National Importance)",
        "2012",
        "New-gen AIIMS in Odisha with growing reputation.",
        ["Government-funded, modern", "Good clinical training", "Low fees"],
        ["Newer institution", "Still building research base"],
    ),
    "AIIMS Jodhpur": (
        "aiimsjodhpur.edu.in",
        "Ministry of Health & Family Welfare, GoI (Institute of National Importance)",
        "2012",
        "New-gen AIIMS in Rajasthan.",
        ["Modern infrastructure", "Low fees, government", "Good training"],
        ["Young institution", "Limited legacy"],
    ),
    "AIIMS Bhopal": (
        "aiimsbhopal.edu.in",
        "Ministry of Health & Family Welfare, GoI (Institute of National Importance)",
        "2012",
        "New-gen AIIMS in Madhya Pradesh.",
        ["Government-funded, modern", "Good clinical exposure", "Low fees"],
        ["Newer", "Still expanding"],
    ),
    "IISER Pune": (
        "iiserpune.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2006",
        "Top institute for basic sciences & research.",
        [
            "World-class science research",
            "Low fees, INI status",
            "Great for PhD pathways",
        ],
        ["Research-focused, fewer UG jobs", "Highly selective"],
    ),
    "IISER Kolkata": (
        "iiserkol.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2006",
        "Leading IISER for integrated science education.",
        ["Strong basic-science research", "Low fees", "Good academic culture"],
        ["Few direct UG placements", "Research-track oriented"],
    ),
    "IISER Bhopal": (
        "iiserb.ac.in",
        "Ministry of Education, GoI (Institute of National Importance)",
        "2008",
        "Multidisciplinary IISER with engineering-sciences.",
        ["Broad science & engineering-science", "Low fees", "Modern campus"],
        ["Younger", "Research-focused"],
    ),
    "NLSIU Bangalore": (
        "nlsiu.edu.in",
        "Public University, Govt. of Karnataka",
        "1987",
        "India's top National Law School.",
        [
            "Best law school in India",
            "Excellent placements (law firms)",
            "Strong alumni",
        ],
        ["Extremely competitive (CLAT)", "Higher fees vs public"],
    ),
    "NID Ahmedabad": (
        "nid.edu",
        "Institute of National Importance, Min. of Commerce & Industry, GoI",
        "1961",
        "India's premier design institute.",
        ["Top design education", "Excellent industry ties", "National brand"],
        ["Very competitive", "Limited seats"],
    ),
    "Presidency University Kolkata": (
        "presiuniv.ac.in",
        "State University, Govt. of West Bengal",
        "1817",
        "Historic elite college/university in Kolkata.",
        [
            "Prestigious academic legacy",
            "Low fees, strong faculty",
            "Great for sciences/humanities",
        ],
        ["Limited professional placements", "Highly rigorous"],
    ),
    "ISI Kolkata": (
        "isical.ac.in",
        "Ministry of Statistics & Programme Implementation, GoI (Institute of National Importance)",
        "1931",
        "World-renowned institute for statistics & mathematics.",
        ["Elite for stats/maths", "Low fees, government", "Excellent research"],
        ["Very selective", "Niche, research-focused"],
    ),
    "St. Stephen's College": (
        "ststephens.edu",
        "Constituent College, University of Delhi (Christian Minority)",
        "1881",
        "India's most prestigious liberal-arts college.",
        ["Top DU college brand", "Excellent humanities/science", "Strong alumni"],
        ["Highly competitive", "Limited professional courses"],
    ),
    "BIT Sindri": (
        "bitsindri.ac.in",
        "State Govt. Engineering College, Jharkhand",
        "1949",
        "Old, respected government engineering college in Jharkhand.",
        ["Low fees, government", "Good alumni in East India", "Solid core branches"],
        ["Infrastructure needs upgrade", "Limited high-end placements"],
    ),
}

# ---------- 3. Scholarship amount fixes ----------
sch_amount_fixes = {
    "NSP - Central Sector Scheme of Scholarships (CSSS)": "₹12,000/year (1st–3rd yr) · ₹20,000 (4th yr, professional)",
    "Pre & Post Matric Scholarship for Minorities (MOMA)": "Up to ₹1,000/year (pre) / actual tuition + maintenance (post)",
    "Swami Vivekananda Merit-cum-Means (SVMCM), WB": "₹8,000 – ₹10,000/month (UG) · ₹10,000 – ₹12,000/month (PG)",
    "Prime Minister's Scholarship Scheme (PMSS)": "₹30,000 (boys) / ₹36,000 (girls) per year (professional courses)",
}

# ---------- 4. Scholarship enrichment ----------
SCH_ENRICH = {
    "Prime Minister's Scholarship Scheme (PMSS)": (
        "Kendriya Sainik Board, Ministry of Defence, GoI",
        "https://ksb.gov.in",
        "For wards of ex-servicemen / serving personnel; professional courses get the higher amount.",
    ),
    "NSP - Central Sector Scheme of Scholarships (CSSS)": (
        "Department of Higher Education, Ministry of Education, GoI (via NSP)",
        "https://scholarships.gov.in",
        "For Class XII top-20% students continuing general or professional UG studies.",
    ),
    "Post Matric Scholarship for SC": (
        "Ministry of Social Justice & Empowerment, GoI (NSP)",
        "https://scholarships.gov.in",
        "Post-matric financial aid for Scheduled Caste students.",
    ),
    "Post Matric Scholarship for OBC": (
        "Ministry of Social Justice & Empowerment, GoI (NSP)",
        "https://scholarships.gov.in",
        "Post-matric aid for OBC students from low-income families.",
    ),
    "Pre & Post Matric Scholarship for Minorities (MOMA)": (
        "Ministry of Minority Affairs, GoI (NSP)",
        "https://scholarships.gov.in",
        "Pre & post-matric support for minority-community students.",
    ),
    "INSPIRE Scholarship (INSPIRE-HELP)": (
        "Department of Science & Technology, GoI",
        "https://inspire.gov.in",
        "For top learners in basic & natural sciences (BSc/MSc).",
    ),
    "AICTE Pragati Scholarship (Girls)": (
        "AICTE, Ministry of Education, GoI",
        "https://www.aicte-india.org",
        "For girls in AICTE-approved technical diploma/degree programs.",
    ),
    "AICTE Saksham Scholarship (PwD)": (
        "AICTE, Ministry of Education, GoI",
        "https://www.aicte-india.org",
        "For PwD students in AICTE-approved technical programs.",
    ),
    "UGC Ishan Uday Scholarship": (
        "UGC, GoI",
        "https://www.ugc.gov.in",
        "For students from North-Eastern states pursuing UG studies.",
    ),
    "Maulana Azad National Fellowship (MANF)": (
        "Ministry of Minority Affairs, GoI (UGC)",
        "https://scholarships.gov.in",
        "Fellowship for minority students pursuing MPhil/PhD.",
    ),
    "National Fellowship for SC (RGF)": (
        "UGC, GoI",
        "https://www.ugc.gov.in",
        "Fellowship for Scheduled Caste scholars (MPhil/PhD).",
    ),
    "Swami Vivekananda Single Girl Child Fellowship (SGC)": (
        "UGC, GoI",
        "https://www.ugc.gov.in",
        "For single girl children pursuing PG studies.",
    ),
    "PM-YASASVI Central Sector Top Class Scheme": (
        "Ministry of Social Justice & Empowerment, GoI (NSP)",
        "https://scholarships.gov.in",
        "Top-class education support for OBC/SC/Denotified tribe students.",
    ),
    "NEC Merit Scholarship": (
        "North Eastern Council, Ministry of DoNER, GoI",
        "https://necouncil.gov.in",
        "Merit scholarship for students from North-Eastern states.",
    ),
    "PM Special Scholarship Scheme for J&K (PMSSS)": (
        "AICTE for J&K (Ministry of Education, GoI)",
        "https://www.aicte-india.org",
        "For J&K students to study in institutions outside the Union Territory.",
    ),
    "Aikyashree (West Bengal Minority Scholarship)": (
        "Minority Affairs & Madrasah Education Dept., Govt. of West Bengal",
        "https://wbmdfc.org",
        "Pre/post-matric scholarships for West Bengal minorities.",
    ),
    "Swami Vivekananda Merit-cum-Means (SVMCM), WB": (
        "Higher Education Dept., Govt. of West Bengal",
        "https://svmmcm.wbhed.gov.in",
        "Merit-cum-means scholarship for West Bengal UG/PG students.",
    ),
    "Kanyashree (West Bengal)": (
        "Dept. of Women Development & Social Welfare, Govt. of West Bengal",
        "https://www.kanyashree.gov.in",
        "Annual incentive for girls continuing education.",
    ),
    "Kerala State Merit Scholarship": (
        "Dept. of Collegiate Education, Govt. of Kerala",
        "https://www.dcescholarship.kerala.gov.in",
        "Merit scholarship for Kerala UG students.",
    ),
    "Kerala Post Matric Scholarship (SC/OBC/General)": (
        "Social Justice / SC-ST-OBC Depts., Govt. of Kerala",
        "https://www.dcescholarship.kerala.gov.in",
        "Post-matric aid for Kerala students by category.",
    ),
    "Tamil Nadu Government School to College Scholarship": (
        "School Education Dept., Govt. of Tamil Nadu",
        "https://www.tn.gov.in",
        "For government-school students entering UG studies.",
    ),
    "Karnataka Vidyasiri / SSP Post Matric": (
        "Social Welfare Dept., Govt. of Karnataka",
        "https://ssp.karnataka.gov.in",
        "Post-matric hostel & scholarship for Karnataka students.",
    ),
    "Maharashtra Rajarshi Shahu Maharaj EBC Scholarship": (
        "Social Justice Dept., Govt. of Maharashtra",
        "https://www.mahadbt.gov.in",
        "For EBC students from Maharashtra.",
    ),
    "Uttar Pradesh Scholarship (Pre/Post Matric)": (
        "Social Welfare Dept., Govt. of Uttar Pradesh",
        "https://scholarship.up.gov.in",
        "Pre/post-matric scholarships for UP students.",
    ),
    "Bihar Scholarship (Post Matric)": (
        "SC/ST/OBC Welfare Dept., Govt. of Bihar",
        "https://pmsonline.bih.nic.in",
        "Post-matric aid for Bihar students.",
    ),
    "Gujarat Mukhyamantri Yuva Swavalamban (MYS) Yojana": (
        "Education Dept., Govt. of Gujarat",
        "https://www.digitalgujarat.gov.in",
        "For Gujarat students within family-income limits.",
    ),
    "Rajasthan Post Matric Scholarship": (
        "Social Justice & Empowerment Dept., Govt. of Rajasthan",
        "https://sje.rajasthan.gov.in",
        "Post-matric aid for Rajasthan students.",
    ),
    "Odisha Post Matric Scholarship (BOC)": (
        "ST/SC Development Dept., Govt. of Odisha",
        "https://scholarship.odisha.gov.in",
        "Post-matric scholarship for Odisha students.",
    ),
    "Reliance Foundation Scholarship": (
        "Reliance Foundation",
        "https://www.reliancefoundation.org",
        "Merit-cum-means for UG students in partner institutions.",
    ),
    "Tata Trusts (Tata Scholars / JN Tata Endowment)": (
        "Tata Trusts",
        "https://www.tatatrusts.org",
        "Loan/grant scholarships for higher studies.",
    ),
    "ONGC Scholarship": (
        "ONGC (CSR)",
        "https://www.ongcindia.com",
        "Merit scholarships for meritorious students (incl. SC/ST/OBC/PwD).",
    ),
    "LIC Golden Jubilee Scholarship": (
        "LIC Golden Jubilee Foundation",
        "https://www.licindia.in",
        "For economically weaker students in 10th/12th/UG.",
    ),
    "HDFC Bank Parivartan Scholarship": (
        "HDFC Bank Parivartan",
        "https://www.hdfcbank.com",
        "Need-based scholarships for school & college students.",
    ),
    "Axis Bank CSSI Scholarship": (
        "Axis Bank Foundation",
        "https://www.axisbankfoundation.org",
        "For students from low-income households.",
    ),
    "Aditya Birla Capital Scholarship": (
        "Aditya Birla Capital",
        "https://www.adityabirlacapital.com",
        "For students from economically weaker sections.",
    ),
    "Keep India Smiling (Colgate)": (
        "Colgate-Palmolive (Keep India Smiling)",
        "https://www.colgate.com",
        "For sports, education & hygiene aspirants.",
    ),
    "JSW Foundation Scholarship": (
        "JSW Foundation",
        "https://www.jsw.in",
        "For meritorious students from JSW-operational districts.",
    ),
    "Sahu Jain Scholarship": (
        "Sahu Jain Trust",
        "https://www.sahujaintrust.org",
        "Need-cum-merit scholarship for Indian students.",
    ),
}


def find_block(name):
    start = src.find('"name": "%s"' % name)
    if start == -1:
        return None, None
    nxt = src.find('"name":', start + 10)
    end = nxt if nxt != -1 else len(src)
    return start, end


def set_field(block, key, value_repr):
    pat = re.compile(r'("%s"\s*:\s*)([^,\n]+)(,?)' % re.escape(key))
    m = pat.search(block)
    if m:
        return (
            block[: m.start()]
            + m.group(1)
            + value_repr
            + (m.group(3) or ",")
            + block[m.end() :]
        )
    idx = block.rstrip().rfind("}")
    pad = "        "
    return block[:idx] + pad + '"%s": %s,\n' % (key, value_repr) + block[idx:]


def vstr(s):
    return json.dumps(s)


def vlist(l):
    return json.dumps(l)


# Apply college NIRF + package
for name, (rk, pkg) in college_fixes.items():
    s, e = find_block(name)
    if s is None:
        print("MISSING COLLEGE:", name)
        continue
    blk = src[s:e]
    blk = set_field(blk, "nirf_rank", "null" if rk is None else str(rk))
    blk = set_field(blk, "avg_package", vstr(pkg))
    src = src[:s] + blk + src[e:]

# Apply college enrichment
for name, (web, aff, fnd, desc, pros, cons) in ENRICH.items():
    s, e = find_block(name)
    if s is None:
        print("MISSING ENRICH:", name)
        continue
    blk = src[s:e]
    blk = set_field(blk, "website", vstr(web))
    blk = set_field(blk, "affiliation", vstr(aff))
    blk = set_field(blk, "founded", vstr(fnd))
    blk = set_field(blk, "description", vstr(desc))
    blk = set_field(blk, "pros", vlist(pros))
    blk = set_field(blk, "cons", vlist(cons))
    src = src[:s] + blk + src[e:]

# Apply scholarship amount fixes
for name, amt in sch_amount_fixes.items():
    s, e = find_block(name)
    if s is None:
        print("MISSING SCH-AMT:", name)
        continue
    blk = src[s:e]
    blk = set_field(blk, "amount", vstr(amt))
    src = src[:s] + blk + src[e:]

# Apply scholarship enrichment
for name, (prov, link, desc) in SCH_ENRICH.items():
    s, e = find_block(name)
    if s is None:
        print("MISSING SCH-ENR:", name)
        continue
    blk = src[s:e]
    blk = set_field(blk, "provider", vstr(prov))
    blk = set_field(blk, "link", vstr(link))
    blk = set_field(blk, "description", vstr(desc))
    src = src[:s] + blk + src[e:]

open(PATH, "w", encoding="utf-8").write(src)
print("seed.py enriched successfully.")
