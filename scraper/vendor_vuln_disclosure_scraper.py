"""
MIS 545 Group Project — Vendor Vulnerability Disclosure Scraper
Author: Ismail (reviewed and improved with Gemini Pro / Perplexity assistance)
Purpose: Check each company's website for evidence of a genuine vulnerability
disclosure mechanism (security.txt, security/trust pages, bug bounty links).

Design decisions documented in team methodology log (Log Entries 5-10, 16).

Log Entry 16 (this revision): Manual review of the 346-company run found 4
false positives (Aden, Chargehound, Fogbender, Jasper.ai), all triggered by a
bare "security@" contact email with no real disclosure process described.
Fix: DISCLOSURE_KEYWORDS is now split into STRONG_DISCLOSURE_KEYWORDS
(self-sufficient — e.g. "bug bounty", "hackerone", "responsible disclosure")
and WEAK_DISCLOSURE_KEYWORDS (email/contact patterns — e.g. "security@").
A weak keyword only counts as a positive signal if disclosure-related
language (vulnerability, bug, disclos-, "report a...") appears within a
150-character window around the match. Strong keywords still qualify on
their own, exactly as before.
"""

import argparse
import requests
import pandas as pd
import time
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, SSLError

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

TIMEOUT = (5, 5)  # (connect timeout, read timeout) in seconds
DELAY_BETWEEN_REQUESTS = 1.5

PATHS = [
    "/.well-known/security.txt",
    "/security.txt",
    "/security",
    "/trust",
    "/trust-center",
    "/bug-bounty",
    "/responsible-disclosure",
    "/vulnerability-disclosure-policy",
    "/security-policy",
    "/responsible-disclosure-policy",
    "/coordinated-vulnerability-disclosure",
    "/bug-bounty-program",
    "/security/bug-bounty",
    "/security/vulnerability-disclosure-policy",
    "/security/report-a-vulnerability",
    "/trust/report-a-vulnerability",
    "/whitehat",
]

STRONG_DISCLOSURE_KEYWORDS = [
    "vulnerability disclosure",
    "responsible disclosure",
    "coordinated disclosure",
    "report a vulnerability",
    "report a security",
    "bug bounty",
    "bugcrowd",
    "hackerone",
    "security researcher",
    "vulnerability disclosure policy",
    "vulnerability disclosure program",
    "safe harbor",
]

WEAK_DISCLOSURE_KEYWORDS = [
    "vulnerability-disclosure@",
    "security@",
]

CONTEXT_CONFIRM_KEYWORDS = [
    "vulnerab", "bug bounty", "bugcrowd", "hackerone",
    "disclos", "report a", "security issue", "security bug",
    "security researcher", "safe harbor", "pgp",
]

CONTEXT_WINDOW = 150  # characters on each side of a weak keyword match

COMPLIANCE_ONLY_KEYWORDS = [
    "soc 2", "soc2", "iso 27001", "iso/iec 27001", "penetration testing",
    "encrypted in transit", "encryption at rest", "compliance",
]


def build_regex(keywords):
    return {
        kw: re.compile(r"(?:^|\W)" + re.escape(kw) + r"(?:$|\W)", re.IGNORECASE)
        for kw in keywords
    }


STRONG_PATTERNS = build_regex(STRONG_DISCLOSURE_KEYWORDS)
WEAK_PATTERNS = build_regex(WEAK_DISCLOSURE_KEYWORDS)
COMPLIANCE_PATTERNS = build_regex(COMPLIANCE_ONLY_KEYWORDS)

ALL_DISCLOSURE_PATTERNS = {**STRONG_PATTERNS, **WEAK_PATTERNS}

CONTEXT_CONFIRM_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in CONTEXT_CONFIRM_KEYWORDS),
    re.IGNORECASE,
)


def get_base_domain(url: str, scheme: str = "https") -> str:
    if not url.startswith("http"):
        url = f"{scheme}://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def strip_www(domain: str) -> str:
    return domain[4:] if domain.startswith("www.") else domain


