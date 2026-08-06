# Vendor Vulnerability Disclosure Prediction

Academic data collection pipeline built for a Data Mining & Machine Learning group project. This repository contains the web scraper, methodology documentation, and data collection logic used to build an original dataset for predicting whether B2B SaaS vendors publish a public vulnerability disclosure program.

## Overview

The project samples B2B companies from the Y Combinator Startup Directory, then checks each company's website for evidence of a genuine vulnerability-disclosure mechanism (a `security.txt` file, a dedicated security/trust page, or a bug-bounty program), rather than relying on generic security/compliance marketing content. See `docs/METHODOLOGY.md` for the full, dated log of every sampling, labeling, and scraper design decision.

## Repository Structure

```
.
├── docs/
│   └── METHODOLOGY.md          # Full data collection & methodology log
├── scraper/
│   ├── vendor_vuln_disclosure_scraper.py   # Main scraper
│   ├── triage_positives.py                 # Post-hoc triage helper for results CSVs
│   └── check_stats.py                      # Quick summary stats for a results CSV
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.9 or later
- pip (bundled with Python)
- A working internet connection (the scraper makes live HTTP requests to each target domain)

**If you don't already have Python installed:**

- **macOS:** Install [Homebrew](https://brew.sh) first if you don't have it, then run:
  ```
  brew install python
  ```
  This installs a current Python 3 alongside pip. Verify with `python3 --version`.
- **Windows:** Download the installer from [python.org/downloads](https://www.python.org/downloads/) and make sure to check "Add python.exe to PATH" during setup. Alternatively, install via `winget install Python.Python.3.12`.
- **Linux (Debian/Ubuntu):**
  ```
  sudo apt update && sudo apt install python3 python3-pip python3-venv
  ```
- **Linux (Fedora):**
  ```
  sudo dnf install python3 python3-pip
  ```

On macOS and Linux, the Python 3 binary is typically invoked as `python3` (not `python`) unless you've aliased it.

## Setup

1. Clone the repository.
2. Create and activate a virtual environment (recommended):
   ```
   python3 -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate      # Windows
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

**Run the scraper** against a CSV containing `company_name` and `website_domain` columns:
```
python scraper/vendor_vuln_disclosure_scraper.py input_file.csv
```
This auto-generates `input_file_RESULTS.csv`. Use `-o` to specify a custom output filename.

**Triage the results** to separate trustworthy positives from the small number that still need manual review:
```
python scraper/triage_positives.py input_file_RESULTS.csv
```
This saves a `*_NEEDS_REVIEW.csv` file containing only the rows that warrant a human look.

**Check summary stats** for a results CSV:
```
python scraper/check_stats.py input_file_RESULTS.csv
```

## Methodology

Every sampling decision, labeling rubric change, bug fix, and re-validation run is documented with dates and rationale in `docs/METHODOLOGY.md`. This is the authoritative record of how the dataset was built.

## AI Assistance Disclosure

AI tools (Perplexity) were used to assist with research, data-source identification, sampling logic design, scraper development and debugging, and documentation drafting throughout the data collection phase.
