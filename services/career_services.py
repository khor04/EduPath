import os
import re
import json
import time

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.users import User
from models.course import Course
from models.semester import Semester
from models.transcript import Transcript
from models.course_skill_mapping import CourseSkillMapping
from models.programme_course_relevance import ProgrammeCourseRelevance
from models.skill_profile import SkillProfile
from models.onet_occupation import OnetOccupation
from models.onet_occupation_concept import OnetOccupationConcept
from models.career_recommendation import CareerRecommendation
from services.cgpa_services import GRADE_POINTS, FAIL_GRADES

MODEL_NAME = "gemini-3.6-flash"
CLASSIFY_PROMPT_VERSION = "v1"
RELEVANCE_PROMPT_VERSION = "v2"

# Initial design weights for relevance tiers -- NOT yet empirically
# calibrated against real recommendation quality. Kept as named
# constants specifically so they can be revisited/tuned later without
# hunting for magic numbers.
CAREER_RELEVANCE_WEIGHTS = {
    "Core": 1.0,
    "Related": 0.7,
    "General": 0.3,
}

# O*NET's standard 35 Skills (Content Model, Basic + Cross-Functional
# Skills domain).
ONET_SKILLS = [
    ("Reading Comprehension", "Understanding written sentences and paragraphs in work-related documents."),
    ("Active Listening", "Giving full attention to what other people are saying, taking time to understand the points being made, asking questions as appropriate, and not interrupting at inappropriate times."),
    ("Writing", "Communicating effectively in writing as appropriate for the needs of the audience."),
    ("Speaking", "Talking to others to convey information effectively."),
    ("Mathematics", "Using mathematics to solve problems."),
    ("Science", "Using scientific rules and methods to solve problems."),
    ("Critical Thinking", "Using logic and reasoning to identify the strengths and weaknesses of alternative solutions, conclusions, or approaches to problems."),
    ("Active Learning", "Understanding the implications of new information for both current and future problem-solving and decision-making."),
    ("Learning Strategies", "Selecting and using training/instructional methods and procedures appropriate for the situation when learning or teaching new things."),
    ("Monitoring", "Monitoring/Assessing performance of yourself, other individuals, or organizations to make improvements or take corrective action."),
    ("Social Perceptiveness", "Being aware of others' reactions and understanding why they react as they do."),
    ("Coordination", "Adjusting actions in relation to others' actions."),
    ("Persuasion", "Persuading others to change their minds or behavior."),
    ("Negotiation", "Bringing others together and trying to reconcile differences."),
    ("Instructing", "Teaching others how to do something."),
    ("Service Orientation", "Actively looking for ways to help people."),
    ("Complex Problem Solving", "Identifying complex problems and reviewing related information to develop and evaluate options and implement solutions."),
    ("Operations Analysis", "Analyzing needs and product requirements to create a design."),
    ("Technology Design", "Generating or adapting equipment and technology to serve user needs."),
    ("Equipment Selection", "Determining the kind of tools and equipment needed to do a job."),
    ("Installation", "Installing equipment, machines, wiring, or programs to meet specifications."),
    ("Programming", "Writing computer programs for various purposes."),
    ("Operations Monitoring", "Watching gauges, dials, or other indicators to make sure a machine is working properly."),
    ("Operation and Control", "Controlling operations of equipment or systems."),
    ("Equipment Maintenance", "Performing routine maintenance on equipment and determining when and what kind of maintenance is needed."),
    ("Troubleshooting", "Determining causes of operating errors and deciding what to do about it."),
    ("Repairing", "Repairing machines or systems using the needed tools."),
    ("Quality Control Analysis", "Conducting tests and inspections of products, services, or processes to evaluate quality or performance."),
    ("Judgment and Decision Making", "Considering the relative costs and benefits of potential actions to choose the most appropriate one."),
    ("Systems Analysis", "Determining how a system should work and how changes in conditions, operations, and the environment will affect outcomes."),
    ("Systems Evaluation", "Identifying measures or indicators of system performance and the actions needed to improve or correct performance, relative to the goals of the system."),
    ("Time Management", "Managing one's own time and the time of others."),
    ("Management of Financial Resources", "Determining how money will be spent to get the work done, and accounting for these expenditures."),
    ("Management of Material Resources", "Obtaining and seeing to the appropriate use of equipment, facilities, and materials needed to do certain work."),
    ("Management of Personnel Resources", "Motivating, developing, and directing people as they work, identifying the best people for the job."),
]