def check_url(url: str):
    """Returns status/final_url/text for a single URL, following redirects."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        final_domain = strip_www(urlparse(resp.url).netloc)
        original_domain = strip_www(urlparse(url).netloc)
        redirected_offsite = final_domain != original_domain

        visible_text = ""
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            visible_text = soup.get_text(separator=" ", strip=True)

        return {
            "status": resp.status_code,
            "final_url": resp.url,
            "redirected_offsite": redirected_offsite,
            "text": visible_text,
            "error": None,
        }
    except SSLError as e:
        return {"status": "SSL_ERROR", "final_url": None, "redirected_offsite": False,
                "text": "", "error": str(e)}
    except RequestException as e:
        return {"status": None, "final_url": None, "redirected_offsite": False,
                "text": "", "error": str(e)}


def classify_evidence(text: str):
    """
    Apply the corrected rubric (Log Entry 16):
    - Strong keywords qualify a page as a positive on their own.
    - Weak keywords (bare "security@" style contacts) only qualify if
      disclosure-related language appears within CONTEXT_WINDOW characters
      of the match, so a generic "email us with questions" footer doesn't
      get mistaken for a real disclosure program.
    """
    strong_hits = [kw for kw, prog in STRONG_PATTERNS.items() if prog.search(text)]

    weak_hits = []
    for kw, prog in WEAK_PATTERNS.items():
        match = prog.search(text)
        if not match:
            continue
        window = text[max(0, match.start() - CONTEXT_WINDOW):match.end() + CONTEXT_WINDOW]
        if CONTEXT_CONFIRM_PATTERN.search(window):
            weak_hits.append(kw)

    disclosure_hits = strong_hits + weak_hits
    compliance_hits = [kw for kw, prog in COMPLIANCE_PATTERNS.items() if prog.search(text)]
    return len(disclosure_hits) > 0, disclosure_hits, compliance_hits


def scrape_company(row):
    base = get_base_domain(row["website_domain"], scheme="https")
    evidence = {
        "base_domain_checked": base,
        "site_reachable": False,
        "any_redirect_offsite": False,
        "final_label_candidate": 0,
        "disclosure_keywords_found": "",
        "compliance_only_keywords_found": "",
        "evidence_url": "",
        "evidence_snippet": "",
        "paths_checked": ";".join(PATHS),
        "notes": "",
    }

    any_success = False
    http_fallback = False

    for path in PATHS:
        full_url = urljoin(base, path)
        result = check_url(full_url)

        if result["status"] == "SSL_ERROR" and not http_fallback:
            base = get_base_domain(row["website_domain"], scheme="http")
            evidence["base_domain_checked"] = base
            full_url = urljoin(base, path)
            result = check_url(full_url)
            http_fallback = True

        if result["status"] not in (None, "SSL_ERROR"):
            time.sleep(DELAY_BETWEEN_REQUESTS)

        if result["status"] in (None, "SSL_ERROR"):
            continue

        any_success = True
        if result["redirected_offsite"]:
            evidence["any_redirect_offsite"] = True

        if result["status"] == 200 and result["text"]:
            has_disclosure, disclosure_hits, compliance_hits = classify_evidence(result["text"])

            if has_disclosure:
                evidence["final_label_candidate"] = 1
                evidence["disclosure_keywords_found"] = ";".join(disclosure_hits)
                evidence["evidence_url"] = result["final_url"]

                snippet_match = ALL_DISCLOSURE_PATTERNS[disclosure_hits[0]].search(result["text"])
                if snippet_match:
                    snippet_idx = snippet_match.start()
                    evidence["evidence_snippet"] = result["text"][max(0, snippet_idx - 80):snippet_idx + 120]
                break

            elif compliance_hits and not evidence["compliance_only_keywords_found"]:
                evidence["compliance_only_keywords_found"] = ";".join(compliance_hits)
                evidence["evidence_url"] = result["final_url"]

    evidence["site_reachable"] = any_success

    notes = []
    if not any_success:
        notes.append("SITE_UNREACHABLE_OR_DEFUNCT -- flag for exclusion, verify manually")
    else:
        if evidence["any_redirect_offsite"]:
            notes.append("OFFSITE_REDIRECT_DETECTED -- verify domain still valid, check for company acquisition/rename")
        if http_fallback:
            notes.append("HTTP_FALLBACK -- forced downgrade to HTTP due to SSL Error")

    evidence["notes"] = " | ".join(notes)
    return evidence


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape company websites for vulnerability disclosure evidence."
    )
    parser.add_argument(
        "input_csv",
        help="Path to input CSV. Must contain 'company_name' and 'website_domain' columns."
    )
    parser.add_argument(
        "-o", "--output_csv",
        default=None,
        help="Path to output CSV. Defaults to '_RESULTS.csv' if not specified."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_csv = args.input_csv
    output_csv = args.output_csv or input_csv.replace(".csv", "_RESULTS.csv")

    df = pd.read_csv(input_csv)
    results = []

    for i, row in df.iterrows():
        print(f"[{i+1}/{len(df)}] Checking {row['company_name']}...")
        evidence = scrape_company(row)
        results.append({**row.to_dict(), **evidence})

    results_df = pd.DataFrame(results)
    results_df.to_csv(output_csv, index=False)

    print(f"Done. Results saved to {output_csv}")
    print(f"Candidate positives: {(results_df['final_label_candidate']==1).sum()}")
    print(f"Unreachable/flagged: {(results_df['site_reachable']==False).sum()}")


if __name__ == "__main__":
    main()
