"""
MIS 545 Group Project — Results Stats Checker
Author: Ismail (with AI assistance)
Purpose: Quick summary statistics for a scraper output CSV, so results can be
sanity-checked against the Hexiosec adoption-rate benchmark (Log Entry 8)
before moving on to human-in-the-loop review.

Usage:
    python scraper/check_stats.py data/Team_YC_Vendor_Sample_346_RESULTSv2.csv
"""

import argparse
import pandas as pd
from collections import Counter


def parse_args():
    parser = argparse.ArgumentParser(
        description="Print summary statistics for a vendor_vuln_disclosure_scraper.py output CSV."
    )
    parser.add_argument("results_csv", help="Path to a scraper output CSV.")
    return parser.parse_args()


def top_keywords(series, n=10):
    counter = Counter()
    for cell in series.dropna():
        if not cell:
            continue
        for kw in str(cell).split(";"):
            kw = kw.strip()
            if kw:
                counter[kw] += 1
    return counter.most_common(n)


def main():
    args = parse_args()
    df = pd.read_csv(args.results_csv)
    total = len(df)

    reachable = df["site_reachable"].sum() if "site_reachable" in df else None
    positives = df["final_label_candidate"].sum() if "final_label_candidate" in df else None
    redirects = df["any_redirect_offsite"].sum() if "any_redirect_offsite" in df else None
    compliance_only = (
        df["compliance_only_keywords_found"].fillna("").astype(bool).sum()
        if "compliance_only_keywords_found" in df else None
    )

    print(f"Total companies:        {total}")
    if reachable is not None:
        print(f"Reachable sites:        {reachable} ({reachable/total:.1%})")
        print(f"Unreachable/defunct:    {total - reachable} ({(total-reachable)/total:.1%})")
    if positives is not None:
        print(f"Candidate positives:    {positives} ({positives/total:.1%})")
    if redirects is not None:
        print(f"Offsite redirects seen: {redirects} ({redirects/total:.1%})")
    if compliance_only is not None:
        print(f"Compliance-only pages:  {compliance_only} ({compliance_only/total:.1%})  "
              f"(security/compliance content found, but no disclosure mechanism)")

    print("\nHexiosec benchmark reference (Log Entry 8): "
          "S&P 500 ~3.6%, FTSE 100 ~5%, Fortune 500 ~4%, top-1M sites ~0.37%.")

    if "disclosure_keywords_found" in df:
        print("\nTop disclosure keywords matched:")
        for kw, count in top_keywords(df["disclosure_keywords_found"]):
            print(f"  {kw}: {count}")

    if "notes" in df:
        flagged = df[df["notes"].fillna("") != ""]
        if len(flagged):
            print(f"\n{len(flagged)} companies flagged with notes (unreachable, redirects, HTTP fallback). "
                  f"See the 'notes' column for details on each.")


if __name__ == "__main__":
    main()
