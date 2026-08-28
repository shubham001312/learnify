# Curated dataset of REAL Indian / global employers, mapped to the career
# categories they hire from. Source of truth for /api/companies and the
# "Top companies that hire" section on career pages.
# Only publicly verifiable companies are included (no fabricated entries).

COMPANIES = [
    # ── Engineering / Tech ──
    {
        "id": "tcs",
        "name": "Tata Consultancy Services",
        "sector": "IT Services & Consulting",
        "description": "India's largest IT services firm; builds software, consulting and BPO solutions for global clients.",
        "website": "https://www.tcs.com",
        "careers": ["Engineering", "Commerce & Finance", "Management"],
    },
    {
        "id": "infosys",
        "name": "Infosys",
        "sector": "IT Services & Consulting",
        "description": "Global IT and consulting company with strong engineering and digital services.",
        "website": "https://www.infosys.com",
        "careers": ["Engineering", "Management"],
    },
    {
        "id": "wipro",
        "name": "Wipro",
        "sector": "IT Services & Consulting",
        "description": "IT, consulting and business process services company.",
        "website": "https://www.wipro.com",
        "careers": ["Engineering", "Management"],
    },
    {
        "id": "hcltech",
        "name": "HCLTech",
        "sector": "IT Services & Consulting",
        "description": "Global technology company providing engineering and cloud services.",
        "website": "https://www.hcltech.com",
        "careers": ["Engineering"],
    },
    {
        "id": "techmahindra",
        "name": "Tech Mahindra",
        "sector": "IT Services & Consulting",
        "description": "IT services and telecom-focused solutions provider.",
        "website": "https://www.techmahindra.com",
        "careers": ["Engineering"],
    },
    {
        "id": "cognizant",
        "name": "Cognizant",
        "sector": "IT Services & Consulting",
        "description": "Digital, technology and consulting services.",
        "website": "https://www.cognizant.com",
        "careers": ["Engineering", "Management"],
    },
    {
        "id": "accenture",
        "name": "Accenture",
        "sector": "Consulting & Technology",
        "description": "Global professional services and technology consultancy.",
        "website": "https://www.accenture.com",
        "careers": ["Engineering", "Management", "Commerce & Finance"],
    },
    {
        "id": "google",
        "name": "Google",
        "sector": "Internet & Technology",
        "description": "Search, cloud, Android and AI products; major employer of engineers and PMs.",
        "website": "https://www.google.com",
        "careers": ["Engineering", "Management", "Design & Creative"],
    },
    {
        "id": "microsoft",
        "name": "Microsoft",
        "sector": "Software & Cloud",
        "description": "Operating systems, cloud (Azure), productivity and gaming.",
        "website": "https://www.microsoft.com",
        "careers": ["Engineering", "Design & Creative"],
    },
    {
        "id": "amazon",
        "name": "Amazon",
        "sector": "E-commerce & Cloud",
        "description": "E-commerce, AWS cloud and devices; large tech employer.",
        "website": "https://www.amazon.jobs",
        "careers": [
            "Engineering",
            "Management",
            "Design & Creative",
            "Commerce & Finance",
        ],
    },
    {
        "id": "apple",
        "name": "Apple",
        "sector": "Consumer Electronics",
        "description": "Designs iPhones, Macs and services; hires hardware/software engineers.",
        "website": "https://www.apple.com",
        "careers": ["Engineering", "Design & Creative"],
    },
    {
        "id": "meta",
        "name": "Meta",
        "sector": "Internet & Social",
        "description": "Facebook, Instagram, WhatsApp and Reality Labs.",
        "website": "https://www.meta.com",
        "careers": ["Engineering", "Design & Creative"],
    },
    {
        "id": "ibm",
        "name": "IBM",
        "sector": "IT & Consulting",
        "description": "Enterprise computing, cloud and AI (watsonx).",
        "website": "https://www.ibm.com",
        "careers": ["Engineering", "Management"],
    },
    {
        "id": "qualcomm",
        "name": "Qualcomm",
        "sector": "Semiconductors",
        "description": "Wireless chipsets and 5G/6G technology.",
        "website": "https://www.qualcomm.com",
        "careers": ["Engineering"],
    },
    {
        "id": "intel",
        "name": "Intel",
        "sector": "Semiconductors",
        "description": "Processor and semiconductor design.",
        "website": "https://www.intel.com",
        "careers": ["Engineering"],
    },
    {
        "id": "nvidia",
        "name": "NVIDIA",
        "sector": "Semiconductors & AI",
        "description": "GPUs and accelerated computing for AI.",
        "website": "https://www.nvidia.com",
        "careers": ["Engineering", "Sciences"],
    },
    {
        "id": "texasinstruments",
        "name": "Texas Instruments",
        "sector": "Semiconductors",
        "description": "Analog and embedded chips.",
        "website": "https://www.ti.com",
        "careers": ["Engineering"],
    },
    {
        "id": "bosch",
        "name": "Bosch",
        "sector": "Engineering & Mobility",
        "description": "Automotive, industrial and consumer tech.",
        "website": "https://www.bosch.com",
        "careers": ["Engineering"],
    },
    {
        "id": "siemens",
        "name": "Siemens",
        "sector": "Industrial & Energy",
        "description": "Electrification, automation and mobility.",
        "website": "https://www.siemens.com",
        "careers": ["Engineering"],
    },
    {
        "id": "cisco",
        "name": "Cisco",
        "sector": "Networking",
        "description": "Networking hardware and security.",
        "website": "https://www.cisco.com",
        "careers": ["Engineering"],
    },
    {
        "id": "samsung",
        "name": "Samsung",
        "sector": "Electronics",
        "description": "Consumer electronics and semiconductors.",
        "website": "https://www.samsung.com",
        "careers": ["Engineering", "Design & Creative"],
    },
    {
        "id": "reljio",
        "name": "Reliance Jio",
        "sector": "Telecom & Digital",
        "description": "India's largest telecom and digital services.",
        "website": "https://www.jio.com",
        "careers": ["Engineering", "Media & Communication"],
    },
    {
        "id": "airtel",
        "name": "Airtel",
        "sector": "Telecom",
        "description": "Telecom and digital services.",
        "website": "https://www.airtel.in",
        "careers": ["Engineering", "Media & Communication"],
    },
    {
        "id": "tatamotors",
        "name": "Tata Motors",
        "sector": "Automotive",
        "description": "Cars, trucks and EVs.",
        "website": "https://www.tatamotors.com",
        "careers": ["Engineering", "Management"],
    },
    {
        "id": "mahindra",
        "name": "Mahindra & Mahindra",
        "sector": "Automotive & Farm",
        "description": "Automotive, tractors and EVs.",
        "website": "https://www.mahindra.com",
        "careers": ["Engineering"],
    },
    {
        "id": "maruti",
        "name": "Maruti Suzuki",
        "sector": "Automotive",
        "description": "India's largest carmaker.",
        "website": "https://www.marutisuzuki.com",
        "careers": ["Engineering"],
    },
    {
        "id": "lnt",
        "name": "Larsen & Toubro",
        "sector": "Engineering & Construction",
        "description": "Infrastructure, EPC and heavy engineering.",
        "website": "https://www.larsentoubro.com",
        "careers": ["Engineering", "Civil Services & Government"],
    },
    {
        "id": "isro",
        "name": "ISRO",
        "sector": "Space & Research",
        "description": "Indian Space Research Organisation.",
        "website": "https://www.isro.gov.in",
        "careers": ["Engineering", "Sciences", "Defence"],
    },
    {
        "id": "drdo",
        "name": "DRDO",
        "sector": "Defence R&D",
        "description": "Defence research and development.",
        "website": "https://www.drdo.gov.in",
        "careers": ["Engineering", "Sciences", "Defence"],
    },
    {
        "id": "hal",
        "name": "Hindustan Aeronautics (HAL)",
        "sector": "Aerospace & Defence",
        "description": "Aircraft manufacturing PSU.",
        "website": "https://www.hal-india.co.in",
        "careers": ["Engineering", "Defence"],
    },
    {
        "id": "bel",
        "name": "Bharat Electronics (BEL)",
        "sector": "Defence Electronics",
        "description": "Defence electronics PSU.",
        "website": "https://bel-india.in",
        "careers": ["Engineering", "Defence"],
    },
    {
        "id": "bhel",
        "name": "BHEL",
        "sector": "Power & Engineering",
        "description": "Power plant equipment PSU.",
        "website": "https://www.bhel.com",
        "careers": ["Engineering"],
    },
    # ── Medical & Health ──
    {
        "id": "aiims",
        "name": "AIIMS",
        "sector": "Hospitals & Research",
        "description": "Premier public medical institute and hospital network.",
        "website": "https://www.aiims.edu",
        "careers": ["Medical & Health", "Sciences"],
    },
    {
        "id": "apollo",
        "name": "Apollo Hospitals",
        "sector": "Healthcare",
        "description": "Large hospital chain.",
        "website": "https://www.apollohospitals.com",
        "careers": ["Medical & Health"],
    },
    {
        "id": "fortis",
        "name": "Fortis Healthcare",
        "sector": "Healthcare",
        "description": "Multi-speciality hospital network.",
        "website": "https://www.fortishealthcare.com",
        "careers": ["Medical & Health"],
    },
    {
        "id": "medanta",
        "name": "Medanta",
        "sector": "Healthcare",
        "description": "Multi-speciality hospital.",
        "website": "https://www.medanta.org",
        "careers": ["Medical & Health"],
    },
    {
        "id": "max",
        "name": "Max Healthcare",
        "sector": "Healthcare",
        "description": "Hospital chain.",
        "website": "https://www.maxhealthcare.in",
        "careers": ["Medical & Health"],
    },
    {
        "id": "tmc",
        "name": "Tata Memorial Centre",
        "sector": "Oncology & Research",
        "description": "Leading cancer care and research.",
        "website": "https://tmc.gov.in",
        "careers": ["Medical & Health", "Sciences"],
    },
    {
        "id": "cipla",
        "name": "Cipla",
        "sector": "Pharmaceuticals",
        "description": "Pharma manufacturing.",
        "website": "https://www.cipla.com",
        "careers": ["Medical & Health"],
    },
    {
        "id": "sunpharma",
        "name": "Sun Pharma",
        "sector": "Pharmaceuticals",
        "description": "Pharma and generics.",
        "website": "https://www.sunpharma.com",
        "careers": ["Medical & Health"],
    },
    {
        "id": "serum",
        "name": "Serum Institute of India",
        "sector": "Vaccines",
        "description": "World's largest vaccine manufacturer.",
        "website": "https://www.seruminstitute.com",
        "careers": ["Medical & Health", "Sciences"],
    },
    {
        "id": "biocon",
        "name": "Biocon",
        "sector": "Biopharma",
        "description": "Biopharmaceuticals and biosimilars.",
        "website": "https://www.biocon.com",
        "careers": ["Medical & Health", "Sciences"],
    },
    {
        "id": "drreddy",
        "name": "Dr Reddy's Laboratories",
        "sector": "Pharmaceuticals",
        "description": "Pharma and generics.",
        "website": "https://www.drreddys.com",
        "careers": ["Medical & Health"],
    },
    # ── Sciences ──
    {
        "id": "iisc",
        "name": "IISc Bengaluru",
        "sector": "Research & Education",
        "description": "Premier science research institute.",
        "website": "https://iisc.ac.in",
        "careers": ["Sciences", "Engineering"],
    },
    {
        "id": "tifr",
        "name": "TIFR",
        "sector": "Research",
        "description": "Tata Institute of Fundamental Research.",
        "website": "https://www.tifr.res.in",
        "careers": ["Sciences"],
    },
    {
        "id": "csir",
        "name": "CSIR",
        "sector": "Research",
        "description": "Council of Scientific & Industrial Research labs.",
        "website": "https://www.csir.res.in",
        "careers": ["Sciences", "Engineering"],
    },
    {
        "id": "thermofisher",
        "name": "Thermo Fisher Scientific",
        "sector": "Biotech & Instruments",
        "description": "Lab instruments and diagnostics.",
        "website": "https://www.thermofisher.com",
        "careers": ["Sciences", "Medical & Health"],
    },
    # ── Commerce & Finance ──
    {
        "id": "deloitte",
        "name": "Deloitte",
        "sector": "Auditing & Consulting",
        "description": "Big Four professional services.",
        "website": "https://www.deloitte.com",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "ey",
        "name": "EY",
        "sector": "Auditing & Consulting",
        "description": "Big Four professional services.",
        "website": "https://www.ey.com",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "kpmg",
        "name": "KPMG",
        "sector": "Auditing & Consulting",
        "description": "Big Four professional services.",
        "website": "https://www.kpmg.com",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "pwc",
        "name": "PwC India",
        "sector": "Auditing & Consulting",
        "description": "Big Four professional services.",
        "website": "https://www.pwc.in",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "hdfcbank",
        "name": "HDFC Bank",
        "sector": "Banking",
        "description": "Major private bank.",
        "website": "https://www.hdfcbank.com",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "icicibank",
        "name": "ICICI Bank",
        "sector": "Banking",
        "description": "Private bank.",
        "website": "https://www.icicibank.com",
        "careers": ["Commerce & Finance"],
    },
    {
        "id": "sbi",
        "name": "State Bank of India",
        "sector": "Banking",
        "description": "Largest public sector bank.",
        "website": "https://www.sbi.co.in",
        "careers": ["Commerce & Finance", "Civil Services & Government"],
    },
    {
        "id": "goldmansachs",
        "name": "Goldman Sachs",
        "sector": "Investment Banking",
        "description": "Global investment bank.",
        "website": "https://www.goldmansachs.com",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "jpmorgan",
        "name": "JPMorgan Chase",
        "sector": "Banking & Finance",
        "description": "Global financial services.",
        "website": "https://www.jpmorgan.com",
        "careers": ["Commerce & Finance", "Management"],
    },
    {
        "id": "morganstanley",
        "name": "Morgan Stanley",
        "sector": "Investment Banking",
        "description": "Financial services.",
        "website": "https://www.morganstanley.com",
        "careers": ["Commerce & Finance"],
    },
    {
        "id": "axisbank",
        "name": "Axis Bank",
        "sector": "Banking",
        "description": "Private bank.",
        "website": "https://www.axisbank.com",
        "careers": ["Commerce & Finance"],
    },
    {
        "id": "nse",
        "name": "NSE India",
        "sector": "Financial Markets",
        "description": "National Stock Exchange.",
        "website": "https://www.nseindia.com",
        "careers": ["Commerce & Finance"],
    },
    # ── Management ──
    {
        "id": "mckinsey",
        "name": "McKinsey & Company",
        "sector": "Management Consulting",
        "description": "Top strategy consultancy.",
        "website": "https://www.mckinsey.com",
        "careers": ["Management", "Commerce & Finance"],
    },
    {
        "id": "bcg",
        "name": "Boston Consulting Group",
        "sector": "Management Consulting",
        "description": "Strategy consultancy.",
        "website": "https://www.bcg.com",
        "careers": ["Management"],
    },
    {
        "id": "bain",
        "name": "Bain & Company",
        "sector": "Management Consulting",
        "description": "Strategy consultancy.",
        "website": "https://www.bain.com",
        "careers": ["Management"],
    },
    {
        "id": "tatagroup",
        "name": "Tata Group",
        "sector": "Conglomerate",
        "description": "Major Indian conglomerate across sectors.",
        "website": "https://www.tata.com",
        "careers": ["Management", "Engineering", "Commerce & Finance"],
    },
    {
        "id": "ril",
        "name": "Reliance Industries",
        "sector": "Conglomerate",
        "description": "Energy, retail and telecom.",
        "website": "https://www.ril.com",
        "careers": ["Management", "Engineering", "Commerce & Finance"],
    },
    {
        "id": "flipkart",
        "name": "Flipkart",
        "sector": "E-commerce",
        "description": "Leading Indian e-commerce.",
        "website": "https://www.flipkart.com",
        "careers": ["Management", "Engineering"],
    },
    {
        "id": "myntra",
        "name": "Myntra",
        "sector": "Fashion E-commerce",
        "description": "Fashion platform.",
        "website": "https://www.myntra.com",
        "careers": ["Management", "Design & Creative"],
    },
    # ── Law ──
    {
        "id": "azb",
        "name": "AZB & Partners",
        "sector": "Law Firm",
        "description": "Leading corporate law firm.",
        "website": "https://www.azbpartners.com",
        "careers": ["Law", "Commerce & Finance"],
    },
    {
        "id": "khaitan",
        "name": "Khaitan & Co",
        "sector": "Law Firm",
        "description": "Corporate law firm.",
        "website": "https://www.khaitanco.com",
        "careers": ["Law"],
    },
    {
        "id": "cam",
        "name": "Cyril Amarchand Mangaldas",
        "sector": "Law Firm",
        "description": "Corporate law firm.",
        "website": "https://www.cyrilamarchand.com",
        "careers": ["Law"],
    },
    {
        "id": "sam",
        "name": "Shardul Amarchand Mangaldas",
        "sector": "Law Firm",
        "description": "Law firm.",
        "website": "https://www.samag.com",
        "careers": ["Law"],
    },
    {
        "id": "trilegal",
        "name": "Trilegal",
        "sector": "Law Firm",
        "description": "Law firm.",
        "website": "https://www.trilegal.com",
        "careers": ["Law"],
    },
    # ── Design & Creative ──
    {
        "id": "tataelxsi",
        "name": "Tata Elxsi",
        "sector": "Design & Technology",
        "description": "Design and engineering services.",
        "website": "https://www.tataelxsi.com",
        "careers": ["Design & Creative", "Engineering"],
    },
    {
        "id": "adobe",
        "name": "Adobe",
        "sector": "Software & Creative",
        "description": "Creative and design software.",
        "website": "https://www.adobe.com",
        "careers": ["Design & Creative", "Engineering"],
    },
    {
        "id": "asianpaints",
        "name": "Asian Paints",
        "sector": "Paints & Design",
        "description": "Decor and design products.",
        "website": "https://www.asianpaints.com",
        "careers": ["Design & Creative"],
    },
    {
        "id": "godrej",
        "name": "Godrej & Boyce",
        "sector": "Consumer & Design",
        "description": "Consumer goods and design.",
        "website": "https://www.godrej.com",
        "careers": ["Design & Creative", "Management"],
    },
    {
        "id": "pepperfry",
        "name": "Pepperfry",
        "sector": "Furniture & Design",
        "description": "Online furniture.",
        "website": "https://www.pepperfry.com",
        "careers": ["Design & Creative"],
    },
    {
        "id": "ogilvy",
        "name": "Ogilvy",
        "sector": "Advertising",
        "description": "Global advertising agency.",
        "website": "https://www.ogilvy.com",
        "careers": ["Media & Communication", "Design & Creative"],
    },
    # ── Civil Services & Government ──
    {
        "id": "upsc",
        "name": "UPSC / Government of India",
        "sector": "Government",
        "description": "Union Public Service Commission & central govt.",
        "website": "https://www.upsc.gov.in",
        "careers": ["Civil Services & Government"],
    },
    {
        "id": "ongc",
        "name": "ONGC",
        "sector": "Energy PSU",
        "description": "Oil & gas PSU.",
        "website": "https://www.ongcindia.com",
        "careers": ["Civil Services & Government", "Engineering"],
    },
    {
        "id": "iocl",
        "name": "Indian Oil",
        "sector": "Energy PSU",
        "description": "Oil PSU.",
        "website": "https://iocl.com",
        "careers": ["Civil Services & Government", "Engineering", "Commerce & Finance"],
    },
    {
        "id": "ntpc",
        "name": "NTPC",
        "sector": "Power PSU",
        "description": "Power generation PSU.",
        "website": "https://www.ntpc.com",
        "careers": ["Civil Services & Government", "Engineering"],
    },
    # ── Defence ──
    {
        "id": "indianarmy",
        "name": "Indian Army",
        "sector": "Defence",
        "description": "Army.",
        "website": "https://joinindianarmy.nic.in",
        "careers": ["Defence", "Engineering"],
    },
    {
        "id": "indiannavy",
        "name": "Indian Navy",
        "sector": "Defence",
        "description": "Navy.",
        "website": "https://www.joinindiannavy.gov.in",
        "careers": ["Defence", "Engineering"],
    },
    {
        "id": "indianairforce",
        "name": "Indian Air Force",
        "sector": "Defence",
        "description": "Air Force.",
        "website": "https://indianairforce.nic.in",
        "careers": ["Defence", "Engineering"],
    },
    # ── Agriculture ──
    {
        "id": "itc",
        "name": "ITC",
        "sector": "FMCG & Agri",
        "description": "Diversified with agri-business.",
        "website": "https://www.itcportal.com",
        "careers": ["Agriculture", "Management"],
    },
    {
        "id": "nestle",
        "name": "Nestlé",
        "sector": "Food & Nutrition",
        "description": "Food and nutrition.",
        "website": "https://www.nestle.in",
        "careers": ["Agriculture", "Management"],
    },
    {
        "id": "pepsico",
        "name": "PepsiCo",
        "sector": "Food & Beverages",
        "description": "Food and beverages.",
        "website": "https://www.pepsico.com",
        "careers": ["Agriculture", "Management"],
    },
    {
        "id": "iffco",
        "name": "IFFCO",
        "sector": "Fertilisers",
        "description": "Cooperative fertiliser.",
        "website": "https://www.iffco.in",
        "careers": ["Agriculture"],
    },
    {
        "id": "nabard",
        "name": "NABARD",
        "sector": "Rural Finance",
        "description": "Agricultural/rural development bank.",
        "website": "https://www.nabard.org",
        "careers": ["Agriculture", "Commerce & Finance", "Civil Services & Government"],
    },
    {
        "id": "upl",
        "name": "UPL",
        "sector": "Agri-Science",
        "description": "Crop protection.",
        "website": "https://www.upl-ltd.com",
        "careers": ["Agriculture"],
    },
    {
        "id": "bayer",
        "name": "Bayer",
        "sector": "Agri & Pharma",
        "description": "Crop science and pharma.",
        "website": "https://www.bayer.com",
        "careers": ["Agriculture", "Medical & Health"],
    },
    {
        "id": "syngenta",
        "name": "Syngenta",
        "sector": "Agri-Science",
        "description": "Crop protection and seeds.",
        "website": "https://www.syngenta.com",
        "careers": ["Agriculture"],
    },
    # ── Media & Communication ──
    {
        "id": "timesgroup",
        "name": "Times Group",
        "sector": "Media",
        "description": "Newspapers, TV and digital.",
        "website": "https://www.timesgroup.com",
        "careers": ["Media & Communication"],
    },
    {
        "id": "network18",
        "name": "Network18",
        "sector": "Media",
        "description": "News and entertainment.",
        "website": "https://www.network18.com",
        "careers": ["Media & Communication"],
    },
    {
        "id": "zee",
        "name": "Zee Entertainment",
        "sector": "Media",
        "description": "TV network.",
        "website": "https://www.zeeentertainment.com",
        "careers": ["Media & Communication"],
    },
    {
        "id": "ndtv",
        "name": "NDTV",
        "sector": "Media",
        "description": "News.",
        "website": "https://www.ndtv.com",
        "careers": ["Media & Communication"],
    },
    {
        "id": "edelman",
        "name": "Edelman",
        "sector": "Public Relations",
        "description": "Global PR firm.",
        "website": "https://www.edelman.com",
        "careers": ["Media & Communication", "Management"],
    },
    {
        "id": "weber",
        "name": "Weber Shandwick",
        "sector": "Public Relations",
        "description": "PR agency.",
        "website": "https://www.webershandwick.com",
        "careers": ["Media & Communication"],
    },
    # ── Hospitality & Sports ──
    {
        "id": "ihcl",
        "name": "IHCL (Taj Hotels)",
        "sector": "Hotels",
        "description": "Taj Hotels.",
        "website": "https://www.tajhotels.com",
        "careers": ["Hospitality & Sports", "Management"],
    },
    {
        "id": "oberoi",
        "name": "Oberoi Hotels",
        "sector": "Hotels",
        "description": "Luxury hotels.",
        "website": "https://www.oberoihotels.com",
        "careers": ["Hospitality & Sports"],
    },
    {
        "id": "marriott",
        "name": "Marriott International",
        "sector": "Hotels",
        "description": "Global hotel chain.",
        "website": "https://www.marriott.com",
        "careers": ["Hospitality & Sports"],
    },
    {
        "id": "oyo",
        "name": "OYO",
        "sector": "Hospitality Tech",
        "description": "Budget hospitality platform.",
        "website": "https://www.oyorooms.com",
        "careers": ["Hospitality & Sports", "Management", "Engineering"],
    },
    {
        "id": "makemytrip",
        "name": "MakeMyTrip",
        "sector": "Travel",
        "description": "Travel booking.",
        "website": "https://www.makemytrip.com",
        "careers": ["Hospitality & Sports", "Management"],
    },
    {
        "id": "decathlon",
        "name": "Decathlon",
        "sector": "Sports Retail",
        "description": "Sports goods retailer.",
        "website": "https://www.decathlon.in",
        "careers": ["Hospitality & Sports"],
    },
]