# O*NET's standard 33 Knowledge areas (Content Model).
ONET_KNOWLEDGE = [
    ("Administration and Management", "Knowledge of business and management principles involved in strategic planning, resource allocation, human resources modeling, leadership technique, production methods, and coordination of people and resources."),
    ("Administrative", "Knowledge of administrative and clerical procedures and systems such as word processing, managing files and records, stenography and transcription, designing forms, and other office procedures and terminology."),
    ("Economics and Accounting", "Knowledge of economic and accounting principles and practices, the financial markets, banking, and the analysis and reporting of financial data."),
    ("Sales and Marketing", "Knowledge of principles and methods for showing, promoting, and selling products or services. This includes marketing strategy and tactics, product demonstration, sales techniques, and sales control systems."),
    ("Customer and Personal Service", "Knowledge of principles and processes for providing customer and personal services. This includes customer needs assessment, meeting quality standards for services, and evaluation of customer satisfaction."),
    ("Personnel and Human Resources", "Knowledge of principles and procedures for personnel recruitment, selection, training, compensation and benefits, labor relations and negotiation, and personnel information systems."),
    ("Production and Processing", "Knowledge of raw materials, production processes, quality control, costs, and other techniques for maximizing the effective manufacture and distribution of goods."),
    ("Food Production", "Knowledge of techniques and equipment for planting, growing, and harvesting food products (both plant and animal) for consumption, including storage/handling techniques."),
    ("Computers and Electronics", "Knowledge of circuit boards, processors, chips, electronic equipment, and computer hardware and software, including applications and programming."),
    ("Engineering and Technology", "Knowledge of the practical application of engineering science and technology. This includes applying principles, techniques, procedures, and equipment to the design and production of various goods and services."),
    ("Design", "Knowledge of design techniques, tools, and principles involved in production of precision technical plans, blueprints, drawings, and models."),
    ("Building and Construction", "Knowledge of materials, methods, and the tools involved in the construction or repair of houses, buildings, or other structures such as highways and roads."),
    ("Mechanical", "Knowledge of machines and tools, including their designs, uses, repair, and maintenance."),
    ("Mathematics", "Knowledge of arithmetic, algebra, geometry, calculus, statistics, and their applications."),
    ("Physics", "Knowledge and prediction of physical principles, laws, their interrelationships, and applications to understanding fluid, material, and atmospheric dynamics, and mechanical, electrical, atomic and sub-atomic structures and processes."),
    ("Chemistry", "Knowledge of the chemical composition, structure, and properties of substances and of the chemical processes and transformations that they undergo."),
    ("Biology", "Knowledge of plant and animal organisms, their tissues, cells, functions, interdependencies, and interactions with each other and the environment."),
    ("Psychology", "Knowledge of human behavior and performance; individual differences in ability, personality, and interests; learning and motivation; psychological research methods; and the assessment and treatment of behavioral and affective disorders."),
    ("Sociology and Anthropology", "Knowledge of group behavior and dynamics, societal trends and influences, human migrations, ethnicity, cultures, and their history and origins."),
    ("Geography", "Knowledge of principles and methods for describing the features of land, sea, and air masses, including their physical characteristics, locations, interrelationships, and distribution of plant, animal, and human life."),
    ("Medicine and Dentistry", "Knowledge of the information and techniques needed to diagnose and treat human injuries, diseases, and deformities. This includes symptoms, treatment alternatives, drug properties and interactions, and preventive health-care measures."),
    ("Therapy and Counseling", "Knowledge of principles, methods, and procedures for diagnosis, treatment, and rehabilitation of physical and mental dysfunctions, and for career counseling and guidance."),
    ("Education and Training", "Knowledge of principles and methods for curriculum and training design, teaching and instruction for individuals and groups, and the measurement of training effects."),
    ("English Language", "Knowledge of the structure and content of the English language including the meaning and spelling of words, rules of composition, and grammar."),
    ("Foreign Language", "Knowledge of the structure and content of a foreign (non-English) language including the meaning and spelling of words, rules of composition and grammar, and pronunciation."),
    ("Fine Arts", "Knowledge of theory and techniques required to compose, produce, and perform works of music, dance, visual arts, drama, and sculpture."),
    ("History and Archeology", "Knowledge of historical events and their causes, indicators, and effects on civilizations and cultures."),
    ("Philosophy and Theology", "Knowledge of different philosophical systems and religions. This includes their basic principles, values, ethics, ways of thinking, customs, practices, and their impact on human culture."),
    ("Public Safety and Security", "Knowledge of relevant equipment, policies, procedures, and strategies to promote effective local, state, or national security operations for the protection of people, data, property, and institutions."),
    ("Law and Government", "Knowledge of laws, legal codes, court procedures, precedents, government regulations, executive orders, agency rules, and the democratic political process."),
    ("Telecommunications", "Knowledge of transmission, broadcasting, switching, control, and operation of telecommunications systems."),
    ("Communications and Media", "Knowledge of media production, communication, and dissemination techniques and methods. This includes alternative ways to inform and entertain via written, oral, and visual media."),
    ("Transportation", "Knowledge of principles and methods for moving people or goods by air, rail, sea, or road, including the relative costs and benefits."),
]

SKILL_NAMES = {name for name, _ in ONET_SKILLS}
KNOWLEDGE_NAMES = {name for name, _ in ONET_KNOWLEDGE}

