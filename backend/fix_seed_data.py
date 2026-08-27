import re

PATH = "backend/database/seed.py"
src = open(PATH, encoding="utf-8").read()

# (name) -> (nirf_rank or None, avg_package string or None)
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

# scholarship name -> corrected amount string
scholarship_fixes = {
    "NSP - Central Sector Scheme of Scholarships (CSSS)": "₹12,000/year (1st–3rd yr) · ₹20,000 (4th yr, professional)",
    "Pre & Post Matric Scholarship for Minorities (MOMA)": "Up to ₹1,000/year (pre) / actual tuition + maintenance (post)",
    "Swami Vivekananda Merit-cum-Means (SVMCM), WB": "₹8,000 – ₹10,000/month (UG) · ₹10,000 – ₹12,000/month (PG)",
    "Prime Minister's Scholarship Scheme (PMSS)": "₹30,000 (boys) / ₹36,000 (girls) per year (professional courses)",
}


def fix_college(name, rank, pkg):
    global src
    start = src.find('"name": "%s"' % name)
    if start == -1:
        print("COLLEGE NOT FOUND:", name)
        return
    nxt = src.find('"name":', start + 10)
    end = nxt if nxt != -1 else len(src)
    block = src[start:end]
    block = re.sub(
        r'"nirf_rank":\s*[^,\n]+,',
        '"nirf_rank": %s,' % ("null" if rank is None else rank),
        block,
        count=1,
    )
    if pkg is None:
        block = re.sub(
            r'"avg_package":\s*"[^"]*",', '"avg_package": null,', block, count=1
        )
    else:
        block = re.sub(
            r'"avg_package":\s*"[^"]*",', '"avg_package": "%s",' % pkg, block, count=1
        )
    src = src[:start] + block + src[end:]


def fix_scholarship(name, amount):
    global src
    start = src.find('"name": "%s"' % name)
    if start == -1:
        print("SCHOLARSHIP NOT FOUND:", name)
        return
    nxt = src.find('"name":', start + 10)
    end = nxt if nxt != -1 else len(src)
    block = src[start:end]
    block = re.sub(r'"amount":\s*"[^"]*",', '"amount": "%s",' % amount, block, count=1)
    src = src[:start] + block + src[end:]


for n, (r, p) in college_fixes.items():
    fix_college(n, r, p)
for n, a in scholarship_fixes.items():
    fix_scholarship(n, a)

open(PATH, "w", encoding="utf-8").write(src)
print("seed.py updated.")
