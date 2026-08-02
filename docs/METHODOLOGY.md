# MIS 545 Group Project — Data Collection & Methodology Log

**Project:** Vendor Vulnerability Disclosure Prediction (Group 11)
**Research Question:** What public-facing business characteristics are associated with a software vendor publishing a security vulnerability disclosure or bug-bounty program?

This log records every data collection decision, bug found, and fix applied, with dates and rationale, so the process is fully reproducible and defensible for the extra-credit "unique/scraped dataset" requirement.

## Team Roles

| Name | Primary Responsibility |
|---|---|
| Ismail | Python web scraping, data collection, cybersecurity SME support; co-supports slide deck/presentation integration in later phases |
| Katrina | Building and evaluating the 4 R classification models |
| Enoch | Visualizations, dplyr queries, results interpretation |
| Ethan | Slide deck and presentation integration lead |

---

## Log Entry 1 — Sampling Frame Selection
**Date:** 2026-07-31 · **Performed by:** Ismail (with AI research assistance)

Selected the Y Combinator official public Startup Directory as the population source, accessed via `yc-oss/api` (a community-maintained open-source mirror of YC's public Algolia search index) at a static JSON endpoint — no HTML scraping, login, or access-control bypass involved. This is YC's own officially published, free public directory; the same data is visible on ycombinator.com/companies, and multiple independent third-party tools extract this identical dataset, confirming it as a low-risk, well-established source.

**Raw population retrieved:** 6,110 YC-funded companies (all industries, all batches, 2005-2027).

---

## Log Entry 2 — Filtering Criteria
**Date:** 2026-07-31 · **Performed by:** Ismail

Filtered the raw population to:
1. `industry == 'B2B'`
2. `status IN ('Active', 'Acquired', 'Public')` (excludes likely-defunct companies)
3. `website IS NOT NULL AND website != ''`

**Result:** 2,659 eligible B2B companies with valid websites and non-defunct status.

---

## Log Entry 3 — Stratified Sampling Design
**Date:** 2026-07-31 · **Performed by:** Ismail

Built a stratified sample instead of simple random sampling to avoid class imbalance in the dependent variable. A simple random sample would have been dominated by 2023-2027 batch companies (1,369 of 2,659), which are unlikely to have mature security-disclosure programs, risking a near-all-zero dependent variable.

**Method:**
- Oversampled Public/Acquired companies (n=80) as a deliberate class-balance measure
- Stratified the remainder proportionally across founding-year bands: 2005-2013 (39), 2014-2018 (54), 2019-2022 (106), 2023-2027 (147)
- Random seed fixed at 42 for reproducibility

**Final sample size:** 346 companies.

---

## Log Entry 4 — Field Construction
**Date:** 2026-07-31 · **Performed by:** Ismail

| Field | Type | Derivation |
|---|---|---|
| company_name | Identifier | Direct from YC data |
| website_domain | Identifier | Direct from YC data — scraper target |
| industry_segment | Categorical IV | Direct from YC data (all = 'B2B' by filter) |
| subindustry | Categorical IV | Direct from YC data |
| batch, founded_year_proxy | Continuous IV | Extracted from YC batch label (reflects YC cohort year, not necessarily incorporation year — documented limitation) |
| company_status | Categorical | Active / Acquired / Public |
| team_size_reported, company_size_band | Continuous/Categorical IV | Bucketed into 1-10, 11-50, 51-200, 200+ |
| is_public_company | Binary IV | 1 if company_status == 'Public', else 0 |
| regions, tags, one_liner | Context only | Retained for manual label-review context |

**Output file:** `Team_YC_Vendor_Sample_346.csv`

---

## Log Entry 5 — Labeling Rubric Finalized & Process Simplification
**Date:** 2026-08-01 · **Performed by:** Ismail

**Final rubric:**
- `1 (Yes)`: Vendor has a publicly identifiable vulnerability-disclosure policy, security.txt file, or approved bug-bounty program. Requires explicit language about vulnerability reporting, responsible disclosure, security researchers, security reports, or bug bounty — a generic "Contact Support" page does NOT qualify.
- `0 (No)`: No such policy found after checking the same fixed set of pages.
- `Exclude`: Site inaccessible, ambiguous, or blocks access.

**Fixed pages checked (initial):** `/.well-known/security.txt`, `/security`, `/security.txt`, `/trust`, `/trust-center`

---

## Log Entry 6 — Timeline & Effort Estimation
**Date:** 2026-07-31 · **Performed by:** Ismail

Estimated ~2-3 working days (Jul 31-Aug 6) for scraper build, full-scale run, manual validation, and human-in-the-loop labeling. Identified a key dependency risk: Katrina's and Enoch's workstreams are gated on Phase 4 preprocessing, itself gated on Ismail's finalized labeled CSV — any slippage cascades downstream.

---

## Log Entry 7 — Justification for Selected Check Paths
**Date:** 2026-08-01 · **Performed by:** Ismail (with AI research assistance)

1. **`/.well-known/security.txt`** — the standardized location per RFC 9116 (IETF, 2022), analogous to `robots.txt` (RFC 8615). CISA hosts its own security.txt here and recommends it as best practice.
2. **`/security.txt`** — RFC 9116 permits this domain-root fallback for cases where `/.well-known/` cannot be used.
3. **`/security`** — RFC 9116's own "Policy" field links out to a human-readable disclosure policy page, confirming this is a standard companion artifact.
4. **`/trust`** and **`/trust-center`** — not RFC-defined, but reflects observed B2B industry convention of consolidating compliance and disclosure info into a single "Trust Center."

**Supporting finding:** Only ~4% of Fortune 500 companies have implemented security.txt despite the standard existing since 2022 — directly informing the stratified sampling decision in Entry 3.

---

## Log Entry 8 — Supporting Empirical Research: Hexiosec security.txt Survey
**Date:** 2026-08-01 · **Performed by:** Ismail

Source: Naz Markuta, "1 Million Websites – How Many Use Security.txt?", Hexiosec (2022), independently cited by CISA.

| Population | security.txt adoption rate |
|---|---|
| Top 1M websites (Tranco) | 0.37% |
| Moz Top 500 | 15.4% |
| FTSE 100 (UK) | 5% |
| S&P 500 (US) | 3.6% |
| UK Banks (top 25) | 25% |
| Fortune 500 (secondary citation) | ~4% |

This validates the stratified sampling design (Entry 3) and provides an external benchmark for the final dataset's adoption rate. It also validates including HackerOne/Bugcrowd references in the rubric (310 and 40 sites respectively referenced these platforms in the study). Methodological lessons adopted: use a clearly identified, non-bot User-Agent (bot UAs triggered 403s in the study); expect redirect/HTML-parsing edge cases and www/non-www mismatches; manual review is required to catch false positives (the study itself manually invalidated a "found" security.txt with a non-functional contact).

---

## Log Entry 9 — Manual Validation Results & Rubric Refinement
**Date:** 2026-08-01 · **Performed by:** Ismail

**Before correction (25-company sample):** 5 positive (20%), 17 negative, 3 excluded.

This 20% rate was far above the Hexiosec benchmark (0.37-5%), prompting review. 4 of 5 positives were general security/compliance marketing pages (SOC 2, ISO 27001, pentest mentions) rather than genuine disclosure mechanisms. Only **Legora** had an actual RFC 9116-compliant security.txt with a dedicated disclosure contact.

**After correction:** 1 positive (4% — Legora only), 21 negative (84%), 3 excluded (12%) — closely matching the Hexiosec Fortune 500 benchmark (~4%), lending external validity.

**Rubric refinement added:** "Does NOT count as a 1: General security/trust pages referencing SOC 2, ISO 27001, encryption-at-rest, penetration testing, or compliance certifications as marketing/reassurance content, UNLESS they also include a specific mechanism for external parties to report a vulnerability (dedicated email, bug-bounty link, or security.txt file)."

**Key interpretive finding:** Many B2B vendors invest visibly in compliance signaling (SOC 2, ISO 27001, pentest badges) aimed at procurement reassurance, without maintaining an actual discoverable vulnerability-disclosure process — a maturity gap between perceived and actual security posture, usable as an original business-recommendation finding.

**Scraper design implications identified:** redirect handling with domain-change flagging; defunct-site detection beyond the status filter; domain-drift handling (companies migrating primary domains); trust centers sometimes hosted on separate subdomains.

---

## Log Entry 10 — Scraper Build & Initial Path/Keyword Expansion
**Date:** 2026-08-01 · **Performed by:** Ismail (with AI assistance)

Built `vendor_vuln_disclosure_scraper.py` implementing the Entry 5-9 rubric: checks configurable paths, follows redirects, strips HTML via BeautifulSoup, classifies against disclosure/compliance keyword lists, outputs an evidence-backed CSV (URL, HTTP status, matched keywords, evidence snippet, notes).

**Paths expanded 5 → 7:** added `/bug-bounty`, `/responsible-disclosure` (via Perplexity Deep Research). Deliberately excluded third-party platform slug-guessing and subdomain enumeration as too unreliable for project scope.

Established `requirements.txt`, `.gitignore`, and a local virtual environment ahead of the initial GitHub commit.

---

## Log Entry 11 — Bug Found: Trailing-"@" Regex Boundary Excluded Valid Emails
**Date:** 2026-08-01 · **Performed by:** Ismail

Ran the scraper against the 25-company validated set; only 1 of 4 known edge cases (Legora, Vooma, Collar, Apollo) was correctly flagged.

**Root cause:** the regex required a non-word character or end-of-string immediately after every keyword, including "@"-based keywords (`vulnerability-disclosure@`, `security@`). Since a real email continues immediately after "@", this silently broke every email-prefix match, including Legora's confirmed valid `Contact: mailto:vulnerability-disclosure@legora.com` field.

**Fix:** `build_regex()` omits the trailing boundary check specifically for keywords ending in "@".

---

## Log Entry 12 — Structured RFC 9116 Parsing Added
**Date:** 2026-08-01 · **Performed by:** Ismail (with AI assistance)

Added a dedicated `parse_security_txt()` function checking directly for the standardized `Contact:` and `Expires:` fields defined by RFC 9116, since security.txt is a structured format better validated by field presence than free-text keyword search. A file containing both fields is treated as a definitive positive.

---

## Log Entry 13 — Bug Found: Offsite Redirects Detected But Not Followed
**Date:** 2026-08-01 · **Performed by:** Ismail

Vooma (manually flagged 1) returned 0 despite a logged `OFFSITE_REDIRECT_DETECTED` note.

**Root cause:** Vooma migrated domains (vooma.ai → vooma.com). The scraper detected the redirect on the first path but kept probing remaining paths against the stale domain.

**Fix:** once an offsite redirect is confirmed, `base_domain_checked` updates to the new live domain for all subsequent paths. This also newly surfaced a genuine "bug bounty" match for NexTravel on its redirected domain (perk.com).

---

## Log Entry 14 — Path and Keyword List Expansion (Deep Research)
**Date:** 2026-08-01 · **Performed by:** Ismail (with Perplexity Deep Research)

**Paths expanded 7 → 16:** added self-hosted convention paths (`/vulnerability-disclosure-policy`, `/security-policy`, `/responsible-disclosure-policy`, `/coordinated-vulnerability-disclosure`, `/bug-bounty-program`) and nested paths (`/security/bug-bounty`, `/security/vulnerability-disclosure-policy`, `/security/report-a-vulnerability`, `/trust/report-a-vulnerability`), validated against a real-world precedent (Tenable's `/security/report`).

**Keywords expanded 16 → 27:** added standards-derived phrases (`vulnerability disclosure program`, `vulnerability disclosure policy`, `good faith security research`, `safe harbor`), `hall of fame`, CERT-style prefixes (`product-security@`, `cert@`, `csirt@`), and select third-party platforms (`synack`, `cobalt.io`, `immunefi`, `open bug bounty`).

**Deliberately excluded:** ISO/NIST internal process jargon unlikely to appear in vendor-facing text; niche bug-bounty platforms judged low-yield for this B2B SaaS population; non-HTTP-path signals (JSON descriptor guessing, Google dork syntax); subdomain enumeration, judged out of scope for a bounded, documented collection process.

Added a try/except wrapper around each per-company scrape so a single failure logs `SCRIPT_ERROR` and the run continues rather than crashing an unattended multi-hour execution.

---

## Log Entry 15 — Re-Validation Results (v3) on 25-Company Test Set
**Date:** 2026-08-01 · **Performed by:** Ismail

Candidate positives increased from 1 to 3 (Legora, Tire Swing, NexTravel) with zero regressions on previously-correct defunct/redirect flags. Legora's positive now comes from the RFC 9116 parser (Entry 12); Tire Swing's is a genuine catch from the expanded keyword list (Entry 14) via a "Vulnerability Disclosure Policy" footer link. Apollo and Collar remain correctly labeled 0, consistent with the Entry 9 rubric refinement.

**Runtime:** 25-company test completed in 9 minutes (~22 sec/company across 16 paths). Full 346-company run estimated 2-2.5 hours, planned for unattended overnight execution.

---

## Log Entry 16 — Full-Scale Run Review & Weak-Keyword Refinement
**Date:** 2026-08-02 · **Performed by:** Ismail (with AI assistance)

Ran the scraper against the full 346-company sample and manually reviewed all candidate positives. Found 4 false positives (Aden, Chargehound, Fogbender, Jasper.ai), 3 of which were triggered purely by a bare `security@` contact address in generic "email us with questions" boilerplate with no real disclosure process described.

**Fix applied:** split the keyword list into two tiers:
- **Strong keywords** (`bug bounty`, `hackerone`, `responsible disclosure`, `safe harbor`, etc.) still qualify a page as a positive on their own.
- **Weak keywords** (`security@`, `vulnerability-disclosure@`) now only qualify if disclosure-related language (`vulnerab`, `disclos`, `report a`, `bug bounty`, `pgp`, etc.) appears within a 150-character window of the match.

Re-checked against the review sheet: Chargehound, Fogbender, and Jasper.ai correctly flip to 0 under the new logic; confirmed true positives (Artillery, Docker) remain 1 since their `security@` mentions sit directly next to disclosure language ("security bugs... reported by email", a linked disclosure policy). Aden's false positive was driven by the strong keyword "responsible disclosure" appearing as a bare navigation/feature label rather than real policy prose — a known, documented limitation not addressed by this fix, since further tightening strong-keyword matching risks new false negatives elsewhere. Also added `/whitehat` to the checked path list based on evidence found in this review round.

---

## AI Assistance Disclosure

Per the course syllabus's generative AI policy, AI tools (Perplexity) were used to assist with research, data-source identification, sampling logic design, scraper debugging, and documentation drafting throughout the data collection phase. All labeling decisions were manually reviewed against the documented rubric by the team.

## Extra-Credit Justification Summary

This dataset is not a pre-existing, downloadable CSV. It was independently constructed through: (1) retrieval of raw public company records via YC's public data index, (2) custom filtering and stratified resampling logic designed specifically for this research question, (3) original field derivation and renaming, and (4) original manual and scripted labeling of the binary dependent variable via direct website inspection. No dataset combining these specific YC companies with vulnerability-disclosure labels exists publicly prior to this project.