# Student-facing competency groups -- a fixed, hand-built mapping of
# the 68 O*NET Skill/Knowledge labels into broader, more legible
# categories (verified to cover every label exactly once -- see
# test_competency_groups.py). This is presentation-only: career
# matching still compares raw O*NET concepts against occupation data,
# never these groups. No Gemini call needed for this layer -- unlike
# course/relevance classification, this mapping doesn't vary per
# student or need semantic judgment, so a static table is both
# simpler and more auditable than generating it per request.
COMPETENCY_GROUPS = {
    "Software & Programming": [
        ("skill", "Programming"),
        ("skill", "Technology Design"),
    ],
    "Analytical & Problem Solving": [
        ("skill", "Critical Thinking"),
        ("skill", "Complex Problem Solving"),
        ("skill", "Operations Analysis"),
        ("skill", "Judgment and Decision Making"),
        ("skill", "Systems Analysis"),
        ("skill", "Systems Evaluation"),
    ],
    "Mathematics & Data": [
        ("skill", "Mathematics"),
        ("knowledge", "Mathematics"),
    ],
    "Systems & Technology": [
        ("skill", "Equipment Selection"),
        ("skill", "Installation"),
        ("skill", "Operations Monitoring"),
        ("skill", "Operation and Control"),
        ("skill", "Equipment Maintenance"),
        ("skill", "Troubleshooting"),
        ("skill", "Repairing"),
        ("skill", "Quality Control Analysis"),
        ("knowledge", "Computers and Electronics"),
        ("knowledge", "Engineering and Technology"),
        ("knowledge", "Design"),
        ("knowledge", "Building and Construction"),
        ("knowledge", "Mechanical"),
        ("knowledge", "Telecommunications"),
        ("knowledge", "Transportation"),
    ],
    "Sciences": [
        ("skill", "Science"),
        ("knowledge", "Physics"),
        ("knowledge", "Chemistry"),
        ("knowledge", "Biology"),
        ("knowledge", "Medicine and Dentistry"),
    ],
    "Communication & Language": [
        ("skill", "Reading Comprehension"),
        ("skill", "Active Listening"),
        ("skill", "Writing"),
        ("skill", "Speaking"),
        ("knowledge", "English Language"),
        ("knowledge", "Foreign Language"),
        ("knowledge", "Communications and Media"),
    ],
    "Learning & Self-Development": [
        ("skill", "Active Learning"),
        ("skill", "Learning Strategies"),
        ("skill", "Monitoring"),
        ("knowledge", "Education and Training"),
    ],
    "People & Social Understanding": [
        ("skill", "Social Perceptiveness"),
        ("skill", "Coordination"),
        ("skill", "Persuasion"),
        ("skill", "Negotiation"),
        ("skill", "Instructing"),
        ("skill", "Service Orientation"),
        ("knowledge", "Customer and Personal Service"),
        ("knowledge", "Psychology"),
        ("knowledge", "Sociology and Anthropology"),
        ("knowledge", "Therapy and Counseling"),
    ],
    "Business & Management": [
        ("skill", "Time Management"),
        ("skill", "Management of Financial Resources"),
        ("skill", "Management of Material Resources"),
        ("skill", "Management of Personnel Resources"),
        ("knowledge", "Administration and Management"),
        ("knowledge", "Administrative"),
        ("knowledge", "Economics and Accounting"),
        ("knowledge", "Sales and Marketing"),
        ("knowledge", "Personnel and Human Resources"),
        ("knowledge", "Production and Processing"),
        ("knowledge", "Food Production"),
    ],
    "Humanities & Society": [
        ("knowledge", "Geography"),
        ("knowledge", "Fine Arts"),
        ("knowledge", "History and Archeology"),
        ("knowledge", "Philosophy and Theology"),
        ("knowledge", "Public Safety and Security"),
        ("knowledge", "Law and Government"),
    ],
}

CONCEPT_TO_COMPETENCY = {
    concept_key: competency
    for competency, concept_keys in COMPETENCY_GROUPS.items()
    for concept_key in concept_keys
}


def _vocab_block(items):
    return "\n".join(f"- {name}: {desc}" for name, desc in items)


# Max courses classified per Gemini call. Batching everything a
# transcript needs into as few calls as possible matters a lot under
# the free tier's 5-requests-per-minute cap -- a 15-course transcript
# costs 1 call here instead of 15.
BATCH_SIZE = 15

COURSE_CONCEPT_BATCH_PROMPT = f"""You are classifying MULTIPLE university courses against a FIXED, CONTROLLED
vocabulary from the O*NET occupational database. You must select ONLY from the exact
labels given below for EACH course — do not invent, rename, merge, or paraphrase any label.

O*NET SKILLS (generic work-behavior competencies):
{_vocab_block(ONET_SKILLS)}

O*NET KNOWLEDGE AREAS (academic/subject domains):
{_vocab_block(ONET_KNOWLEDGE)}

Courses to classify:
{{courses_block}}

Task: for EACH course listed above, select up to 5 Skills and up to 5 Knowledge areas
from the lists above that are GENUINELY relevant to what a student would learn or
practice in that course. Only include a label if you are reasonably confident it is a
meaningful match — do not pad the list with weak or generic matches just to reach 5. It
is fine to return fewer than 5, or even zero, for either list if nothing fits well.
Classify every course independently — one course's content must not influence another
course's classification.

For each selected label, give a confidence between 0 and 1.

Respond with ONLY this JSON structure, no markdown fences, no extra text. Use the exact
course code given for each course as the JSON key:
{{{{
  "<course code>": {{{{
    "skills": [{{{{"name": "<exact label from the Skills list>", "confidence": 0.0}}}}],
    "knowledge": [{{{{"name": "<exact label from the Knowledge list>", "confidence": 0.0}}}}]
  }}}}
}}}}"""

# Validated version 2 -- v1 let Gemini justify Core/Related purely from
# general transferable-skill usefulness (e.g. "writing is useful for any
# degree"), which meant the General tier never fired (0/12 in testing).
# v2 restricts the judgment to disciplinary subject-matter content only.
CAREER_RELEVANCE_PROMPT_V2 = """Classify the relevance of EACH of the following university courses to the
student's programme, based on ACADEMIC DISCIPLINARY RELEVANCE — not general usefulness.

Core: The course teaches knowledge or methods that are fundamental to the student's
programme's primary academic discipline.

Related: The course is not fundamental to the discipline, but its subject matter has a
direct and meaningful academic connection to the discipline.

General: The course does not substantially contribute subject knowledge or disciplinary
methods to the student's programme. This includes general education, language,
communication, or university-wide courses whose content is not specific to the discipline.

IMPORTANT: Do not classify a course as Core or Related merely because the skills learned
in the course (e.g., communication, writing, critical thinking, teamwork) are useful for
studying the programme or succeeding in a career. Evaluate the course's SUBJECT MATTER
and DISCIPLINARY CONTENT, not its general usefulness.

Follow this decision procedure:
1. Identify the primary academic discipline of the programme.
2. Identify the primary subject matter of the course.
3. Determine whether the course subject matter is:
   - fundamental to the discipline -> Core
   - directly connected but not fundamental -> Related
   - not substantially connected -> General
4. Do NOT use transferable skills or general career usefulness as evidence for Core or Related.

Examples:

Programme: Bachelor of Psychology
Course: Academic English
-> General
Reason: Although academic writing is useful for Psychology students, English is not
itself a core subject area of Psychology.

Programme: Bachelor of Computer Science
Course: Data Structures
-> Core
Reason: Data structures and their manipulation are fundamental subject matter within
Computer Science.

Programme: Bachelor of Computer Science
Course: Engineering Mathematics
-> Related
Reason: Mathematics directly supports computational and technical study, but is not
itself the central discipline of Computer Science.

Now classify the following. Evaluate each course independently — one course's
classification must not influence another's.

Student's Programme:
{programme}

Courses:
{courses_block}

Respond with ONLY this JSON structure, no markdown fences, no extra text. Use the exact
course code given for each course as the JSON key:
{{"<course code>": {{"tier": "Core" | "Related" | "General", "reason": "..."}}}}"""


