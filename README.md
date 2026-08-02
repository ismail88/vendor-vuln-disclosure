# Vendor Vulnerability Disclosure Prediction

Academic data collection pipeline built for an MIS 545 (Data Mining & Machine Learning) group project. This repository contains the web scraper, methodology documentation, and data collection logic used to build an original dataset for predicting whether B2B SaaS vendors publish a public vulnerability disclosure program.

## Research question

What public-facing business characteristics are associated with a software vendor publishing a security vulnerability disclosure or bug-bounty program?

The binary dependent variable, `has_vulnerability_disclosure`, is set to `1` when a vendor has a publicly identifiable vulnerability-disclosure policy, `security.txt` file, or approved bug-bounty program, and `0` otherwise, following a documented, repeatable rubric (see `docs/METHODOLOGY.md`).

## What this scraper does

`scraper/vendor_vuln_disclosure_scraper.py` checks each company's website against a fixed set of common disclosure-related paths (e.g. `/.well-known/security.txt`, `/security`, `/trust-center`, `/bug-bounty`), follows redirects, strips visible text with BeautifulSoup, and classifies matches against a tiered keyword list:

- **Strong keywords** (e.g. `bug bounty`, `hackerone`, `responsible disclosure`, `safe harbor`) qualify a page as a positive on their own.
- **Weak keywords** (bare `security@` / `vulnerability-disclosure@` contacts) only qualify if genuine disclosure language appears within a 150-character window of the match, to avoid false positives from generic "email us" contact footers.
- **Compliance-only keywords** (`SOC 2`, `ISO 27001`, `penetration testing`, etc.) are tracked separately and never count as a disclosure positive on their own, since they signal security marketing, not an actual reporting channel.

It also includes structured RFC 9116 parsing for `security.txt` files (checking for `Contact:` / `Expires:` fields directly), automatic HTTP fallback on SSL errors, offsite-redirect handling that updates the base domain mid-scan, and per-company error isolation so a single failure doesn't crash a multi-hour unattended run.

Every design decision, bug found, and fix applied is documented with dates and rationale in `docs/METHODOLOGY.md` (Log Entries 1-16).

## Setup

```bash
git clone https://github.com/ismail88/vendor-vuln-disclosure.git
cd vendor-vuln-disclosure
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

## Usage

The input CSV must contain `company_name` and `website_domain` columns.

```bash
# Auto-generates output filename (input_file_RESULTS.csv)
python scraper/vendor_vuln_disclosure_scraper.py data/Team_YC_Vendor_Sample_346.csv

# Specify a custom output filename
python scraper/vendor_vuln_disclosure_scraper.py data/Team_YC_Vendor_Sample_346.csv -o data/my_results.csv

# Help
python scraper/vendor_vuln_disclosure_scraper.py -h
```

## Repository structure

```
vendor-vuln-disclosure/
├── README.md
├── requirements.txt
├── .gitignore
├── scraper/
│   └── vendor_vuln_disclosure_scraper.py
├── docs/
│   └── METHODOLOGY.md          # Full data collection & decision log (Entries 1-16)
└── data/                       # Added locally
    ├── Manual_Validated_URLs_25.csv
    ├── Team_YC_Vendor_Sample_346_RESULTS.csv
    └── review_sheet_346.csv
```

## Data source & sampling

The sampling frame is the Y Combinator public Startup Directory (accessed via the community-maintained `yc-oss/api` static JSON mirror), filtered to active/acquired/public B2B companies with valid websites, then stratified across founding-year bands and oversampled for Public/Acquired status to avoid a near-all-zero dependent variable. Full rationale is in `docs/METHODOLOGY.md`, Log Entries 1-3.


## AI assistance disclosure

Per the course's generative AI policy, Perplexity was used to assist with research, data-source identification, sampling logic design, scraper debugging, and documentation drafting throughout the data collection phase. All labeling decisions were manually reviewed against the documented rubric.