# ── Derive richer profile fields (clearly sector-typical, not fabricated per-co) ──
HQ_OVERRIDES = {
    "google": "Mountain View, USA (India: Bengaluru)",
    "microsoft": "Redmond, USA (India: Bengaluru / Hyderabad)",
    "amazon": "Seattle, USA (India: Bengaluru / Hyderabad)",
    "apple": "Cupertino, USA (India: Hyderabad)",
    "meta": "Menlo Park, USA (India: Bengaluru)",
    "nvidia": "Santa Clara, USA (India: Bengaluru / Pune)",
    "intel": "Santa Clara, USA (India: Bengaluru)",
    "qualcomm": "San Diego, USA (India: Bengaluru / Hyderabad)",
    "samsung": "Suwon, South Korea (India: Bengaluru / Noida)",
    "cisco": "San Jose, USA (India: Bengaluru / Chennai)",
    "ibm": "Armonk, USA (India: Bengaluru / Kochi)",
    "accenture": "Dublin, Ireland (India: Bengaluru / Mumbai)",
    "adobe": "San Jose, USA (India: Noida / Bengaluru)",
    "deloitte": "London, UK (India: Hyderabad / Mumbai)",
    "ey": "London, UK (India: Bengaluru / Mumbai)",
    "kpmg": "Amstelveen, Netherlands (India: Bengaluru / Mumbai)",
    "pwc": "London, UK (India: Bengaluru / Kolkata)",
    "goldmansachs": "New York, USA (India: Bengaluru)",
    "jpmorgan": "New York, USA (India: Mumbai / Bengaluru)",
    "morganstanley": "New York, USA (India: Mumbai)",
    "bayer": "Leverkusen, Germany (India: Mumbai / Bengaluru)",
    "nestle": "Vevey, Switzerland (India: Gurugram)",
    "pepsico": "Purchase, USA (India: Gurugram)",
    "siemens": "Munich, Germany (India: Bengaluru / Mumbai)",
    "bosch": "Gerlingen, Germany (India: Bengaluru)",
    "thermofisher": "Waltham, USA (India: Bengaluru)",
    "ogilvy": "New York, USA (India: Mumbai / Bengaluru)",
    "mckinsey": "New York, USA (India: Gurugram / Bengaluru)",
    "bcg": "Boston, USA (India: New Delhi / Bengaluru)",
    "bain": "Boston, USA (India: Gurugram / Mumbai)",
    "tcs": "Mumbai, India",
    "infosys": "Bengaluru, India",
    "wipro": "Bengaluru, India",
    "hcltech": "Noida, India",
    "techmahindra": "Pune, India",
    "cognizant": "Teaneck, USA (India: Chennai / Bengaluru)",
    "reliance": "Mumbai, India",
    "ril": "Mumbai, India",
    "tatagroup": "Mumbai, India",
    "tatamotors": "Mumbai, India",
    "mahindra": "Mumbai, India",
    "maruti": "New Delhi, India",
    "lnt": "Mumbai, India",
    "airtel": "New Delhi, India",
    "reljio": "Mumbai, India",
    "hdfcbank": "Mumbai, India",
    "icicibank": "Mumbai, India",
    "sbi": "Mumbai, India",
    "axisbank": "Mumbai, India",
    "flipkart": "Bengaluru, India",
    "myntra": "Bengaluru, India",
    "asianpaints": "Mumbai, India",
    "godrej": "Mumbai, India",
    "itc": "Kolkata, India",
    "oyo": "Gurugram, India",
    "makemytrip": "Gurugram, India",
    "decathlon": "Bengaluru, India",
    "isro": "Bengaluru, India",
    "drdo": "New Delhi, India",
    "aiims": "New Delhi, India",
    "iisc": "Bengaluru, India",
    "upsc": "New Delhi, India",
}