# Backoff schedule for rate-limit errors, in seconds. The free tier's
# per-minute quota resets on a rolling window, so waiting comfortably
# longer than a minute across all retries clears even a fully-exhausted
# window rather than just guessing at a short delay.
RATE_LIMIT_BACKOFF_SECONDS = [15, 30, 60]


def _call_gemini(prompt):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(MODEL_NAME)

    for attempt, delay in enumerate([0] + RATE_LIMIT_BACKOFF_SECONDS):
        if delay:
            time.sleep(delay)
        try:
            response = model.generate_content(prompt)
            break
        except ResourceExhausted:
            if attempt == len(RATE_LIMIT_BACKOFF_SECONDS):
                raise
            continue

    text = response.text.strip()

    if "```" in text:
        text = re.sub(r"```json|```", "", text).strip()

    return json.loads(text)


def get_or_create_course_mappings(courses):
    """
    courses: list of (course_code, course_title) tuples.
    Returns dict: course_code -> {"skills": [...], "knowledge": [...]}

    Cached by course_code alone -- deliberately NEVER takes programme
    as input, so the same course always means the same thing regardless
    of which student or programme is asking. Every course not already
    cached is classified in as few Gemini calls as possible (BATCH_SIZE
    per call) rather than one call per course.
    """
    result = {}

    # One bulk lookup instead of one query per course -- on a full
    # cache hit (the common case after a student's first visit) this
    # turns N round trips to the DB into 1, which matters a lot more
    # than it sounds once you're talking to a remote Postgres instance
    # instead of a local one.
    all_codes = list({code for code, _ in courses})
    cached_rows = (
        CourseSkillMapping.query.filter(CourseSkillMapping.course_code.in_(all_codes)).all()
        if all_codes else []
    )
    cached_by_code = {}
    for r in cached_rows:
        cached_by_code.setdefault(r.course_code, []).append(r)

    uncached = []
    for course_code, course_title in courses:
        cached = cached_by_code.get(course_code)
        if cached:
            result[course_code] = {
                "skills": [{"name": r.concept_name, "confidence": r.confidence} for r in cached if r.concept_type == "skill"],
                "knowledge": [{"name": r.concept_name, "confidence": r.confidence} for r in cached if r.concept_type == "knowledge"],
            }
        else:
            uncached.append((course_code, course_title))

    for i in range(0, len(uncached), BATCH_SIZE):
        result.update(_classify_course_batch(uncached[i:i + BATCH_SIZE]))

    return result


def _normalize_batch_keys(raw):
    """
    Defensive normalization for batched-response JSON keys. The prompt
    asks for the bare course code as the key, but LLM output formatting
    can drift (e.g. once observed echoing back "[CHEM201]" instead of
    "CHEM201" because the course was shown in brackets in the prompt's
    numbered list) -- stripping whitespace/brackets/quotes here means a
    lookup by bare course code still succeeds even if that happens again.
    """
    return {k.strip().strip("[]\"'"): v for k, v in raw.items()}


def _classify_course_batch(batch):
    """
    batch: list of (course_code, course_title) tuples, already
    confirmed not cached. Makes ONE Gemini call for the whole batch,
    then commits each course's rows separately -- so if another
    request concurrently cached one course in this batch, only that
    one course falls back to its cached result; the rest of the batch
    is unaffected.
    """
    courses_block = "\n".join(f"{i + 1}. Course code: {code} | Title: {title}" for i, (code, title) in enumerate(batch))
    raw = _call_gemini(COURSE_CONCEPT_BATCH_PROMPT.format(courses_block=courses_block))
    raw = _normalize_batch_keys(raw)

    result = {}

    for course_code, course_title in batch:
        entry = raw.get(course_code, {})

        # Never trust a label Gemini didn't actually offer -- drop
        # anything outside the controlled vocabulary rather than caching it.
        skills = [s for s in entry.get("skills", []) if s.get("name") in SKILL_NAMES]
        knowledge = [k for k in entry.get("knowledge", []) if k.get("name") in KNOWLEDGE_NAMES]

        for s in skills:
            db.session.add(CourseSkillMapping(
                course_code=course_code, course_title=course_title,
                concept_type="skill", concept_name=s["name"], confidence=s["confidence"],
                model_name=MODEL_NAME, prompt_version=CLASSIFY_PROMPT_VERSION,
            ))
        for k in knowledge:
            db.session.add(CourseSkillMapping(
                course_code=course_code, course_title=course_title,
                concept_type="knowledge", concept_name=k["name"], confidence=k["confidence"],
                model_name=MODEL_NAME, prompt_version=CLASSIFY_PROMPT_VERSION,
            ))

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            cached = CourseSkillMapping.query.filter_by(course_code=course_code).all()
            skills = [{"name": r.concept_name, "confidence": r.confidence} for r in cached if r.concept_type == "skill"]
            knowledge = [{"name": r.concept_name, "confidence": r.confidence} for r in cached if r.concept_type == "knowledge"]

        result[course_code] = {"skills": skills, "knowledge": knowledge}

    return result


