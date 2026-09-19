"""
One-time reference-data scraper: collects the official "Career
Prospects" list for every undergraduate programme on UM's study
portal (study.um.edu.my) and writes it to a CSV, one row per
(programme, career title).

This is the programme -> graduate-destination ground truth the career
re-ranking step is built on -- UM's own published answer to "what jobs
does this degree lead to", rather than an LLM's judgment. Like
scripts/load_onet_data.py it's offline reference data: not run by the
app, and never touches the database. Re-running simply overwrites the
CSV.

The portal answers requests without a browser User-Agent with an HTTP
500 (verified), so one is always sent. Requests are spaced out and
retried, since this is a public university site, not an API.

Needs beautifulsoup4 (offline-only, so deliberately not in
requirements.txt):
    pip install beautifulsoup4

Usage:
    python scripts/scrape_um_career_prospects.py [output.csv]
"""
import csv
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://study.um.edu.my/"
INDEX_PAGE = "undergraduate-faculties"
HEADERS = {"User-Agent": "Mozilla/5.0 (FYP research scraper; UM student project)"}

REQUEST_DELAY_SECONDS = 1.5
RETRY_DELAYS_SECONDS = [3, 10, 30]

# Site-wide navigation/footer links present on every page -- anything
# else a faculty page links to is one of its programmes.
NAV_LINKS = {
    "index", "programmes", "undergraduate-faculties", "international-student",
    "how-to-apply", "faqs-amp-info", "our-team",
}

CAREER_HEADING = "career prospects"


def fetch(slug):
    for delay in [0] + RETRY_DELAYS_SECONDS:
        if delay:
            time.sleep(delay)
        try:
            response = requests.get(BASE_URL + slug, headers=HEADERS, timeout=30)
        except requests.RequestException:
            continue
        if response.status_code == 200:
            time.sleep(REQUEST_DELAY_SECONDS)
            return BeautifulSoup(response.text, "html.parser")
    return None


def _local_links(soup):
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip().lstrip("/")
        if not href or href.startswith(("#", "http", "mailto:")) or "." in href:
            continue
        links.append(href)
    return list(dict.fromkeys(links))


def faculty_slugs(index_soup):
    return [href for href in _local_links(index_soup) if href not in NAV_LINKS]


def programme_slugs(faculty_soup, faculty_slug, all_faculty_slugs):
    return [
        href for href in _local_links(faculty_soup)
        if href not in NAV_LINKS and href != faculty_slug and href not in all_faculty_slugs
    ]


def split_careers(text):
    # Lists are comma-separated sentences ("A, B, C."), occasionally
    # semicolon- or newline-separated.
    parts = re.split(r"[,;\n•]", text)
    careers = []
    for part in parts:
        title = re.sub(r"\s+", " ", part).strip(" .\t-")
        title = re.sub(r"^(and|or)\s+", "", title, flags=re.IGNORECASE)
        if title:
            careers.append(title)
    return list(dict.fromkeys(careers))


def parse_programme(soup):
    """
    Returns (programme_title, [career titles]) -- careers is empty if
    the page has no Career Prospects section.
    """
    heading = soup.find("h2")
    programme = heading.get_text(" ", strip=True) if heading else None

    for h4 in soup.find_all("h4"):
        if h4.get_text(strip=True).lower() != CAREER_HEADING:
            continue
        section = h4.find_next_sibling()
        if section is None:
            return programme, []
        items = [li.get_text(" ", strip=True) for li in section.find_all("li")]
        if items:
            return programme, list(dict.fromkeys(i.strip(" .") for i in items if i.strip(" .")))
        return programme, split_careers(section.get_text("\n", strip=True))

    return programme, []


def scrape():
    index = fetch(INDEX_PAGE)
    if index is None:
        raise RuntimeError("Could not load the faculty index page.")

    faculties = faculty_slugs(index)
    rows, report = [], []

    for faculty in faculties:
        faculty_soup = fetch(faculty)
        if faculty_soup is None:
            report.append((faculty, None, "FACULTY PAGE FAILED"))
            continue

        faculty_name = faculty_soup.find("h2")
        faculty_name = faculty_name.get_text(" ", strip=True) if faculty_name else faculty

        for slug in programme_slugs(faculty_soup, faculty, faculties):
            soup = fetch(slug)
            if soup is None:
                report.append((faculty, slug, "PAGE FAILED"))
                continue

            programme, careers = parse_programme(soup)
            report.append((faculty, slug, f"{len(careers)} careers" if careers else "NO CAREER SECTION"))

            for career in careers:
                rows.append({
                    "faculty": faculty_name,
                    "programme": programme,
                    "programme_slug": slug,
                    "career_title": career,
                })

    return rows, report


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "um_career_prospects.csv"

    rows, report = scrape()

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["faculty", "programme", "programme_slug", "career_title"])
        writer.writeheader()
        writer.writerows(rows)

    for faculty, slug, status in report:
        print(f"{faculty:45} {slug or '':70} {status}")
    print(f"\n{len(rows)} career rows from {len({r['programme_slug'] for r in rows})} programmes -> {output}")
