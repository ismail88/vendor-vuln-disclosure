"""
Vendor Vulnerability Disclosure Scraper
Author: Ismail (reviewed and improved with AI assistance)
Purpose: Check each company's website for evidence of a genuine vulnerability
disclosure mechanism (security.txt, security/trust pages, bug bounty links).

Design decisions documented in docs/METHODOLOGY.md (Log Entries 5-10, 16, 17).

Log Entry 17 (this revision): The v2 full run returned a 13.29% candidate-positive
rate (46/346) -- well above the Hexiosec benchmark range even accounting for our
stratified sampling. Rather than manually reviewing all 46, we added a
`needs_manual_review` column so only the genuinely ambiguous cases require a
human look:
  - Any security.txt hit (RFC 9116 file) is now auto-trusted directly off the
    presence of a "Contact:" field in the raw file, without depending on the
    general keyword classifier.
  - "vulnerability-disclosure@" is specific enough to auto-trust on its own and
    is no longer treated as an ambiguous "weak" keyword.
  - The bare "security@" pattern remains the only keyword that still requires
    manual review even after passing the context-window check, since it's the
    one pattern historically prone to false positives (Log Entry 16).
See scraper/triage_positives.py for a standalone helper that backfills this same
triage logic onto an already-completed results CSV without re-scraping.
"""

import argparse
import requests
import pandas as pd
import time
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, SSLError

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

TIMEOUT = (5, 5)
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

SECURITY_TXT_PATHS = {"/.well-known/security.txt", "/security.txt"}

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

TRUSTED_EMAIL_KEYWORDS = [
    "vulnerability-disclosure@",
]

WEAK_DISCLOSURE_KEYWORDS = [
    "security@",
]

CONTEXT_CONFIRM_KEYWORDS = [
    "vulnerab", "bug bounty", "bugcrowd", "hackerone",
    "disclos", "report a", "security issue", "security bug",
    "security researcher", "safe harbor", "pgp",
]

CONTEXT_WINDOW = 150

COMPLIANCE_ONLY_KEYWORDS = [
    "soc 2", "soc2", "iso 27001", "iso/iec 27001", "penetration testing",
    "encrypted in transit", "encryption at rest", "compliance",
]

SECURITY_TXT_CONTACT_PATTERN = re.compile(r"^Contact:\s*\S+", re.IGNORECASE | re.MULTILINE)


def build_regex(keywords):
    return {
        kw: re.compile(r"(?:^|\W)" + re.escape(kw) + r"(?:$|\W)", re.IGNORECASE)
        for kw in keywords
    }


STRONG_PATTERNS = build_regex(STRONG_DISCLOSURE_KEYWORDS)
TRUSTED_EMAIL_PATTERNS = build_regex(TRUSTED_EMAIL_KEYWORDS)
WEAK_PATTERNS = build_regex(WEAK_DISCLOSURE_KEYWORDS)
COMPLIANCE_PATTERNS = build_regex(COMPLIANCE_ONLY_KEYWORDS)

ALL_DISCLOSURE_PATTERNS = {**STRONG_PATTERNS, **TRUSTED_EMAIL_PATTERNS, **WEAK_PATTERNS}

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
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        final_domain = strip_www(urlparse(resp.url).netloc)
        original_domain = strip_www(urlparse(url).netloc)
        redirected_offsite = final_domain != original_domain

        visible_text = ""
        raw_text = resp.text if resp.status_code == 200 else ""
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            visible_text = soup.get_text(separator=" ", strip=True)

        return {
            "status": resp.status_code,
            "final_url": resp.url,
            "redirected_offsite": redirected_offsite,
            "text": visible_text,
            "raw_text": raw_text,
            "error": None,
        }
    except SSLError as e:
        return {"status": "SSL_ERROR", "final_url": None, "redirected_offsite": False,
                "text": "", "raw_text": "", "error": str(e)}
    except RequestException as e:
        return {"status": None, "final_url": None, "redirected_offsite": False,
                "text": "", "raw_text": "", "error": str(e)}


def is_confirmed_security_txt(raw_text: str) -> bool:
    return bool(SECURITY_TXT_CONTACT_PATTERN.search(raw_text or ""))


def classify_evidence(text: str):
    strong_hits = [kw for kw, prog in STRONG_PATTERNS.items() if prog.search(text)]
    trusted_email_hits = [kw for kw, prog in TRUSTED_EMAIL_PATTERNS.items() if prog.search(text)]

    weak_hits = []
    for kw, prog in WEAK_PATTERNS.items():
        match = prog.search(text)
        if not match:
            continue
        window = text[max(0, match.start() - CONTEXT_WINDOW):match.end() + CONTEXT_WINDOW]
        if CONTEXT_CONFIRM_PATTERN.search(window):
            weak_hits.append(kw)

    disclosure_hits = strong_hits + trusted_email_hits + weak_hits
    compliance_hits = [kw for kw, prog in COMPLIANCE_PATTERNS.items() if prog.search(text)]
    needs_review = bool(weak_hits) and not strong_hits and not trusted_email_hits
    return len(disclosure_hits) > 0, disclosure_hits, compliance_hits, needs_review


def scrape_company(row):
    base = get_base_domain(row["website_domain"], scheme="https")
    evidence = {
        "base_domain_checked": base,
        "site_reachable": False,
        "any_redirect_offsite": False,
        "final_label_candidate": 0,
        "needs_manual_review": False,
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
            if path in SECURITY_TXT_PATHS and is_confirmed_security_txt(result["raw_text"]):
                evidence["final_label_candidate"] = 1
                evidence["needs_manual_review"] = False
                evidence["disclosure_keywords_found"] = "RFC9116_CONTACT_FIELD"
                evidence["evidence_url"] = result["final_url"]
                evidence["evidence_snippet"] = result["raw_text"][:200]
                evidence["notes"] = "SECURITY_TXT_CONFIRMED -- auto-trusted, no review needed"
                break

            has_disclosure, disclosure_hits, compliance_hits, needs_review = classify_evidence(result["text"])

            if has_disclosure:
                evidence["final_label_candidate"] = 1
                evidence["needs_manual_review"] = needs_review
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
        if evidence["needs_manual_review"]:
            notes.append("NEEDS_MANUAL_REVIEW -- bare security@ match, verify context manually")

    if evidence["notes"]:
        evidence["notes"] = evidence["notes"] + " | " + " | ".join(notes) if notes else evidence["notes"]
    else:
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

    positives = results_df["final_label_candidate"] == 1
    needs_review = results_df["needs_manual_review"] == True

    print(f"Done. Results saved to {output_csv}")
    print(f"Candidate positives: {positives.sum()}")
    print(f"  Auto-accepted:     {(positives & ~needs_review).sum()}")
    print(f"  Needs review:      {(positives & needs_review).sum()}")
    print(f"Unreachable/flagged: {(results_df['site_reachable']==False).sum()}")


if __name__ == "__main__":
    main()