def get_or_create_relevances(courses, programme):
    """
    courses: list of (course_code, course_title, concepts) tuples.
    Returns dict: course_code -> relevance tier ("Core"/"Related"/"General")

    Cached by (course_code, programme) -- a different axis from
    get_or_create_course_mappings()'s cache, since relevance genuinely
    depends on the programme while the underlying concepts must not.
    Batched the same way: as few Gemini calls as possible.
    """
    result = {}

    # Same bulk-lookup change as get_or_create_course_mappings(), for
    # the same reason -- one query for every course's cache status
    # instead of one query per course.
    all_codes = list({code for code, _, _ in courses})
    cached_rows = (
        ProgrammeCourseRelevance.query.filter(
            ProgrammeCourseRelevance.course_code.in_(all_codes),
            ProgrammeCourseRelevance.programme == programme,
        ).all()
        if all_codes else []
    )
    cached_by_code = {r.course_code: r.relevance_tier for r in cached_rows}

    uncached = []
    for course_code, course_title, concepts in courses:
        tier = cached_by_code.get(course_code)
        if tier is not None:
            result[course_code] = tier
        else:
            uncached.append((course_code, course_title, concepts))

    for i in range(0, len(uncached), BATCH_SIZE):
        result.update(_classify_relevance_batch(uncached[i:i + BATCH_SIZE], programme))

    return result


def _classify_relevance_batch(batch, programme):
    """
    batch: list of (course_code, course_title, concepts) tuples,
    already confirmed not cached for this programme. Same
    one-call-per-batch, commit-per-course pattern as
    _classify_course_batch().
    """
    lines = []
    for i, (code, title, concepts) in enumerate(batch):
        knowledge_list = ", ".join(k["name"] for k in concepts.get("knowledge", [])) or "(none)"
        skills_list = ", ".join(s["name"] for s in concepts.get("skills", [])) or "(none)"
        lines.append(f"{i + 1}. Course code: {code} | Title: {title}\n   Knowledge: {knowledge_list}\n   Skills: {skills_list}")
    courses_block = "\n".join(lines)

    raw = _call_gemini(CAREER_RELEVANCE_PROMPT_V2.format(programme=programme, courses_block=courses_block))
    raw = _normalize_batch_keys(raw)

    result = {}

    for course_code, course_title, concepts in batch:
        entry = raw.get(course_code, {})
        tier = entry.get("tier")

        if tier not in CAREER_RELEVANCE_WEIGHTS:
            raise ValueError(f"Unexpected relevance tier from Gemini for {course_code!r}: {tier!r}")

        db.session.add(ProgrammeCourseRelevance(
            course_code=course_code, programme=programme, relevance_tier=tier,
            model_name=MODEL_NAME, prompt_version=RELEVANCE_PROMPT_VERSION,
        ))

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            cached = ProgrammeCourseRelevance.query.filter_by(
                course_code=course_code, programme=programme
            ).first()
            tier = cached.relevance_tier

        result[course_code] = tier

    return result


def _select_best_attempt_per_course(courses):
    """
    Same best-attempt rule calculate_cgpa_credits() uses: if a student
    retook a course, only its best passing attempt (or the latest one,
    if never passed) should count -- a retake must not let one course
    code contribute to the profile twice.
    """
    by_code = {}
    for c in courses:
        by_code.setdefault(c.course_code.strip().upper(), []).append(c)

    selected = []
    for code, attempts in by_code.items():
        passed = [c for c in attempts if c.grade not in FAIL_GRADES]
        best = max(passed, key=lambda c: GRADE_POINTS.get(c.grade, 0)) if passed else attempts[-1]
        selected.append(best)
    return selected


def build_student_profile(user_id):
    """
    Aggregates a student's completed courses into a weighted
    Knowledge/Skill competency profile:

        contribution = concept_confidence
                        x (grade_point / 4.0)
                        x credit_hour
                        x relevance_weight

    summed per concept across all of the student's courses.

    Gemini's role ends at semantic interpretation (which O*NET
    concepts a course maps to, how relevant a course is to the
    programme) -- every number in this aggregation is deterministic
    arithmetic on that interpretation, not an LLM output, so the same
    inputs always reproduce the same profile.

    Returns a list of {"concept_type", "concept_name", "raw_score",
    "percentage"} sorted by raw_score descending. Empty list if the
    student has no gradeable courses yet.
    """
    user = User.query.get(user_id)
    if user is None:
        raise ValueError("User not found.")

    courses = (
        db.session.query(Course)
        .join(Semester)
        .join(Transcript)
        .filter(Transcript.user_id == user_id)
        .all()
    )
    courses = _select_best_attempt_per_course(courses)

    gradeable = [
        c for c in courses
        if c.grade and c.credit_hour and GRADE_POINTS.get(c.grade) is not None
    ]

    # Two passes: first resolve every course's concepts + relevance
    # (batched, so a fresh transcript costs a small handful of Gemini
    # calls instead of one per course), then do the deterministic
    # weighting math in a second pass now that everything is available.
    concepts_by_code = get_or_create_course_mappings(
        [(c.course_code, c.course_name or c.course_code) for c in gradeable]
    )
    tier_by_code = get_or_create_relevances(
        [(c.course_code, c.course_name or c.course_code, concepts_by_code[c.course_code]) for c in gradeable],
        user.programme,
    )

    totals = {}
    contributors = {}   # (concept_type, concept_name) -> [{"course_code","course_title","grade","contribution"}]

    for course in gradeable:
        grade_point = GRADE_POINTS[course.grade]
        course_title = course.course_name or course.course_code
        concepts = concepts_by_code[course.course_code]
        tier = tier_by_code[course.course_code]

        grade_weight = grade_point / 4.0
        relevance_weight = CAREER_RELEVANCE_WEIGHTS.get(tier, CAREER_RELEVANCE_WEIGHTS["General"])

        for concept_type, items in (("skill", concepts["skills"]), ("knowledge", concepts["knowledge"])):
            for item in items:
                contribution = item["confidence"] * grade_weight * course.credit_hour * relevance_weight
                key = (concept_type, item["name"])
                totals[key] = totals.get(key, 0.0) + contribution
                contributors.setdefault(key, []).append({
                    "course_code": course.course_code,
                    "course_title": course_title,
                    "grade": course.grade,
                    "contribution": round(contribution, 3),
                })

    if not totals:
        return []

    max_score = max(totals.values())

    profile = []
    for (concept_type, concept_name), score in totals.items():
        courses_for_concept = sorted(
            contributors[(concept_type, concept_name)],
            key=lambda c: c["contribution"], reverse=True
        )
        profile.append({
            "concept_type": concept_type,
            "concept_name": concept_name,
            "raw_score": round(score, 3),
            "percentage": round(score / max_score * 100, 1) if max_score > 0 else 0.0,
            "courses": courses_for_concept,
        })

    profile.sort(key=lambda x: x["raw_score"], reverse=True)

    return profile


