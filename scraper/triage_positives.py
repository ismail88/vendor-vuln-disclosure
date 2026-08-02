"""
Positive Triage Helper
Author: Ismail (with AI assistance)
Purpose: Split the candidate positives from a results CSV into "auto-accept"
(trustworthy without manual review) vs. "needs review" (the bare security@
weak-keyword cases that still need a human eyeball), per Log Entry 17 in
docs/METHODOLOGY.md. Works on any existing RESULTS CSV without re-running the
scraper.

Auto-accept rules (no manual check needed):
  - Any hit whose evidence_url is a security.txt path (/.well-known/security.txt
    or /security.txt) with a Contact: field visible in the evidence text --
    RFC 9116 files are structured/standardized enough to trust.
  - Any hit that includes at least one STRONG keyword (bug bounty, hackerone,
    responsible disclosure, safe harbor, etc.).
  - Any hit that includes "vulnerability-disclosure@" -- specific enough to
    trust on its own.

Needs review:
  - Any positive whose ONLY disclosure signal is the bare "security@" keyword.
  - Any security.txt-path hit whose evidence_snippet does NOT contain a
    "Contact:" field -- this catches SPA/soft-404 sites that return HTML for
    every path rather than a real RFC 9116 file.

Usage:
    python scraper/triage_positives.py data/Team_YC_Vendor_Sample_346_RESULTSv2.csv
"""

import argparse
import re
import pandas as pd

STRONG_KEYWORDS = {
    "vulnerability disclosure", "responsible disclosure", "coordinated disclosure",
    "report a vulnerability", "report a security", "bug bounty", "bugcrowd",
    "hackerone", "security researcher", "vulnerability disclosure policy",
    "vulnerability disclosure program", "safe harbor",
}
TRUSTED_WEAK_KEYWORDS = {"vulnerability-disclosure@"}
SECURITY_TXT_PATH_MARKERS = (".well-known/security.txt", "security.txt")
CONTACT_FIELD_PATTERN = re.compile(r"contact\s*:", re.IGNORECASE)


def is_security_txt_hit(evidence_url: str) -> bool:
    if not isinstance(evidence_url, str):
        return False
    return any(marker in evidence_url.lower() for marker in SECURITY_TXT_PATH_MARKERS)


def looks_like_real_security_txt(evidence_snippet: str) -> bool:
    return bool(CONTACT_FIELD_PATTERN.search(str(evidence_snippet)))


def classify_row(row) -> str:
    if row.get("final_label_candidate") != 1:
        return "not_positive"

    hits = [h.strip() for h in str(row.get("disclosure_keywords_found", "")).split(";") if h.strip()]
    evidence_url = row.get("evidence_url", "")
    evidence_snippet = row.get("evidence_snippet", "")

    if is_security_txt_hit(evidence_url):
        if looks_like_real_security_txt(evidence_snippet):
            return "auto_accept_security_txt"
        else:
            return "needs_review_unconfirmed_security_txt"

    if any(h in STRONG_KEYWORDS for h in hits):
        return "auto_accept_strong_keyword"
    if any(h in TRUSTED_WEAK_KEYWORDS for h in hits):
        return "auto_accept_trusted_email"
    if "security@" in hits:
        return "needs_review_bare_security_email"
    return "auto_accept_other"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Split scraper positives into auto-accept vs. needs-manual-review."
    )
    parser.add_argument("results_csv", help="Path to a scraper output CSV.")
    return parser.parse_args()


def main():
    args = parse_args()
    df = pd.read_csv(args.results_csv)
    df["triage_status"] = df.apply(classify_row, axis=1)

    positives = df[df["final_label_candidate"] == 1]
    review_statuses = {"needs_review_bare_security_email", "needs_review_unconfirmed_security_txt"}
    needs_review = positives[positives["triage_status"].isin(review_statuses)]
    auto_accepted = positives[~positives["triage_status"].isin(review_statuses)]

    print(f"Total positives:        {len(positives)}")
    print(f"Auto-accepted:          {len(auto_accepted)}")
    print(f"Needs manual review:    {len(needs_review)}")
    print()
    print("Auto-accept breakdown:")
    print(auto_accepted["triage_status"].value_counts().to_string())
    print()
    print("Needs-review breakdown:")
    print(needs_review["triage_status"].value_counts().to_string())

    needs_review_path = args.results_csv.replace(".csv", "_NEEDS_REVIEW.csv")
    needs_review.to_csv(needs_review_path, index=False)
    print(f"\nSaved {len(needs_review)} row(s) needing manual review to: {needs_review_path}")


if __name__ == "__main__":
    main()