def _sector_profile(sector):
    s = (sector or "").lower()
    if any(
        k in s
        for k in (
            "it ",
            "consult",
            "software",
            "cloud",
            "internet",
            "technology",
            "semicon",
            "electronics",
            "digital",
            "network",
        )
    ):
        return (
            [
                "Software Engineer",
                "Systems Engineer",
                "Data Analyst",
                "Consultant",
                "Product Manager",
            ],
            "₹3.5–8 LPA (fresher)",
            "MNC / Tech",
        )
    if any(k in s for k in ("bank", "finance", "investment", "financial", "audit")):
        return (
            ["Analyst", "Associate", "Risk Manager", "Audit Executive"],
            "₹4–9 LPA (fresher)",
            "Finance",
        )
    if "management" in s:
        return (
            ["Consultant", "Business Analyst", "Project Manager"],
            "₹6–12 LPA (fresher)",
            "Consulting",
        )
    if any(
        k in s
        for k in ("health", "pharma", "vaccine", "biotech", "oncology", "medicine")
    ):
        return (
            [
                "Doctor",
                "Research Associate",
                "Clinical Specialist",
                "Medical Representative",
            ],
            "₹4–10 LPA (fresher)",
            "Healthcare",
        )
    if "law" in s:
        return (
            ["Associate", "Legal Researcher", "Paralegal"],
            "₹3–7 LPA (fresher)",
            "Law Firm",
        )
    if any(k in s for k in ("design", "advertising", "creative")):
        return (
            ["Designer", "Creative Lead", "UX/UI Designer"],
            "₹3–7 LPA (fresher)",
            "Creative",
        )
    if any(k in s for k in ("media", "public relations", "news")):
        return (
            ["Content Producer", "PR Executive", "Journalist"],
            "₹3–6 LPA (fresher)",
            "Media",
        )
    if any(
        k in s
        for k in (
            "automotive",
            "aerospace",
            "defence",
            "space",
            "engineering",
            "power",
            "energy",
            "construction",
            "mobility",
        )
    ):
        return (
            ["Engineer (Core)", "R&D Engineer", "Production Manager"],
            "₹3.5–7 LPA (fresher)",
            "Core / PSU",
        )
    if "government" in s:
        return (
            ["Officer (Govt)", "Civil Servant", "PSU Executive"],
            "₹5–10 LPA (Govt scale)",
            "Government / PSU",
        )
    if any(k in s for k in ("hotel", "hospitality", "travel", "sports")):
        return (
            ["Operations Executive", "Guest Relations", "Management Trainee"],
            "₹2.5–5 LPA (fresher)",
            "Hospitality",
        )
    if any(k in s for k in ("agri", "food", "fertil", "nutrition", "beverage")):
        return (
            ["Agri Officer", "R&D Executive", "Sales Manager"],
            "₹3–6 LPA (fresher)",
            "FMCG / Agri",
        )
    if any(k in s for k in ("research", "science")):
        return (
            ["Research Scientist", "Research Fellow", "Lab Analyst"],
            "₹4–8 LPA (fresher)",
            "Research",
        )
    if any(k in s for k in ("e-commerce", "retail")):
        return (
            ["Category Manager", "Operations Analyst", "Software Engineer"],
            "₹3.5–8 LPA (fresher)",
            "Consumer Tech",
        )
    return (
        ["Engineer", "Analyst", "Manager", "Executive"],
        "₹3.5–7 LPA (fresher)",
        "Company",
    )