def build_competency_profile(profile):
    """
    Regroups an already-computed O*NET-concept-level profile (from
    build_student_profile()) into the broader, student-facing
    COMPETENCY_GROUPS -- e.g. "Programming" + "Technology Design"
    become "Software & Programming". Presentation-only: career
    matching still uses the concept-level profile this is built from,
    never this regrouped view.

    Returns a list of {"competency_name", "raw_score", "percentage",
    "courses"} sorted by raw_score descending, same shape as
    build_student_profile()'s output except keyed by competency_name
    instead of concept_name -- so top_strengths() works unchanged on
    either one.
    """
    totals = {}
    contributors = {}   # competency_name -> {course_code: course dict}

    for row in profile:
        key = (row["concept_type"], row["concept_name"])
        competency = CONCEPT_TO_COMPETENCY.get(key)
        if competency is None:
            continue  # shouldn't happen -- COMPETENCY_GROUPS covers all 68 labels

        totals[competency] = totals.get(competency, 0.0) + row["raw_score"]

        courses_by_code = contributors.setdefault(competency, {})
        for c in row["courses"]:
            code = c["course_code"]
            if code in courses_by_code:
                # This course reaches the same competency through more
                # than one O*NET concept (e.g. both "Programming" and
                # "Technology Design" landing under Software &
                # Programming) -- its total contribution to the
                # competency is the sum, not just one concept's share.
                courses_by_code[code]["contribution"] = round(
                    courses_by_code[code]["contribution"] + c["contribution"], 3
                )
            else:
                courses_by_code[code] = dict(c)

    if not totals:
        return []

    max_score = max(totals.values())

    result = [
        {
            "competency_name": competency,
            "raw_score": round(score, 3),
            "percentage": round(score / max_score * 100, 1) if max_score > 0 else 0.0,
            "courses": sorted(contributors[competency].values(), key=lambda c: c["contribution"], reverse=True),
        }
        for competency, score in totals.items()
    ]
    result.sort(key=lambda x: x["raw_score"], reverse=True)

    return result


# A concept below this normalized percentage isn't a meaningful
# strength -- it's noise (e.g. a single unrelated elective barely
# touching an obscure O*NET label, like "Geography" scoring 1.9%
# because one course happened to brush against it). Initial, not yet
# empirically calibrated threshold.
MIN_STRENGTH_PERCENTAGE = 25.0


def top_strengths(profile, top_n=5):
    """
    Returns up to top_n highest-scoring rows from an already-computed
    profile -- works on either build_student_profile()'s raw O*NET
    concept list or build_competency_profile()'s regrouped list,
    since both share a "percentage" field and this function doesn't
    care which. Excludes anything below MIN_STRENGTH_PERCENTAGE: a
    thin profile can legitimately return fewer than top_n items,
    since padding the list with near-zero-contribution rows just to
    fill five slots would misrepresent them as meaningful strengths.

    There is deliberately no concept-driven "growth" counterpart here
    -- see identify_improvement_courses() for why. A concept's
    aggregate score reflects how much evidence exists for it across
    every course that touches it, which is a different question from
    whether the student performed comparatively worse in any one of
    those courses. The two can (and often do) disagree: "Programming"
    can be an aggregate Strength built from four A-grade courses and
    one B+, while that same B+ course is independently worth flagging
    as an improvement opportunity. Deriving "areas for improvement"
    from the bottom of this same concept list conflates those two
    questions -- it surfaces concepts with thin or weak evidence
    (often General-relevance electives touched by only one course),
    not courses the student actually underperformed in, which could
    put an A-grade course under "needs improvement" for no better
    reason than it being the only evidence for an obscure concept.
    """
    meaningful = [row for row in profile if row["percentage"] >= MIN_STRENGTH_PERCENTAGE]
    return meaningful[:top_n]


# Only A+/A/A- count as strength-level grades -- every other grade
# (B+ and below) is an improvement candidate. Expressed as GRADE_POINTS["B+"]
# (the highest non-A-range value) rather than a bare number so it stays
# correct automatically if the grading scale in GRADE_POINTS ever changes.
IMPROVEMENT_GRADE_THRESHOLD = GRADE_POINTS["B+"]


