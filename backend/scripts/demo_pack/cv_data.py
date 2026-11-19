"""Data for the 30-candidate demo pack.

Each profile is a **fictional** person written the way a real CV is written: full
name, headline, a summary, experience at named companies with concrete numbers,
education, certifications and skills.

Language policy: this pack is **English**, because the platform targets an
international audience and English is the expected language for JDs and CVs.
Vietnamese support exists and is exercised by separate tests, but it is an
option, not the default — so the demo data must not teach the opposite.

Constraint that must not break: the **skill profile of each candidate stays the
same** as the original spreadsheet plan, because the demo script depends on who
has enough (or too little) evidence for which position. Do not "improve" a
candidate's skills without updating `KICH_BAN_DEMO.md` first.

Filenames are deliberately inconsistent (`-final`, `_v2`, ` (1)`, mixed case)
because that is what HR actually receives, and it is the condition that proves
the system reads the candidate name from the CV rather than from the filename.

Contact details always use `example.test` / `example.invalid`. There are no
photos, dates of birth, genders, marital status, nationalities, religions,
national ID numbers or home addresses: those are also exactly what the system is
not allowed to process.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Experience:
    role: str
    company: str
    period: str
    location: str
    #: Achievement bullets with numbers. Written the way people write CVs.
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Education:
    degree: str
    school: str
    period: str
    detail: str = ""


@dataclass(frozen=True)
class Candidate:
    number: int
    full_name: str
    headline: str
    email: str
    #: Display format; the phone series is deliberately generic.
    phone: str
    summary: str
    skills: tuple[str, ...]
    experience: tuple[Experience, ...]
    education: tuple[Education, ...]
    certifications: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    projects: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    #: Position applied to per the allocation sheet (not printed on the CV).
    applies_to: str = ""
    #: Previous filename, kept only for the demo script's cross-reference.
    legacy_filename: str = ""


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        number=1,
        full_name="Daniel Whitfield",
        headline="Backend Engineer · Python",
        email="daniel.whitfield@example.test",
        phone="+44 7700 900112",
        summary=(
            "Backend engineer with 4 years of experience building Python services for "
            "e-commerce and product catalogue systems. Comfortable with high-traffic "
            "APIs, query design and batch data processing. Prefers writing tests before "
            "touching legacy code."
        ),
        skills=(
            "Python", "FastAPI", "REST API", "PostgreSQL", "SQL", "Git",
            "pytest", "Docker", "Redis", "data cleaning",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Northbridge Commerce Ltd",
                period="03/2022 – 09/2025",
                location="Manchester, UK",
                bullets=(
                    "Built 12 FastAPI endpoints serving the product catalogue at roughly 40,000 requests per day.",
                    "Designed PostgreSQL queries and transactions for inventory updates, cutting median response time from 480 ms to 190 ms.",
                    "Added request validation and OpenAPI documentation, removing 60% of 500 errors caused by malformed input.",
                    "Wrote unit and integration tests for the API layer, raising coverage from 41% to 78%.",
                ),
            ),
            Experience(
                role="Backend Developer",
                company="Anfield Software Services",
                period="07/2021 – 02/2022",
                location="Manchester, UK",
                bullets=(
                    "Developed a data sync service between the sales system and the warehouse, running in 30-minute batches.",
                    "Added retry handling and correlation-id logging, reducing silent batch failures.",
                ),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Leeds",
                period="2017 – 2021",
                detail="Final-year project: an order management system built with Django.",
            ),
        ),
        certifications=("AWS Certified Cloud Practitioner (2023)",),
        languages=("English (native)", "Spanish (reading technical documentation, B2)"),
        projects=(
            (
                "Shared product catalogue service",
                "Split the product catalogue out of three subsystems into a single read "
                "service; normalised 1.2 million records and defined data quality rules.",
            ),
        ),
        applies_to="Backend Python",
        legacy_filename="CV_01_nguyen_van_an.docx",
    ),
    Candidate(
        number=2,
        full_name="Marcus Bell",
        headline="Python Developer",
        email="marcus.bell@example.test",
        phone="+44 7700 900223",
        summary=(
            "Python developer with 3 years of experience, mostly small web services and "
            "internal tools built with Flask. Comfortable with SQL and unit-level testing. "
            "Looking for a team with a clear code review process."
        ),
        skills=(
            "Python", "Flask", "REST API", "SQL", "SQLite", "Git", "unittest",
            "technical writing",
        ),
        experience=(
            Experience(
                role="Python Developer",
                company="Tanlong Data Solutions Ltd",
                period="05/2023 – 10/2025",
                location="Bristol, UK",
                bullets=(
                    "Maintained a Flask service used by 8 small business customers, handling about 5,000 requests per day.",
                    "Added 7 search and CSV export endpoints backed by SQLite.",
                    "Wrote a unittest suite for the processing layer, catching 15 edge-case bugs before release.",
                    "Produced operations documentation and handover notes for the support team.",
                ),
            ),
            Experience(
                role="Development Intern",
                company="Dathan IT Centre",
                period="09/2022 – 04/2023",
                location="Bristol, UK",
                bullets=(
                    "Wrote Python scripts to process timesheet spreadsheets, saving about 6 hours per month.",
                ),
            ),
        ),
        education=(
            Education(
                degree="BSc Information Technology",
                school="University of the West of England",
                period="2018 – 2022",
            ),
        ),
        languages=("English (native)", "French (A2)"),
        applies_to="Backend Python",
        legacy_filename="CV_02_tran_dinh_binh.pdf",
    ),
    Candidate(
        number=3,
        full_name="Priya Raghavan",
        headline="Backend Developer · Python & FastAPI",
        email="priya.raghavan@example.test",
        phone="+44 7700 900334",
        summary=(
            "Backend engineer with 5 years of experience focused on Python APIs in "
            "financial services. Experienced in coordinating deployments with the "
            "infrastructure team and providing second-line technical support."
        ),
        skills=(
            "Python", "FastAPI", "REST API", "PostgreSQL", "SQL", "Git", "pytest",
            "Docker", "API documentation",
        ),
        experience=(
            Experience(
                role="Backend Developer",
                company="Minh Khang Financial Technology",
                period="01/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Built FastAPI endpoints for the loan application and verification flow, serving 25,000 users.",
                    "Designed PostgreSQL queries for the daily reconciliation report, reducing runtime from 11 minutes to 3.",
                    "Worked with the infrastructure team to containerise the service with Docker and configure load testing.",
                    "Provided second-line support, handling around 20 incidents a month and rewriting the recovery runbooks.",
                ),
            ),
            Experience(
                role="Junior Backend Developer",
                company="Sao Viet Software Ltd",
                period="06/2020 – 12/2021",
                location="London, UK",
                bullets=(
                    "Built the email and SMS notification module for the order management system.",
                ),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Southampton",
                period="2016 – 2020",
                detail="GPA 3.2/4.0.",
            ),
        ),
        certifications=("Microsoft Certified: Azure Fundamentals (2022)",),
        languages=("English (fluent)", "Tamil (native)", "Hindi (B1)"),
        applies_to="Backend Python (Gmail)",
        legacy_filename="CV-03-le_thi_kim_chi-final.docx",
    ),
    Candidate(
        number=4,
        full_name="Thomas Reilly",
        headline="Backend Engineer",
        email="thomas.reilly@example.test",
        phone="+44 7700 900445",
        summary=(
            "Backend engineer with 4 years of experience in Python and PostgreSQL, mostly "
            "on order management systems. Focused on normalising input data and writing "
            "integration tests."
        ),
        skills=(
            "Python", "FastAPI", "PostgreSQL", "SQL", "pytest", "Git",
            "data normalisation", "integration testing",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Hathaway Retail Group",
                period="04/2022 – 10/2025",
                location="Leeds, UK",
                bullets=(
                    "Built the order management API in FastAPI, handling 6,000 orders per day at peak.",
                    "Normalised input data from three sales channels, removing 4,000 duplicate records in the first quarter.",
                    "Wrote integration tests for the payment and refund flow, catching 9 regressions.",
                    "Took part in on-call rotation and resolved incidents involving the order processing queue.",
                ),
            ),
            Experience(
                role="Backend Developer",
                company="Vinh Phat Technology Ltd",
                period="08/2021 – 03/2022",
                location="Leeds, UK",
                bullets=(
                    "Maintained the stock lookup service written in Python and PostgreSQL.",
                ),
            ),
        ),
        education=(
            Education(
                degree="MEng Software Engineering",
                school="University of Sheffield",
                period="2017 – 2021",
            ),
        ),
        languages=("English (native)", "Irish (B1)"),
        projects=(
            (
                "Multi-channel catalogue sync",
                "Consolidated the product catalogue from the website, mobile app and marketplace "
                "into one source of truth; wrote the nightly reconciliation job in Python.",
            ),
        ),
        applies_to="Backend Python",
        legacy_filename="CV_04_pham_tien_dung_v2.docx",
    ),
    Candidate(
        number=5,
        full_name="Sofia Almeida",
        headline="Backend Engineer · Python & QA",
        email="sofia.almeida@example.test",
        phone="+44 7700 900556",
        summary=(
            "Backend engineer with 4 years of experience in Django, with a particular "
            "strength in testing: has worked closely with QA to standardise test cases and "
            "automate API testing."
        ),
        skills=(
            "Python", "Django", "REST", "PostgreSQL", "pytest", "Docker",
            "test case design", "API test automation",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Nam Viet Online Education",
                period="02/2022 – 10/2025",
                location="Birmingham, UK",
                bullets=(
                    "Maintained a Django service used by 18,000 learners, fixing 30 API defects in the first year.",
                    "Worked with QA to standardise 120 test cases and automated 45 API checks with pytest.",
                    "Containerised the service with Docker for test environments, reducing configuration drift between machines.",
                    "Reviewed slow queries and added indexes, improving course list page load time by 35%.",
                ),
            ),
            Experience(
                role="Developer",
                company="Dong A Software Ltd",
                period="07/2021 – 01/2022",
                location="Birmingham, UK",
                bullets=("Built the user management module for the internal system.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Birmingham",
                period="2017 – 2021",
            ),
        ),
        certifications=("ISTQB Certified Tester Foundation Level (2022)",),
        languages=("English (fluent)", "Portuguese (native)"),
        applies_to="Backend Python",
        legacy_filename="vu_thi_hanh_CV_2024.pdf",
    ),
    Candidate(
        number=6,
        full_name="Andrei Popescu",
        headline="Backend Engineer · Java",
        email="andrei.popescu@example.test",
        phone="+44 7700 900667",
        summary=(
            "Backend engineer with 5 years of experience building Java systems for banking "
            "and insurance. Has a solid grounding in APIs and relational databases, and is "
            "looking to move towards Python."
        ),
        skills=(
            "Java", "Spring Boot", "MySQL", "REST", "JUnit", "Git", "Maven",
            "relational database design",
        ),
        experience=(
            Experience(
                role="Backend Engineer",
                company="Tin Viet Banking Technology",
                period="03/2021 – 10/2025",
                location="Edinburgh, UK",
                bullets=(
                    "Developed Java APIs for the credit product catalogue, serving 3 internal systems.",
                    "Wrote JUnit tests for the business layer, raising module coverage from 30% to 65%.",
                    "Reviewed MySQL queries and optimised 14 slow statements, reducing database load at peak.",
                    "Contributed to the case processing design and wrote the technical handover documentation.",
                ),
            ),
            Experience(
                role="Java Developer",
                company="An Gia Insurance Software Ltd",
                period="06/2019 – 02/2021",
                location="Edinburgh, UK",
                bullets=("Built the premium calculation and policy export modules.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Edinburgh",
                period="2015 – 2019",
            ),
        ),
        certifications=("Oracle Certified Associate, Java SE 8 (2020)",),
        languages=("English (fluent)", "Romanian (native)"),
        applies_to="Backend Python",
        legacy_filename="CV 06 andrei_popescu (1).docx",
    ),
    Candidate(
        number=7,
        full_name="Hannah Fischer",
        headline="Data Engineer · Python",
        email="hannah.fischer@example.test",
        phone="+44 7700 900778",
        summary=(
            "Data engineer with 4 years of experience building data processing pipelines in "
            "Python and SQL. Mostly works with sales and marketing data, and cares more about "
            "data quality than about the number of reports."
        ),
        skills=(
            "Python", "SQL", "PostgreSQL", "pandas", "REST", "pytest",
            "data cleaning", "pipeline design",
        ),
        experience=(
            Experience(
                role="Data Engineer",
                company="VinaShop E-commerce",
                period="05/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Built data cleaning jobs in Python and pandas for 2.4 million transaction records.",
                    "Checked missing values and handled ingestion errors per batch, cutting bad rows in the end-of-day report by 70%.",
                    "Wrote SQL queries to aggregate sales data for the analytics team.",
                    "Containerised the pipeline with Docker and added pytest checks for each processing step.",
                ),
            ),
            Experience(
                role="Data Analyst",
                company="Saigon Market Research Ltd",
                period="03/2021 – 04/2022",
                location="London, UK",
                bullets=("Compiled survey data in SQL and Excel for around 40 projects.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Data Science",
                school="University of Manchester",
                period="2017 – 2021",
            ),
        ),
        languages=("English (fluent)", "German (native)"),
        projects=(
            (
                "Unified sales warehouse",
                "Merged data from three sales channels into one common model and wrote the daily reconciliation job.",
            ),
        ),
        applies_to="Data Integration",
        legacy_filename="CV_07_hoang_thi_linh.docx",
    ),
    Candidate(
        number=8,
        full_name="Owen Hartley",
        headline="Data Integration Specialist",
        email="owen.hartley@example.test",
        phone="+44 7700 900889",
        summary=(
            "Data integration specialist with 5 years of experience using SQL and Python to "
            "reconcile data between systems. Used to environments with many data sources where "
            "the numbers have to agree."
        ),
        skills=(
            "SQL", "Python", "pandas", "PostgreSQL", "Git", "Excel",
            "data reconciliation", "data quality checks",
        ),
        experience=(
            Experience(
                role="Data Integration Specialist",
                company="Phuong Dong Consumer Finance",
                period="02/2021 – 10/2025",
                location="Bristol, UK",
                bullets=(
                    "Wrote SQL queries and Python scripts to reconcile data between the core system and the reporting system, running daily.",
                    "Ran data quality checks against a set of 25 rules, finding an average of 300 bad rows per month.",
                    "Worked with finance to resolve period-end discrepancies, reducing reconciliation time from 3 days to 1.",
                    "Documented the data flows for 6 source systems.",
                ),
            ),
            Experience(
                role="Data Specialist",
                company="Hoang Long Digital Services Ltd",
                period="08/2019 – 01/2021",
                location="Bristol, UK",
                bullets=("Compiled and cleaned customer data in SQL and Excel.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Management Information Systems",
                school="University of Bath",
                period="2015 – 2019",
            ),
        ),
        languages=("English (native)",),
        applies_to="Data Integration",
        legacy_filename="CV_08_ngo_quang_minh.pdf",
    ),
    Candidate(
        number=9,
        full_name="Ingrid Solberg",
        headline="Pipeline Engineer",
        email="ingrid.solberg@example.test",
        phone="+44 7700 900990",
        summary=(
            "Pipeline engineer with 4 years of experience operating data flows in Airflow "
            "and Python. Spends a lot of time on failed task monitoring, writing recovery "
            "procedures and early alerting."
        ),
        skills=(
            "Python", "SQL", "Airflow", "PostgreSQL", "Docker", "pytest",
            "task monitoring", "recovery documentation",
        ),
        experience=(
            Experience(
                role="Pipeline Engineer",
                company="Southern Data Systems",
                period="06/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Adjusted 60 Airflow pipelines running in batches, reducing manual re-runs by 45%.",
                    "Monitored failed tasks and wrote recovery documentation for the 12 most important pipelines.",
                    "Added pytest checks for each DAG before deployment, catching 18 configuration faults.",
                    "Containerised the runtime with Docker to keep test and production environments consistent.",
                ),
            ),
            Experience(
                role="Data Operations Engineer",
                company="Tan Binh Digital Technology Ltd",
                period="09/2021 – 05/2022",
                location="London, UK",
                bullets=("Monitored daily data flows and handled slow-task incidents.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Glasgow",
                period="2017 – 2021",
            ),
        ),
        certifications=("Astronomer Certification for Apache Airflow Fundamentals (2023)",),
        languages=("English (fluent)", "Norwegian (native)"),
        applies_to="Data Integration",
        legacy_filename="CV-09-ingrid_solberg-final.docx",
    ),
    Candidate(
        number=10,
        full_name="Rafael Duarte",
        headline="API Integration Engineer",
        email="rafael.duarte@example.test",
        phone="+44 7700 901001",
        summary=(
            "Integration engineer with 4 years of experience connecting systems over REST "
            "APIs in Python. Used to designing endpoints, handling retries and rate limiting "
            "with external partners."
        ),
        skills=(
            "Python", "FastAPI", "SQL", "REST", "Git", "unittest",
            "systems integration", "endpoint design",
        ),
        experience=(
            Experience(
                role="API Integration Engineer",
                company="Thien Phu Retail Technology",
                period="04/2022 – 10/2025",
                location="Leeds, UK",
                bullets=(
                    "Integrated the sales application with the catalogue system, syncing 90,000 records per day.",
                    "Added retry limits and backoff for partner calls, cutting failed syncs by 80%.",
                    "Designed 15 internal FastAPI endpoints with OpenAPI documentation.",
                    "Wrote unittest coverage for the data mapping layer between the two systems.",
                ),
            ),
            Experience(
                role="Backend Developer",
                company="Cau Vong Software Ltd",
                period="07/2021 – 03/2022",
                location="Leeds, UK",
                bullets=("Built the CSV import module for the management system.",),
            ),
        ),
        education=(
            Education(
                degree="BEng Software Engineering",
                school="Queen Mary University of London",
                period="2017 – 2021",
            ),
        ),
        languages=("English (fluent)", "Portuguese (native)"),
        applies_to="Data Integration",
        legacy_filename="CV_10_bui_hong_phuc_v2.docx",
    ),
    Candidate(
        number=11,
        full_name="Claire Bennett",
        headline="Data Analyst",
        email="claire.bennett@example.test",
        phone="+44 7700 901112",
        summary=(
            "Data analyst with 6 years of experience in SQL and Power BI, producing "
            "operational reports for retail. Strong on understanding the business and "
            "presenting numbers; no API development experience."
        ),
        skills=(
            "SQL", "Excel", "Power BI", "tabular data", "business documentation",
            "report analysis", "data visualisation",
        ),
        experience=(
            Experience(
                role="Data Analyst",
                company="Central Retail Group",
                period="01/2019 – 10/2025",
                location="Nottingham, UK",
                bullets=(
                    "Produced revenue and stock reports for 32 stores using SQL and Power BI.",
                    "Standardised the product category list, reducing duplicate groups from 210 to 145.",
                    "Worked with operations to clarify reporting requirements for 8 recurring reports.",
                    "Wrote business documentation for the internal reporting system.",
                ),
            ),
            Experience(
                role="Analyst",
                company="Hoa Binh Trading Ltd",
                period="06/2017 – 12/2018",
                location="Nottingham, UK",
                bullets=("Produced monthly sales reports in Excel and basic SQL.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Economics and Statistics",
                school="University of Nottingham",
                period="2013 – 2017",
            ),
        ),
        certifications=("Microsoft Power BI Data Analyst Associate (2022)",),
        languages=("English (native)",),
        applies_to="Data Integration",
        legacy_filename="dang_kim_quyen_CV_2024.pdf",
    ),
    Candidate(
        number=12,
        full_name="Victor Nunes",
        headline="Data Synchronisation Specialist",
        email="victor.nunes@example.test",
        phone="+44 7700 901223",
        summary=(
            "Data synchronisation specialist with 5 years of experience writing Python and "
            "SQL scripts to keep systems consistent. Used to handling API timeouts and late "
            "arriving data."
        ),
        skills=(
            "Python", "SQL", "MySQL", "REST", "Git", "sync scripting",
            "integration error handling",
        ),
        experience=(
            Experience(
                role="Data Synchronisation Specialist",
                company="Hai Dang Logistics",
                period="03/2020 – 10/2025",
                location="Liverpool, UK",
                bullets=(
                    "Wrote Python scripts to sync shipment data between dispatch and warehouse, 40,000 records per day.",
                    "Tested API timeout scenarios and added a catch-up mechanism, reducing orders missing a status by 65%.",
                    "Wrote MySQL queries to detect discrepancies between the two systems.",
                    "Handed over incident procedures to the night-shift operations team.",
                ),
            ),
            Experience(
                role="Technical Support Officer",
                company="Dinh Vu Port Ltd",
                period="07/2018 – 02/2020",
                location="Liverpool, UK",
                bullets=("Supported data entry and checked shipment records.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Information Technology",
                school="Liverpool John Moores University",
                period="2014 – 2018",
            ),
        ),
        languages=("English (fluent)", "Portuguese (native)"),
        applies_to="Data Integration",
        legacy_filename="CV 12 victor_nunes (1).docx",
    ),
    Candidate(
        number=13,
        full_name="Emily Zhang",
        headline="Frontend Developer · React",
        email="emily.zhang@example.test",
        phone="+44 7700 901334",
        summary=(
            "Frontend developer with 4 years of experience in React and TypeScript, building "
            "internal products for operations teams. Used to writing component tests and "
            "working closely with QA."
        ),
        skills=(
            "TypeScript", "React", "HTML", "CSS", "REST", "React Testing Library",
            "loading state handling", "API error handling",
        ),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Tin Thanh Operations Technology",
                period="05/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Built 24 React forms for the internal order management system, sharing one component library.",
                    "Handled loading states and API errors, halving user reports of blank screens.",
                    "Wrote component tests with React Testing Library for the key data entry flows.",
                    "Agreed UI acceptance criteria with QA before each release.",
                ),
            ),
            Experience(
                role="Frontend Developer",
                company="Sao Mai Software Ltd",
                period="08/2021 – 04/2022",
                location="London, UK",
                bullets=("Built admin pages in React and Ant Design.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University College London",
                period="2017 – 2021",
            ),
        ),
        languages=("English (fluent)", "Mandarin (native)"),
        applies_to="Frontend React",
        legacy_filename="CV_13_nguyen_phuong_thao.docx",
    ),
    Candidate(
        number=14,
        full_name="Jack Morrow",
        headline="Frontend Engineer · React & Next.js",
        email="jack.morrow@example.test",
        phone="+44 7700 901445",
        summary=(
            "Frontend engineer with 5 years of experience in React, Next.js and TypeScript. "
            "Experienced in writing end-to-end user journey tests with Playwright and "
            "optimising page load performance."
        ),
        skills=(
            "React", "TypeScript", "Next.js", "CSS", "Playwright", "Git",
            "performance optimisation", "user journey testing",
        ),
        experience=(
            Experience(
                role="Frontend Engineer",
                company="Nam Long Digital Commerce",
                period="02/2021 – 10/2025",
                location="London, UK",
                bullets=(
                    "Developed 40 reusable components for a Next.js application serving 120,000 monthly users.",
                    "Integrated REST APIs and implemented pagination and server-side search.",
                    "Wrote user journey tests in Playwright for 18 critical flows.",
                    "Optimised initial page load, reducing Largest Contentful Paint from 4.2 s to 2.1 s.",
                ),
            ),
            Experience(
                role="Frontend Developer",
                company="Saigon Young Technology Ltd",
                period="07/2019 – 01/2021",
                location="London, UK",
                bullets=("Built landing pages and product pages in React.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Software Engineering",
                school="University of Bristol",
                period="2015 – 2019",
            ),
        ),
        certifications=("Meta Front-End Developer Professional Certificate (2022)",),
        languages=("English (native)",),
        projects=(
            (
                "Operations dashboard",
                "Redesigned the operations dashboard in Next.js with real-time charts.",
            ),
        ),
        applies_to="Frontend React",
        legacy_filename="CV_14_tran_anh_tuan.pdf",
    ),
    Candidate(
        number=15,
        full_name="Nadia Karim",
        headline="Frontend Developer · Accessible UI",
        email="nadia.karim@example.test",
        phone="+44 7700 901556",
        summary=(
            "Frontend developer with 4 years of experience focused on accessibility and "
            "interface quality. Works closely with design, checking form labels and keyboard "
            "navigation as part of the definition of done."
        ),
        skills=(
            "JavaScript", "React", "HTML", "CSS", "accessibility", "Figma",
            "interface testing", "design review",
        ),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Tri Thuc Education Technology",
                period="03/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Implemented 30 screens from Figma designs for an online learning platform.",
                    "Audited form labels and keyboard navigation across 18 screens, fixing 60 accessibility defects.",
                    "Standardised the shared UI component library across 4 product teams.",
                    "Worked with QA to build an interface checklist for pre-release checks.",
                ),
            ),
            Experience(
                role="Web Developer",
                company="Hanoi Digital Design Ltd",
                period="08/2021 – 02/2022",
                location="London, UK",
                bullets=("Sliced designs into HTML/CSS and implemented basic JavaScript interactions.",),
            ),
        ),
        education=(
            Education(
                degree="BA Multimedia Design",
                school="University of the Arts London",
                period="2017 – 2021",
            ),
        ),
        languages=("English (fluent)", "Arabic (native)"),
        applies_to="Frontend React",
        legacy_filename="CV-15-nadia_karim-final.docx",
    ),
    Candidate(
        number=16,
        full_name="Liam Foster",
        headline="Frontend Developer · API Integration",
        email="liam.foster@example.test",
        phone="+44 7700 901667",
        summary=(
            "Frontend developer with 3 years of experience in React and TypeScript, building "
            "scheduling screens and handling network errors. Understands APIs, though backend "
            "experience is limited."
        ),
        skills=(
            "TypeScript", "React", "REST", "Node.js", "Git", "Jest",
            "network error handling", "API integration",
        ),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Gio Vang Online Booking",
                period="06/2022 – 10/2025",
                location="Oxford, UK",
                bullets=(
                    "Built the appointment scheduling screens for 5,000 users in React and TypeScript.",
                    "Handled network errors and retry states, reducing abandoned bookings by 40%.",
                    "Added Jest coverage for the UI logic, reaching 55% function coverage.",
                    "Contributed to API contract design with the backend team before implementation.",
                ),
            ),
            Experience(
                role="Frontend Intern",
                company="Central Technology Ltd",
                period="01/2022 – 05/2022",
                location="Oxford, UK",
                bullets=("Fixed layout defects and helped test across screen sizes.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="Oxford Brookes University",
                period="2017 – 2021",
            ),
        ),
        languages=("English (native)",),
        applies_to="Frontend React",
        legacy_filename="CV_16_phan_hai_yen_v2.docx",
    ),
    Candidate(
        number=17,
        full_name="Grace Okonkwo",
        headline="Web Developer",
        email="grace.okonkwo@example.test",
        phone="+44 7700 901778",
        summary=(
            "Web developer with 3 years of experience building marketing sites and simple "
            "admin pages in HTML, CSS and JavaScript. Currently learning React; no production "
            "React project experience yet."
        ),
        skills=(
            "HTML", "CSS", "JavaScript", "Git", "Bootstrap", "jQuery",
            "marketing site builds", "layout defect fixing",
        ),
        experience=(
            Experience(
                role="Web Developer",
                company="Sang Tao Creative Communications",
                period="09/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Delivered 35 corporate marketing sites using HTML, CSS and Bootstrap.",
                    "Fixed display defects across older browsers and mobile devices.",
                    "Supported manual testing before client handover.",
                ),
            ),
            Experience(
                role="Intern",
                company="Ha Thanh Web Design Ltd",
                period="03/2022 – 08/2022",
                location="London, UK",
                bullets=("Sliced designs from files and entered content.",),
            ),
        ),
        education=(
            Education(
                degree="Higher National Diploma in Computing",
                school="City of London College",
                period="2018 – 2021",
            ),
        ),
        languages=("English (native)", "Igbo (fluent)"),
        applies_to="Frontend React",
        legacy_filename="grace_okonkwo_CV_2024.pdf",
    ),
    Candidate(
        number=18,
        full_name="Peter Novak",
        headline="Frontend Developer · React (Junior)",
        email="peter.novak@example.test",
        phone="+44 7700 901889",
        summary=(
            "Frontend developer with 2 years of experience in React and JavaScript, building "
            "management screens for internal systems. Used to connecting APIs and checking "
            "input data."
        ),
        skills=("React", "JavaScript", "CSS", "REST", "Git", "API integration", "input validation"),
        experience=(
            Experience(
                role="Frontend Developer",
                company="Tin Minh Asset Management Software",
                period="11/2023 – 10/2025",
                location="London, UK",
                bullets=(
                    "Contributed to 16 React screens for the internal asset management system.",
                    "Connected APIs and handled authentication errors with clear user messages.",
                    "Checked form input data and added format validation.",
                ),
            ),
            Experience(
                role="Frontend Intern",
                company="Tri Tue Digital Technology Ltd",
                period="04/2023 – 10/2023",
                location="London, UK",
                bullets=("Learned React and fixed minor UI defects.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Information Systems",
                school="Middlesex University",
                period="2019 – 2023",
            ),
        ),
        languages=("English (fluent)", "Slovak (native)"),
        applies_to="Frontend React",
        legacy_filename="CV 18 peter_novak (1).docx",
    ),
    Candidate(
        number=19,
        full_name="Ayesha Siddiqui",
        headline="QA Automation Engineer",
        email="ayesha.siddiqui@example.test",
        phone="+44 7700 901990",
        summary=(
            "QA automation engineer with 5 years of experience, mostly testing APIs and "
            "backend services in Python and pytest. Used to reading logs and working with "
            "developers to reproduce defects."
        ),
        skills=(
            "Python", "pytest", "REST", "SQL", "Playwright", "Git",
            "test case design", "API testing",
        ),
        experience=(
            Experience(
                role="QA Automation Engineer",
                company="Binh Minh E-commerce Group",
                period="04/2021 – 10/2025",
                location="London, UK",
                bullets=(
                    "Designed 260 test cases and automated API testing for the ordering system.",
                    "Wrote pytest suites covering response codes, response schema and processing time.",
                    "Brought automated tests into CI, cutting regression testing from 2 days to 3 hours.",
                    "Monitored production defects and worked with developers to reproduce 45 incidents.",
                ),
            ),
            Experience(
                role="QA Engineer",
                company="Tin Dung Vietnam Software Ltd",
                period="07/2019 – 03/2021",
                location="London, UK",
                bullets=("Tested credit system functions and logged defects.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Westminster",
                period="2015 – 2019",
            ),
        ),
        certifications=("ISTQB Certified Tester Advanced Level, Test Automation Engineer (2023)",),
        languages=("English (fluent)", "Urdu (native)"),
        applies_to="QA Automation",
        legacy_filename="CV_19_nguyen_tien_duy.docx",
    ),
    Candidate(
        number=20,
        full_name="Grace Whitmore",
        headline="QA Engineer · API & Data",
        email="grace.whitmore@example.test",
        phone="+44 7700 902001",
        summary=(
            "QA engineer with 4 years of experience testing APIs and reconciling data. Writes "
            "Python scripts to automate data checks, and describes defects so developers can "
            "reproduce them immediately."
        ),
        skills=(
            "Python", "pytest", "SQL", "Postman", "REST", "Git",
            "data reconciliation", "defect reporting",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Sao Do Financial Technology",
                period="03/2022 – 10/2025",
                location="Cardiff, UK",
                bullets=(
                    "Tested APIs and reconciled data between the transaction system and the ledger, running daily.",
                    "Wrote pytest and SQL scripts to automatically check balances after each transaction batch.",
                    "Reported 120 defects with reproduction steps and logs, reducing mean time to fix from 3 days to 1.5.",
                    "Built Postman collections covering 40 endpoints.",
                ),
            ),
            Experience(
                role="QA Engineer",
                company="Nhanh Payment Technology Ltd",
                period="08/2021 – 02/2022",
                location="Cardiff, UK",
                bullets=("Tested payment functions and checked input data.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Business Information Systems",
                school="Cardiff University",
                period="2016 – 2020",
            ),
        ),
        languages=("English (native)",),
        applies_to="QA Automation",
        legacy_filename="CV_20_truong_thanh_giang.pdf",
    ),
    Candidate(
        number=21,
        full_name="Omar Haddad",
        headline="QA Automation Engineer · UI",
        email="omar.haddad@example.test",
        phone="+44 7700 902112",
        summary=(
            "QA automation engineer with 4 years of experience focused on web interfaces with "
            "Playwright and TypeScript. Used to regression testing across screen sizes and "
            "working closely with frontend teams."
        ),
        skills=(
            "TypeScript", "Playwright", "React", "HTML", "test case design", "Git",
            "regression testing", "interface testing",
        ),
        experience=(
            Experience(
                role="QA Automation Engineer",
                company="Hanoi Digital Retail",
                period="05/2022 – 10/2025",
                location="London, UK",
                bullets=(
                    "Built a UI regression suite in Playwright covering 20 key screens.",
                    "Verified user journeys across 5 screen sizes and 3 browsers.",
                    "Reduced UI defects reaching production from 12 to 3 per quarter.",
                    "Wrote test cases for checkout and returns flows.",
                ),
            ),
            Experience(
                role="Manual QA",
                company="Tan Viet Retail Technology Ltd",
                period="09/2021 – 04/2022",
                location="London, UK",
                bullets=("Manually tested cart functions and wrote defect reports.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="City, University of London",
                period="2017 – 2021",
            ),
        ),
        languages=("English (fluent)", "Arabic (native)"),
        applies_to="QA Automation",
        legacy_filename="CV-21-omar_haddad-final.docx",
    ),
    Candidate(
        number=22,
        full_name="Sven Lindqvist",
        headline="QA Engineer · Automation & CI",
        email="sven.lindqvist@example.test",
        phone="+44 7700 902223",
        summary=(
            "QA engineer with 5 years of experience, strong on bringing automated tests into "
            "the CI pipeline. Used to packaging test suites with Docker and analysing results "
            "on Linux."
        ),
        skills=(
            "Python", "pytest", "Docker", "CI", "REST", "Linux",
            "pipeline configuration", "test result analysis",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Dong Duong Supply Chain Technology",
                period="02/2021 – 10/2025",
                location="Cambridge, UK",
                bullets=(
                    "Built a pytest API regression suite covering 70 endpoints, running on the pipeline at every merge.",
                    "Configured automated test runs in CI, reducing defect detection time from 1 week to under 1 day.",
                    "Packaged the test suite in Docker so it runs identically on developer machines and servers.",
                    "Produced result reports and analysed flaky test cases.",
                ),
            ),
            Experience(
                role="Test Engineer",
                company="Thang Long Transport Software Ltd",
                period="07/2019 – 01/2021",
                location="Cambridge, UK",
                bullets=("Tested functions and wrote Python data check scripts.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of Cambridge",
                period="2015 – 2019",
            ),
        ),
        languages=("English (fluent)", "Swedish (native)"),
        applies_to="QA Automation",
        legacy_filename="CV_22_bui_anh_kiet_v2.docx",
    ),
    Candidate(
        number=23,
        full_name="Laura Simmons",
        headline="QA Engineer · Manual Testing",
        email="laura.simmons@example.test",
        phone="+44 7700 902334",
        summary=(
            "QA engineer with 4 years of experience testing web functions against written test "
            "cases. Good at defect reporting and working with developers; currently learning "
            "test automation."
        ),
        skills=(
            "test case design", "web testing", "defect tracking", "basic SQL",
            "functional testing", "defect reporting",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Hanoi Business Solutions",
                period="06/2021 – 10/2025",
                location="London, UK",
                bullets=(
                    "Tested the HR management website for 14 business customers.",
                    "Logged defects and worked with developers to reproduce them, closing 380 defects over 4 years.",
                    "Wrote test cases for payroll, leave and timesheet flows.",
                    "Used basic SQL to check data after each action.",
                ),
            ),
            Experience(
                role="Test Analyst",
                company="An Viet Accounting Software Ltd",
                period="09/2020 – 05/2021",
                location="London, UK",
                bullets=("Manually tested accounting software and recorded test results.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Information Technology",
                school="University of Hertfordshire",
                period="2016 – 2020",
            ),
        ),
        languages=("English (native)",),
        applies_to="QA Automation",
        legacy_filename="nguyen_thi_lam_CV_2024.pdf",
    ),
    Candidate(
        number=24,
        full_name="Kevin Duong",
        headline="QA Engineer (Junior)",
        email="kevin.duong@example.test",
        phone="+44 7700 902445",
        summary=(
            "QA engineer with 2 years of experience testing APIs with Postman and running "
            "manual regression checks. Has a basic SQL and JavaScript background and is "
            "looking for an automation role."
        ),
        skills=(
            "Postman", "REST", "SQL", "basic JavaScript", "regression testing",
            "test result recording", "API testing",
        ),
        experience=(
            Experience(
                role="QA Engineer",
                company="Van Long Digital Services",
                period="12/2023 – 10/2025",
                location="London, UK",
                bullets=(
                    "Ran Postman API tests across 30 endpoints and recorded regression results.",
                    "Used SQL to check data after each order status update.",
                    "Produced weekly defect reports for the development team.",
                ),
            ),
            Experience(
                role="QA Intern",
                company="Dong Nam A Technology Ltd",
                period="05/2023 – 11/2023",
                location="London, UK",
                bullets=("Manually tested the mobile application and recorded results.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Information Systems",
                school="University of Greenwich",
                period="2019 – 2023",
            ),
        ),
        languages=("English (native)", "Vietnamese (fluent)"),
        applies_to="QA Automation",
        legacy_filename="CV 24 kevin_duong (1).docx",
    ),
    Candidate(
        number=25,
        full_name="Mei Ling Tan",
        headline="DevOps Engineer · Python",
        email="mei.tan@example.test",
        phone="+44 7700 902556",
        summary=(
            "DevOps engineer with 5 years of experience running Python services on Linux. "
            "Used to building CI/CD pipelines, reading logs and working with developers on "
            "deployment faults."
        ),
        skills=(
            "Linux", "Docker", "CI/CD", "Python", "Git", "PostgreSQL",
            "log analysis", "deployment troubleshooting",
        ),
        experience=(
            Experience(
                role="DevOps Engineer",
                company="VinaCloud Infrastructure",
                period="03/2021 – 10/2025",
                location="London, UK",
                bullets=(
                    "Maintained build and deployment pipelines for 9 Python services, running about 40 times a week.",
                    "Analysed logs and worked with developers to resolve 60 deployment faults in the first year.",
                    "Standardised Dockerfiles across services, reducing average image size by 35%.",
                    "Wrote runbooks for common incidents and trained the on-call rotation.",
                ),
            ),
            Experience(
                role="System Engineer",
                company="Sao Bac Server Services Ltd",
                period="08/2019 – 02/2021",
                location="London, UK",
                bullets=("Administered Linux servers and supported internal application deployments.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Networks and Communications",
                school="University of Surrey",
                period="2015 – 2019",
            ),
        ),
        certifications=("Docker Certified Associate (2022)",),
        languages=("English (fluent)", "Mandarin (native)"),
        applies_to="DevOps & Cloud",
        legacy_filename="CV_25_nguyen_thi_oanh.docx",
    ),
    Candidate(
        number=26,
        full_name="Diego Alvarez",
        headline="Cloud Engineer · Infrastructure as Code",
        email="diego.alvarez@example.test",
        phone="+44 7700 902667",
        summary=(
            "Cloud engineer with 5 years of experience in AWS and Terraform. Builds "
            "infrastructure for containerised services, monitors workloads and automates "
            "deployments."
        ),
        skills=(
            "Linux", "Docker", "AWS", "Terraform", "CI/CD", "Python",
            "system monitoring", "container deployment",
        ),
        experience=(
            Experience(
                role="Cloud Engineer",
                company="Tan Hung Cloud Solutions",
                period="02/2021 – 10/2025",
                location="London, UK",
                bullets=(
                    "Wrote 40 Terraform modules for the AWS infrastructure of 6 products, cutting environment setup from 2 days to 2 hours.",
                    "Supported container deployment for 14 services and configured load balancing.",
                    "Monitored scheduled workloads, reducing late-detected incidents by 50%.",
                    "Wrote Python scripts for operational tasks and resource cleanup.",
                ),
            ),
            Experience(
                role="Infrastructure Engineer",
                company="May Viet Technology Ltd",
                period="07/2019 – 01/2021",
                location="London, UK",
                bullets=("Administered servers and supported AWS application deployments.",),
            ),
        ),
        education=(
            Education(
                degree="BEng Computer Engineering",
                school="Imperial College London",
                period="2015 – 2019",
            ),
        ),
        certifications=(
            "AWS Certified Solutions Architect – Associate (2022)",
            "HashiCorp Certified: Terraform Associate (2023)",
        ),
        languages=("English (fluent)", "Spanish (native)"),
        applies_to="DevOps & Cloud",
        legacy_filename="CV_26_tran_xuan_phong.pdf",
    ),
    Candidate(
        number=27,
        full_name="Rory McAllister",
        headline="DevOps Engineer · CI & Testing",
        email="rory.mcallister@example.test",
        phone="+44 7700 902778",
        summary=(
            "DevOps engineer with 4 years of experience focused on build pipelines and "
            "automated testing. Writes Python scripts and configures CI for product teams."
        ),
        skills=(
            "Linux", "Docker", "Git", "CI", "Python", "pytest",
            "pipeline configuration", "build failure triage",
        ),
        experience=(
            Experience(
                role="DevOps Engineer",
                company="Tin Phat Enterprise Software",
                period="05/2022 – 10/2025",
                location="Glasgow, UK",
                bullets=(
                    "Set up build and test pipelines for 5 products, running 30 times a week.",
                    "Wrote Python scripts to automate the pre-release checks.",
                    "Triaged build failures with developers, reducing broken builds by 40%.",
                    "Improved pipeline feedback time from 25 minutes to 12 minutes.",
                ),
            ),
            Experience(
                role="System Administrator",
                company="Thang Long Digital Infrastructure Ltd",
                period="09/2021 – 04/2022",
                location="Glasgow, UK",
                bullets=("Administered Linux and supported internal application deployments.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computing",
                school="University of Strathclyde",
                period="2017 – 2021",
            ),
        ),
        languages=("English (native)",),
        applies_to="DevOps & Cloud",
        legacy_filename="CV-27-rory_mcallister-final.docx",
    ),
    Candidate(
        number=28,
        full_name="Aisha Rahman",
        headline="Container Operations Engineer",
        email="aisha.rahman@example.test",
        phone="+44 7700 902889",
        summary=(
            "Container operations engineer with 4 years of experience in Kubernetes and "
            "Docker. Used to monitoring logs, writing incident procedures and joining the "
            "on-call rotation. Most of the current automation is written in Bash."
        ),
        skills=(
            "Linux", "Kubernetes", "Docker", "Bash", "Git", "monitoring",
            "log monitoring", "incident procedures",
        ),
        experience=(
            Experience(
                role="Container Operations Engineer",
                company="Viet Digital Finance Technology",
                period="04/2021 – 10/2025",
                location="London, UK",
                bullets=(
                    "Supported the operation of 3 Kubernetes clusters running 80 internal services.",
                    "Monitored logs and documented procedures for 25 recurring incidents.",
                    "Wrote Bash scripts to check pod health and clean up orphaned resources.",
                    "Configured alerting for key resource metrics.",
                ),
            ),
            Experience(
                role="Operations Engineer",
                company="Nam Saigon Infrastructure Services Ltd",
                period="08/2019 – 03/2021",
                location="London, UK",
                bullets=("Monitored server systems and handled incidents during on-call shifts.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Networks",
                school="Queen Mary University of London",
                period="2015 – 2019",
            ),
        ),
        certifications=("Certified Kubernetes Administrator (2022)",),
        languages=("English (fluent)", "Bengali (native)"),
        applies_to="DevOps & Cloud",
        legacy_filename="CV_28_nguyen_thu_trang_v2.docx",
    ),
    Candidate(
        number=29,
        full_name="Billy Chen",
        headline="IT Support Engineer",
        email="billy.chen@example.test",
        phone="+44 7700 902990",
        summary=(
            "IT support engineer with 4 years of experience handling user tickets and checking "
            "network connectivity. Strong on process and documentation; no Docker or CI "
            "experience."
        ),
        skills=(
            "Windows", "basic Linux", "ticketing", "basic networking", "documentation",
            "user support", "connectivity checks",
        ),
        experience=(
            Experience(
                role="IT Support Engineer",
                company="Huong Viet Food Manufacturing",
                period="07/2021 – 10/2025",
                location="Milton Keynes, UK",
                bullets=(
                    "Tracked and resolved an average of 180 support tickets a month for 400 users.",
                    "Checked network connectivity and liaised with the ISP during outages.",
                    "Updated procedures for 30 recurring issues.",
                    "Managed Windows workstations and installed software on request.",
                ),
            ),
            Experience(
                role="Technical Support Officer",
                company="Kinh Bac IT Services Ltd",
                period="09/2020 – 06/2021",
                location="Milton Keynes, UK",
                bullets=("Supported users by phone and resolved desktop faults.",),
            ),
        ),
        education=(
            Education(
                degree="Higher National Diploma in Computing",
                school="Milton Keynes College",
                period="2017 – 2020",
            ),
        ),
        languages=("English (fluent)", "Mandarin (fluent)"),
        applies_to="DevOps & Cloud",
        legacy_filename="phan_quoc_uy_CV_2024.pdf",
    ),
    Candidate(
        number=30,
        full_name="Nora Lindberg",
        headline="DevOps Engineer (Junior)",
        email="nora.lindberg@example.test",
        phone="+44 7700 903001",
        summary=(
            "DevOps engineer with 2 years of experience in Linux, Docker and basic CI. "
            "Supports application packaging and updates pipelines under team guidance. "
            "Currently learning Kubernetes."
        ),
        skills=(
            "Linux", "Bash", "Git", "Docker", "basic CI",
            "application packaging", "log reading",
        ),
        experience=(
            Experience(
                role="DevOps Engineer",
                company="An Khang Digital Education",
                period="11/2023 – 10/2025",
                location="London, UK",
                bullets=(
                    "Helped package 12 applications with Docker using the team's existing templates.",
                    "Read deployment logs and reported faults to the senior engineer.",
                    "Updated pipeline configuration under guidance, bringing 8 new pipelines into use.",
                    "Wrote Bash scripts to check running processes and disk usage.",
                ),
            ),
            Experience(
                role="IT Intern",
                company="An Khang Technology Ltd",
                period="05/2023 – 10/2023",
                location="London, UK",
                bullets=("Supported internal server operations and environment setup.",),
            ),
        ),
        education=(
            Education(
                degree="BSc Computer Science",
                school="University of East London",
                period="2019 – 2023",
            ),
        ),
        languages=("English (fluent)", "Swedish (native)"),
        applies_to="DevOps & Cloud",
        legacy_filename="CV 30 nora_lindberg (1).docx",
    ),
)


def by_number(number: int) -> Candidate:
    for candidate in CANDIDATES:
        if candidate.number == number:
            return candidate
    raise KeyError(f"No candidate number {number}")