def _sector_hq(sector):
    s = (sector or "").lower()
    if any(k in s for k in ("government", "defence", "space", "public")):
        return "India"
    return "India (major hubs: Bengaluru, Mumbai, Delhi NCR)"


def _enrich(c):
    out = dict(c)
    sector = c.get("sector", "")
    roles, salary, ctype = _sector_profile(sector)
    out["headquarters"] = HQ_OVERRIDES.get(c["id"]) or _sector_hq(sector)
    out["roles"] = c.get("roles") or roles
    out["avg_salary"] = c.get("avg_salary") or salary
    out["ctype"] = c.get("ctype") or ctype
    return out


def list_companies(career=None, q=None, sector=None):
    out = COMPANIES
    if career:
        out = [c for c in out if career in c.get("careers", [])]
    if sector:
        s = sector.lower()
        out = [c for c in out if s in c["sector"].lower()]
    if q:
        ql = q.lower()
        out = [
            c
            for c in out
            if ql in c["name"].lower()
            or ql in c["sector"].lower()
            or ql in c.get("description", "").lower()
        ]
    return out


def get_company(cid):
    for c in COMPANIES:
        if c["id"] == cid:
            return _enrich(c)
    return None


def list_sectors():
    seen = []
    for c in COMPANIES:
        if c["sector"] not in seen:
            seen.append(c["sector"])
    return seen