def identify_improvement_courses(user_id, top_n=5):
    """
    Course-driven counterpart to top_strengths(): "which courses did
    the student perform comparatively worse in", not "which concepts
    have the least accumulated evidence". A course only qualifies if
    its grade is at or below IMPROVEMENT_GRADE_THRESHOLD, then
    qualifying courses are ranked by

        priority = grade_weakness x relevance_weight x credit_hour

    so a weak grade in a Core, high-credit course ranks above an
    equally weak grade in a General-relevance elective -- a low grade
    in an elective that barely relates to the student's programme
    isn't a meaningful "improvement opportunity" the way a weak grade
    in a core course is.

    Returns up to top_n courses, each with its own contributing
    O*NET concepts and their mapped student-facing competencies (via
    CONCEPT_TO_COMPETENCY) attached, so the UI can show why that
    course matters using the same competency vocabulary as the
    Strengths side. Empty list if nothing qualifies.
    """
    user = User.query.get(user_id)
    if user is None:
        raise ValueError("User not found.")

    courses = (
        db.session.query(Course)
        .join(Semester)
        .join(Transcript)
        .filter(Transcript.user_id == user_id)
        .all()
    )
    courses = _select_best_attempt_per_course(courses)

    candidates = [
        c for c in courses
        if c.grade and c.credit_hour
        and GRADE_POINTS.get(c.grade) is not None
        and GRADE_POINTS[c.grade] <= IMPROVEMENT_GRADE_THRESHOLD
    ]

    if not candidates:
        return []

    concepts_by_code = get_or_create_course_mappings(
        [(c.course_code, c.course_name or c.course_code) for c in candidates]
    )
    tier_by_code = get_or_create_relevances(
        [(c.course_code, c.course_name or c.course_code, concepts_by_code[c.course_code]) for c in candidates],
        user.programme,
    )

    scored = []
    for course in candidates:
        concepts = concepts_by_code[course.course_code]
        tier = tier_by_code[course.course_code]

        grade_weakness = IMPROVEMENT_GRADE_THRESHOLD - GRADE_POINTS[course.grade]
        relevance_weight = CAREER_RELEVANCE_WEIGHTS.get(tier, CAREER_RELEVANCE_WEIGHTS["General"])
        priority = grade_weakness * relevance_weight * course.credit_hour

        concept_keys = [("skill", s["name"]) for s in concepts["skills"]] + [("knowledge", k["name"]) for k in concepts["knowledge"]]
        concept_names = [name for _, name in concept_keys]
        competency_names = list(dict.fromkeys(
            CONCEPT_TO_COMPETENCY[key] for key in concept_keys if key in CONCEPT_TO_COMPETENCY
        ))

        scored.append({
            "course_code": course.course_code,
            "course_title": course.course_name or course.course_code,
            "grade": course.grade,
            "credit_hour": course.credit_hour,
            "relevance_tier": tier,
            "priority": round(priority, 3),
            "concepts": concept_names,
            "competencies": competency_names,
        })

    scored.sort(key=lambda r: r["priority"], reverse=True)

    return scored[:top_n]


def save_skill_profile(user_id, competency_profile, top_n=5):
    """
    Persists the top_n Strengths into the SkillProfile table, replacing
    whatever was stored before -- SkillProfile always reflects the most
    recently computed profile, not a history of past snapshots.

    Takes the COMPETENCY-level profile (build_competency_profile()'s
    output), not the raw O*NET concept-level one -- SkillProfile
    should reflect what the student actually sees ("Software &
    Programming"), not the underlying O*NET labels only career
    matching needs.

    Only Strengths are stored here -- identify_improvement_courses()'s
    output is course-shaped (course_code, grade, credit_hour), not
    competency-shaped, so it doesn't fit this table's schema and isn't
    persisted for now; the /career route recomputes it fresh each time.
    """
    latest_transcript = (
        Transcript.query
        .filter_by(user_id=user_id)
        .order_by(Transcript.uploaded_at.desc())
        .first()
    )
    if latest_transcript is None:
        raise ValueError("Student has no transcript to attach this profile to.")

    strengths = top_strengths(competency_profile, top_n=top_n)

    SkillProfile.query.filter_by(user_id=user_id).delete()

    for row in strengths:
        db.session.add(SkillProfile(
            user_id=user_id,
            transcript_id=latest_transcript.transcript_id,
            skill_name=row["competency_name"],
            raw_score=row["raw_score"],
            percentage=row["percentage"],
            skill_category="strength",
        ))

    db.session.commit()


# In-process cache of every occupation's O*NET concept-importance
# vector, populated on first use and kept for the life of this
# process. Occupation data is static reference data -- it only
# changes when someone re-runs scripts/load_onet_data.py, an offline
# operation -- so re-fetching all ~60K rows from Postgres on every
# single /career page view would be pure waste. Restart the app
# process to pick up a fresh load.
_occupation_vectors_cache = None


def _get_occupation_vectors():
    global _occupation_vectors_cache

    if _occupation_vectors_cache is not None:
        return _occupation_vectors_cache

    vectors = {}
    for row in OnetOccupationConcept.query.all():
        vectors.setdefault(row.onet_soc_code, {})[(row.concept_type, row.concept_name)] = row.importance_normalized

    occupations = {
        occ.onet_soc_code: {"title": occ.title, "description": occ.description}
        for occ in OnetOccupation.query.filter(OnetOccupation.onet_soc_code.in_(vectors.keys())).all()
    }

    _occupation_vectors_cache = (vectors, occupations)
    return _occupation_vectors_cache


def _cosine_similarity(vector_a, vector_b):
    """
    Standard cosine similarity between two {key: value} vectors over
    a shared (but not necessarily identical) key space. The dot
    product only needs to sum over keys present in both -- any key
    unique to one vector contributes 0 either way -- but each
    vector's own magnitude must sum over all of its own keys.
    """
    shared_keys = vector_a.keys() & vector_b.keys()
    if not shared_keys:
        return 0.0

    dot_product = sum(vector_a[k] * vector_b[k] for k in shared_keys)
    magnitude_a = sum(v * v for v in vector_a.values()) ** 0.5
    magnitude_b = sum(v * v for v in vector_b.values()) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def _top_contributing_concepts(vector_a, vector_b, top_n=5):
    """
    Returns the top_n (concept_type, concept_name) keys that
    contributed most to the dot product between two vectors -- i.e.
    the shared dimensions that actually drove the similarity score,
    ranked by how much each one contributed, not just any overlap
    regardless of size.
    """
    shared_keys = vector_a.keys() & vector_b.keys()
    contributions = sorted(
        ((key, vector_a[key] * vector_b[key]) for key in shared_keys),
        key=lambda c: c[1], reverse=True
    )
    return [key for key, _ in contributions[:top_n]]


