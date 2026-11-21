# GradTrack — GT-33 University ID OCR Feasibility Spike

**Antigravity CLI task specification | User-selected Flash 3.8 High**  
**Prepared:** 2026-11-21  
**Repository:** https://github.com/MahmoudNagiubX/GradTrack  
**Jira:** [GT-33 — Scan a University ID Card](https://mahmoudnagiub.atlassian.net/browse/GT-33)  
**Work type:** Focused, experimental feasibility spike — **NOT** full GT-33 product implementation.  
**Environment:** User's Windows 11 laptop; GradTrack FastAPI + PostgreSQL 16 + private local file storage; no cloud required.

## 1. Objective and acceptance context

Determine whether a **local/offline, Arabic- and English-capable OCR solution** is practical for suggesting a **full name** and **student/university ID number** from a *synthetic university-ID-like image*, suitable for a later student-confirmation screen. Benchmark OCR quality, extraction reliability, CPU latency, install/maintenance burden, and compatibility on the actual demo laptop.

The actual Jira GT-33 acceptance criteria for the **future complete feature** are:

1. A scan suggests name and student number.
2. The student can correct extracted text before saving.
3. Manual entry is always available.
4. Tests use synthetic ID cards, never real student records.

**The spike does not satisfy all four story criteria**, because it deliberately does not build onboarding UI or a public API. Record its status as feasibility evidence, not `Done` or a fully implemented GT-33.

### Current verified repository baseline (refresh immediately before starting)

- GT-32 Profile Management: open stacked [PR #13](https://github.com/MahmoudNagiubX/GradTrack/pull/13), branch `feature/GT-32-user-profiles`, **real GitHub head `a31a09e9dc580b07e6b530c85c652a42c61d5f23`**.
- Exact-head [GitHub Actions run 44844479579](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44844479579) succeeded on that actual commit. GT-32 execution report states 312 passing tests in CI, 311 passed and one skipped locally.
- **Documentation correction required:** The pasted Antigravity GT-32 summary mistakenly gave `a31a09e083907eb6bf9c1b48b62c4a9c67bb8e46`; this is **not** the actual GitHub head. Verify the source and correct only the false evidence if present in committed documents.
- PRs **#2–#13 remain unmerged** as last observed. Human review and merge remain required, but were deferred by the Product Owner. Do not touch `main`, `develop`, or any existing PR branches except an explicitly authorized documentation-only correction.
- `src/backend/app/models.py::User` now includes self-reported `student_number`, `faculty`, `department`, `academic_level`, plus avatar support. `GET/PATCH /auth/me` and avatar routes exist. **No OCR endpoint, OCR trained model or OCR dependency exists yet.**
- `src/backend/requirements.txt` has no OCR runtime dependencies. Do not add large packages to the main runtime before proving the approach.
- Local PostgreSQL and the full prior HTTP demo reportedly pass on the user's laptop; OCR spike should not change existing database/API behavior.

## 2. Read sources first

1. Root `AGENTS.md`, Master Plan §5.1 (OCR onboarding, privacy, editable suggestions, Arabic/English support), Priority 3, and Jira GT-33.
2. `docs/developer-tasks/GradTrack_Backend_Advanced_Features_Roadmap_Antigravity.md`, GT-32 spec/report and current `app.models`, `app.schemas`, `app.auth`, and any image/storage logic directly relevant to integration planning.
3. Relevant read-only parts of `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner` for OCR or image preprocessing if present; report **REUSE / ADAPT / REFERENCE / REJECT** honestly, and never copy unrelated auth, storage or database implementations.
4. Official OCR documents; check installed versions and actual hardware, not assumed compatibility:
   - Tesseract: https://tesseract-ocr.github.io/tessdoc/Installation.html (`eng` and `ara` traineddata).
   - Tesseract language data: https://github.com/tesseract-ocr/tessdata
   - PaddleOCR multilingual support: https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html
   - PaddleOCR pipeline: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
   - Optional fallback EasyOCR: https://github.com/JaidedAI/EasyOCR (Windows PyTorch setup can be significant).

## 3. Proposed decisions — only effective after explicit PO approval

**F1 — Offline-only inference for the demo.** All images and recognized text are processed on the laptop. A one-time *official* language/model download is acceptable **only after reporting model origin/size, installed dependencies and compatibility**; don't require paid API keys or a cloud OCR endpoint. No images or IDs sent to external services.

**F2 — Synthetic data only.** Generate fictitious **Arabic, English and bilingual** university-ID-like cards with clearly fictional names/IDs and generic school branding. Never use real student records, real university ID scans or copied logos/watermarks. Don't store real uploaded IDs. Generated assets may be produced under an ignored temporary directory; avoid committing binary test photos unless explicitly necessary and approved.

**F3 — Two fields, nothing more.** Extract *suggestions* for `full_name` and `student_number`; optional raw detected text and confidence indicators. No face matching, barcode validation, faculty/level inference, eligibility verification, official identity claims, or automatic privileged-role assignment. OCR is **not** identity verification.

**F4 — Compare lightweight baseline first.** Start with Tesseract 5 + English/Arabic language packs if available/installable, using either CLI/subprocess or a lightweight interface. Measure actual outcomes. Evaluate **one** additional candidate (prefer PaddleOCR Arabic-capable recognition) *only if it runs locally within the existing demo constraints without destabilizing the backend*. Do not silently install gigabytes of packages or GPU tooling. If installing Tesseract or a second engine requires manual/system-wide changes, describe them and request user action/approval.

**F5 — Manual confirmation is mandatory in the later integration.** OCR output is prefill-only. Missing/ambiguous name or ID must return uncertainty and permit manual correction, not fabricate values or save automatically. This spike may demonstrate editing of returned suggestions in a small local CLI, **not** a React/Flutter screen.

**F6 — No invasive backend edits in the spike.** No new OCR FastAPI routes, Alembic migrations, User model changes, persistent ID-image fields, OCR file-storage pipeline, registration redesign, fake auth flow, React/Flutter, queues, cloud services, or production rate-limit platform. Keep experimental packages outside the main backend virtual environment if compatibility requires it.

**F7 — Data-driven decision gate.** Choose a proposed integration approach based on observed name/number accuracy, false positives, failure modes, latency, install burden and robustness under synthetic degradations. Report a `RECOMMEND`, `RECOMMEND_WITH_LIMITATIONS`, or `NOT_READY` conclusion; the **human PO** makes the actual engine/integration decision later. Never claim synthetic-test accuracy generalizes to actual university IDs.

## 4. Execution scope and deliverables

### 4.1 Environment check first

- Record current repo branch/head, `git status`, `python --version`, available CPUs/RAM, whether the demo GPU exists (optional), Tesseract path/version and installed `eng`/`ara` packs, and relevant installed OCR/image libraries.
- Observe whether `Python 3.14.6` is supported by a candidate on Windows. If not, make an **isolated** Python 3.12 experiment environment **only with approval** or report as blocked; do not downgrade/replace the working backend virtual environment.
- Do not modify Windows-wide PATH, PostgreSQL service, existing `.venv`, system registry, auth secrets, or firewall without explicit user permission.
- Write reproducible setup instructions with actual commands and measured dependency sizes where observable. Don't list hypothetical successful installations as facts.

### 4.2 Synthetic corpus

- Create a repeatable generator (prefer a short script and a seeded random sample), or a curated set that can be regenerated, with **at least 36 synthetic cards**, balanced between:
  - English-only field labels/names.
  - Arabic-only field labels/names.
  - Mixed Arabic/English layouts, digits, names and field labels.
- Include 3 image conditions when possible: clean/front-facing, modest rotation/perspective, and mild blur/low-light/compression. Keep cases realistic but do not use actual university templates or images.
- Ground-truth manifest contains only `sample_id`, `language/layout`, original `expected_full_name`, `expected_student_number`, and image-condition metadata. Use clearly fictional identifiers; avoid actual-looking personal secrets.
- Generate using system-installed fonts for Arabic and Latin; verify Arabic is **visually shaped/right-to-left and actually readable**. If a suitable Arabic text renderer is unavailable, report the blocker instead of counting broken glyphs as genuine Arabic test samples. Do not package or distribute font files.
- Add a few deliberate ambiguity/absence cases (no student ID or conflicting numbers) as **separate** negative tests, not disguised inside the regular accuracy denominator.
- If the expected generator needs Pillow or image tooling not already present, keep the addition isolated to a small spike-only environment, not default `src/backend/requirements.txt`.

### 4.3 OCR experiment

- Benchmark Tesseract with verified local language packs; record command/configuration, version and optional preprocessing attempts (crop, grayscale, contrast, deskew) only if they improve measured results. Don't optimize on the same sample without noting it.
- Extract the **name and student number** from the raw OCR output using transparent, deterministic parsing of field labels (e.g., `Name`, `Student ID`, `الاسم`, `الرقم الجامعي`) and a constrained ID-number format appropriate to fictional test data. Explicitly return missing/ambiguous fields as `null`.
- Normalize comparisons carefully: strip extraneous whitespace; normalize Unicode composition, and optionally Arabic diacritics/alef forms for **evaluation only**; normalize Arabic-Indic and Western digits. Keep raw predicted text alongside normalized text for audit.
- If a second engine is feasible, benchmark the same corpus and report its model size, cold start, average/p50/p95 CPU latency, approximate peak memory where measurable, and errors. If its runtime/download footprint is excessive, document and **skip**, rather than block the whole project.
- Collect an honest per-sample CSV/JSON report and separate aggregate tables for English, Arabic, mixed and each image condition. Do not invent successful predictions.

### 4.4 Metrics and review

At minimum report:

1. **Student number exact-match accuracy**: correct predictions / all samples with a number, split by language/condition; no partial-credit number matching.
2. **Normalized full-name exact match** or transparently defined similarity metric; show both field-extraction rate and exact-match rate. Do not claim a near-correct name is a verified identity.
3. **False positives / abstention** on missing/conflicting field samples.
4. **Latency per image**: cold initialization separately from warm-run p50 and p95, with clearly stated hardware and CPU/GPU mode.
5. **Install cost**: approximate disk/model footprint, dependencies, model licenses and Windows-specific friction, with evidence.
6. **Failure examples**: at least five representative cases when possible; discuss handwritten names, glare, skew, mixed scripts and inaccurate labels without claiming they were fully tested if they were not.

Practical **discussion** targets, not guaranteed acceptance criteria: clean student-number exact match around 90% or better, clean normalized-name match around 80% or better, and acceptable single-image latency for a local demo. Below-target results do not imply fake success; recommend narrower supported conditions or manual fallback. A sample set of 36+ synthetic images is **not** evidence for deployment to real university IDs.

### 4.5 Project-safe implementation structure

Preferred small footprint (adapt if repository conventions differ):

```text
experiments/gt33_ocr_spike/
  README.md                  # reproducible local commands and candidate versions
  generate_synthetic.py      # deterministic fictional card generation
  benchmark.py               # invokes candidate(s) and writes metrics
  parse_fields.py            # pure deterministic text parsing / normalization
  test_parse_fields.py       # small tests, no OCR model required
  .gitignore                 # excludes generated images, caches, model weights and outputs

docs/developer-tasks/
  GT-33-ocr-feasibility-report.md  # sole persistent decision/evidence report
```

Do **not** add a framework, persistent OCR service or many redundant adapters for a one-off experiment. Reuse simple scripts when sufficient. Generated cards/test results may be copied into the written report as a **small number of synthetic** reference examples; keep raw datasets/models ignored by default. Worktree/commit contents must be reviewed before push.

### 4.6 Tests and verification

- Field parser unit tests: Arabic and English labels, extra spaces, Arabic-Indic/Western digits, missing label, ambiguous student numbers, blank/invalid inputs; assert abstention rather than guessing.
- Corpus manifest generation deterministic from seed; assert there are no real identifiers, the sample set is balanced, and Arabic glyph display is usable.
- OCR benchmark runs locally and outputs actual counts/runtimes. If a candidate is blocked, record **BLOCKED**, commands attempted and error rather than inventing scores.
- Preserve all existing backend phases. If application source is untouched, **do not pretend OCR has passed the full backend test suite**; exact-head CI may still be run to validate no regression.
- Run `git diff --check`, focused parser/corpus tests and relevant backend tests; record actual results and links. A successful GT-33 spike **does not** mark Jira GT-33 Done.

## 5. Git/Jira process and stop boundary

1. Verify current `develop`/feature PR status before new work. If PRs remain unmerged, the PO specifically authorizes a **new stacked experiment branch from the verified GT-32 PR #13 head**; suggested `spike/GT-33-university-id-ocr`. If integration occurred meanwhile, follow the repository branch rules instead. Preserve all uncommitted user changes.
2. Commit only useful scripts/tests/docs for the spike using honest conventional-style messages such as `spike(GT-33): benchmark local Arabic-English university-card OCR` and `docs(GT-33): record synthetic OCR feasibility results`.
3. Push your new branch and open a **stacked PR to `develop`** (per existing project PR convention). Include real hardware, versions, test counts, benchmark outputs and limitations. Do not merge.
4. Put a factual evidence comment on Jira GT-33 if the spike was executed. **Leave the story `To Do`/`In Progress`**, not `In Review` as a full product feature and never `Done`, because the acceptance criteria require actual OCR-suggested registration with correction/manual fallback.
5. Correct the GT-32 SHA documentation error **only if the committed file contains it** and if the fix will not overwrite unrelated work. The original GT-32 PR was already submitted; avoid rewriting its history. Add a factual clarification in the GT-33 report if more appropriate.
6. **STOP after the spike report and PR.** Do not automatically implement the full GT-33 API/onboarding flow, start GT-34, add Google/email auth, or make unapproved hardware/architecture decisions.

## 6. Required Antigravity execution report

```text
Task: GT-33 OCR feasibility spike (NOT full GT-33)
Actual starting branch/head, working tree state, PR stack:
Windows/Python/hardware observed:
OCR engines checked, version/language packs/license:
Install attempts and any manual permissions required:
Smart Life Planner audit (if OCR-related code exists):
Synthetic corpus count, languages/layouts/conditions, ground truth strategy:
Actual benchmark metrics by language and image condition:
Fields parsed, uncertainty/abstention behavior, failure examples:
Warm/cold latency, memory where measured, model/disk footprint:
Tests/checks actually executed, counts and outcomes:
Changed files, exact commits, PR URL, exact CI head/run:
Recommendation: RECOMMEND / RECOMMEND_WITH_LIMITATIONS / NOT_READY
Known limitations and next decision required from PO:
GT-33 story status unchanged; no merge, no main/backend/frontend integration:
```

## 7. Ready-to-paste Antigravity startup prompt

> Read root `AGENTS.md`, the Master Plan §5.1, Jira GT-33, `docs/developer-tasks/GradTrack_Backend_Advanced_Features_Roadmap_Antigravity.md`, and `docs/developer-tasks/GradTrack_GT33_OCR_Feasibility_Antigravity.md` completely. I approve **F1–F7** and authorize a **GT-33 synthetic university-ID OCR feasibility spike only**. Verify PR #13 actual head and CI, then create a new stacked experiment branch if earlier PRs are unmerged. Compare Tesseract Arabic+English baseline with one second local candidate only if setup is feasible; do not install global software or heavy dependencies without approval. Generate fictional English, Arabic and mixed ID-like examples and record actual OCR/extraction accuracy, false positives, latency, installation burden and failure cases. Preserve all FastAPI/PostgreSQL APIs, avoid real ID images and cloud OCR, and do not claim identity verification. Run focused tests and relevant CI, open a stacked PR, produce a factual feasibility report, then STOP. Do not build GT-33 final onboarding yet, do not mark Jira GT-33 Done, do not merge PRs or start frontend/GT-34 work.