# Career match tier boundaries. Calibrated against real observed
# scores, not intuition about what a percentage "should" mean -- 5
# synthetic programme profiles tested against the real O*NET dataset
# all had their best match land between 47.6% and 59.0%, nowhere near
# 80-100%. A naive 85/70/50 scale (borrowed from the original mockup)
# would never show "Strong" for anyone. Still based on synthetic
# profiles rather than a large real sample, so worth revisiting once
# real student data is available.
STRONG_MATCH_THRESHOLD = 0.50
MIN_CAREER_SIMILARITY = 0.25   # below this, a career isn't shown at all


def _career_match_tier(similarity):
    if similarity >= STRONG_MATCH_THRESHOLD:
        return "Strong Match", "strong"
    return "Moderate Match", "moderate"


def match_careers(user_id, top_n=10, profile=None):
    """
    Ranks O*NET occupations by cosine similarity between the student's
    O*NET concept-level profile (build_student_profile()) and each
    occupation's Skill/Knowledge importance vector
    (OnetOccupationConcept.importance_normalized).

    `profile` lets a caller that already ran build_student_profile()
    pass its result straight in, instead of this function silently
    recomputing it from scratch. build_student_profile() isn't free
    (it resolves every course's O*NET concepts and programme
    relevance), and the Dashboard, Career page, and Report all already
    call it themselves right before calling this -- without `profile`,
    that work happened twice in the same request.

    Purely deterministic -- Gemini's role ends at building the concept
    profile; nothing in this function is an LLM output, so re-running
    it against the same stored data always reproduces the same ranking.

    Occupations with no concept data at all (~106 of O*NET's 1,016 --
    mostly "All Other" residual SOC categories and the military
    classification block, found during the Phase 2A data inspection)
    are naturally excluded: they never get an entry in the occupation
    vector cache, so they can't be scored.

    Occupations scoring below MIN_CAREER_SIMILARITY are excluded
    entirely rather than shown as a weak match.

    Returns up to top_n {"onet_soc_code", "title", "description",
    "similarity", "match_percentage", "tier", "tier_class",
    "matched_competencies"} dicts sorted by similarity descending.
    matched_competencies is the "why it matched" explanation -- the
    student-facing competency names (via CONCEPT_TO_COMPETENCY, same
    vocabulary as Strengths/Improvement) behind the O*NET concepts
    that contributed most to that occupation's score, not just any
    shared concept regardless of size.

    Empty list if the student has no profile yet.
    """
    concept_profile = profile if profile is not None else build_student_profile(user_id)
    if not concept_profile:
        return []

    student_vector = {
        (row["concept_type"], row["concept_name"]): row["raw_score"]
        for row in concept_profile
    }

    occupation_vectors, occupations = _get_occupation_vectors()

    # Score every occupation first (cheap -- just the cosine calc), then
    # only compute "why it matched" for the occupations that actually
    # make the cut. Ranking the top contributing concepts is wasted
    # work for the ~900 occupations that won't be shown.
    scored = []
    for soc_code, occ_vector in occupation_vectors.items():
        similarity = _cosine_similarity(student_vector, occ_vector)
        if similarity < MIN_CAREER_SIMILARITY:
            continue
        scored.append((soc_code, occ_vector, similarity))

    scored.sort(key=lambda r: r[2], reverse=True)

    results = []
    for soc_code, occ_vector, similarity in scored[:top_n]:
        top_concepts = _top_contributing_concepts(student_vector, occ_vector, top_n=5)
        matched_competencies = list(dict.fromkeys(
            CONCEPT_TO_COMPETENCY[key] for key in top_concepts if key in CONCEPT_TO_COMPETENCY
        ))
        tier, tier_class = _career_match_tier(similarity)

        results.append({
            "onet_soc_code": soc_code,
            "title": occupations[soc_code]["title"],
            "description": occupations[soc_code]["description"],
            "similarity": round(similarity, 4),
            "match_percentage": round(similarity * 100, 1),
            "tier": tier,
            "tier_class": tier_class,
            "matched_competencies": matched_competencies,
        })

    return results


def save_career_recommendations(user_id, careers):
    """
    Persists match_careers()'s output into CareerRecommendation so
    Feedback (which references a specific career_id) has something
    real to attach to.

    Deliberately get-or-create per (user_id, career_name), NOT the
    delete-then-reinsert pattern save_skill_profile() uses: deleting a
    CareerRecommendation row would violate the Feedback FK constraint
    the moment a student has actually rated it, and even ignoring
    that, wiping the table on every page view would destroy feedback
    history -- which is valuable evaluation data for an FYP, not
    disposable state. An existing row is updated in place (score,
    tier, rank can drift as the student's transcript changes); a new
    one is only inserted for a career never recommended to this
    student before.

    Returns a dict mapping career title -> career_id, so the route can
    tell the template which career_id backs each displayed card.
    """
    latest_transcript = (
        Transcript.query
        .filter_by(user_id=user_id)
        .order_by(Transcript.uploaded_at.desc())
        .first()
    )
    if latest_transcript is None:
        raise ValueError("Student has no transcript to attach these recommendations to.")

    name_to_id = {}

    for rank, career in enumerate(careers, start=1):
        existing = CareerRecommendation.query.filter_by(
            user_id=user_id, career_name=career["title"]
        ).first()

        if existing:
            existing.career_score = career["similarity"]
            existing.match_level = career["tier_class"]
            existing.rank = rank
            existing.transcript_id = latest_transcript.transcript_id
            name_to_id[career["title"]] = existing.career_id
        else:
            row = CareerRecommendation(
                user_id=user_id,
                transcript_id=latest_transcript.transcript_id,
                career_name=career["title"],
                career_score=career["similarity"],
                match_level=career["tier_class"],
                rank=rank,
            )
            db.session.add(row)
            db.session.flush()  # populate row.career_id before commit
            name_to_id[career["title"]] = row.career_id

    db.session.commit()

    return name_to_id
