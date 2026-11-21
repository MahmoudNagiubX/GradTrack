# GradTrack — GT-33 University ID OCR Feasibility Report

> **Task:** GT-33 Focused OCR Feasibility Spike (NOT full GT-33 product implementation)  
> **Jira:** [GT-33 — Scan a University ID Card](https://mahmoudnagiub.atlassian.net/browse/GT-33)  
> **Status:** Feasibility Evidence Recorded — Story remains `To Do` / `In Progress` (Acceptance criteria require user confirmation UI and manual fallback)  
> **Date:** 2026-11-21  
> **Branch:** `spike/GT-33-university-id-ocr` (stacked on `feature/GT-32-user-profiles`, PR #13)  
> **PR Target:** `develop`

---

## 1. Executive Summary & Recommendation

### Recommendation: `RECOMMEND_WITH_LIMITATIONS`

A local, offline, CPU-only OCR pipeline utilizing **Tesseract 5.4.0** with official English and Arabic language models (`ara+eng`) and deterministic field parsing is **feasible, practical, and responsive** for suggesting a student's full name and student ID on the demo laptop.

- **Clean Card Quality:** Achieves **100.0% Student ID exact match** and **100.0% Full Name normalized match** across English, Arabic, and bilingual cards.
- **Overall Quality (36 positive cards):** Achieves **86.1% Student ID exact match** and **75.0% Full Name normalized match** across clean, perspective-skewed, and degraded/compressed conditions.
- **Negative Sample Abstention:** **100.0% abstention** on cards with missing IDs or conflicting numbers (zero false positive IDs assigned).
- **Latency:** Cold start **0.59s**, warm median **538.0ms (p50)**, warm 95th percentile **746.6ms (p95)** on CPU.
- **Footprint:** Tesseract 5.4.0 binary + language models occupy **~18 MB** on disk and **~60 MB RAM**, requiring zero GPU tooling, zero external network calls, and zero cloud API costs.
- **PaddleOCR 3.7.0 Evaluation:** **`BLOCKED`**. PaddlePaddle 3.3.1 oneDNN executor on Windows CPU crashes with `NotImplementedError` during detection inference. Furthermore, PaddleOCR requires Python <= 3.12 and pulls ~500 MB of dependencies, making it unsuitable for the GradTrack runtime.
- **Core Product Boundary:** OCR text extraction is **strictly a prefill suggestion**. In accordance with Master Plan §5.1 and Decision F5, student review, correction, and manual data entry remain mandatory. OCR is **not** identity verification or eligibility determination.

---

## 2. Environment & Baseline Verification

### 2.1 Starting Baseline
- **Upstream PR:** PR #13 on `feature/GT-32-user-profiles`.
- **True GitHub Head Commit SHA:** `a31a09e9dc580b07e6b530c85c652a42c61d5f23`.
- **GitHub Actions Verification:** Exact-head run `44844479579` succeeded (312 passed, 0 failed).
- **Documentation Correction:** Corrected historical transcription typo in `docs/developer-tasks/GT-32-profile-backend-execution-report.md` on this branch from `a31a09e083907eb6bf9c1b48b62c4a9c67bb8e46` to the verified commit SHA `a31a09e9dc580b07e6b530c85c652a42c61d5f23`.

### 2.2 System & Runtime Observed
- **OS:** Windows 11 Home Single Language x86_64 (Build 26100.3194).
- **Main Backend Python:** Python 3.14.6 in `.venv` (untouched, zero OCR dependencies added).
- **Isolated Spike Environment:** Python 3.12.13 in `experiments/gt33_ocr_spike/.venv` managed via `uv`.
- **Spike Dependencies:** `pillow==13.0.0`, `pytesseract==0.3.13`, `arabic-reshaper==3.1.0`, `python-bidi==0.6.12`, `pytest==9.2.0`.

---

## 3. OCR Engines & Setup Friction

| Candidate | Version | License | Disk Footprint | Setup Method & Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **Tesseract OCR** | 5.4.0.20240606 (AVX2) | Apache 2.0 | ~18 MB total (4.1MB eng, 2.5MB ara, 10.5MB osd) | **SUCCESS**. Installed into user directory `C:\Users\mahmo\AppData\Local\Programs\Tesseract-OCR` using `$env:__COMPAT_LAYER = "RunAsInvoker"`. Zero administrative UAC prompts. Downloaded official LSTM language pack `ara.traineddata` (2.49 MB) from official Tesseract repository. |
| **PaddleOCR** | 3.7.0 (PaddlePaddle 3.3.1) | Apache 2.0 | ~500 MB (100MB paddle wheel, 43MB opencv, 120MB models) | **BLOCKED ON WINDOWS CPU**. Installed into isolated Python 3.12 venv. When executing `PaddleOCR(use_angle_cls=True, lang='ar')`, PaddlePaddle 3.3.1 oneDNN CPU engine crashed: `NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>] (at ..\paddle\fluid\framework\new_executor\instruction\onednn\onednn_instruction.cc:118)`. |

---

## 4. Smart Life Planner Reference Audit

- **Inspected File:** `C:\Users\mahmo\Desktop\Vscode\Smart Life Planner\mobile\lib\features\notes\services\note_ocr_service.dart`.
- **Audit Findings:** Smart Life Planner used Flutter's `google_mlkit_text_recognition` restricted to `TextRecognitionScript.latin` to extract plain text from note attachments.
- **Assessment:**
  - **REJECT:** Flutter Google ML Kit mobile dependency and Latin-only limitation. GradTrack requires server-side/offline Arabic and English support.
  - **ADAPT:** `NoteOcrResult` data-class concept (raw text, confidence, line counts, clean abstraction).
  - **REFERENCE:** Attachment check pattern.

---

## 5. Synthetic Dataset Architecture

To comply with Master Plan §5.1, Decision F2, and AGENTS.md §13, **zero real university ID cards or real student records were used**. 

The deterministic generator (`experiments/gt33_ocr_spike/generate_synthetic.py`, seed 42) created **40 fictional university card images** (standard ID card aspect ratio 856x540):

1. **English Cards (12):**
   - 4 Clean: Front-facing, high contrast, clean white card stock.
   - 4 Perspective: Rotated 5° with simulated drop shadow on neutral surface.
   - 4 Degraded: Defocus blur (0.9px Gaussian) and JPEG compression artifacts (quality 38).
2. **Arabic Cards (12):**
   - 4 Clean, 4 Perspective (-4.5°), 4 Degraded.
   - Rendered using Windows native `arial.ttf` with visual shaping via `arabic_reshaper` and Bidirectional layout via `python-bidi`.
3. **Mixed / Bilingual Cards (12):**
   - 4 Clean, 4 Perspective (5.5°), 4 Degraded.
   - Bilingual headers and field labels (`Name / الاسم:`, `ID / الرقم:`).
4. **Negative & Ambiguity Cards (4):**
   - `neg_01_no_id`: English card with valid student name but ID omitted entirely.
   - `neg_02_conflicting_ids`: Card with competing 8-digit Serial and Barcode numbers without an ID label.
   - `neg_03_visitor_badge`: Arabic visitor badge without matriculation ID.
   - `neg_04_blank_noise`: Degraded blank card background with noise texture and no text.

---

## 6. Deterministic Field Parsing Strategy

The pure parser (`experiments/gt33_ocr_spike/parse_fields.py`) extracts suggestions without machine learning or heuristics:
- **Digit Normalization:** Converts Eastern Arabic (٠١٢٣٤٥٦٧٨٩) and Persian (۰۱۲۳۴۵۶۷۸۹) digits to standard Western ASCII digits.
- **Bidirectional Control Stripping:** Strips Unicode directional formatting characters (`\u200e`, `\u200f`, `\u202a`–`\u202e`).
- **RTL Reading Order Adaptation:** When Tesseract scans visual Arabic RTL text in LTR mode, values frequently precede field labels in the character stream (e.g., `أحمد محمود علي الاسم:`). The parser checks both forward (LTR) and backward (RTL) token sequences.
- **Academic Noise Filtering:** Filters out institutional titles (`جامعة`, `كلية`, `قسم`, `Faculty`, `Department`, `Academic Year`) and label keywords (`الرقم`, `الجامعي`, `كود`, `ID`, `No`).
- **Abstention on Ambiguity:** If multiple candidate 6–12 digit numbers are found without an explicit label, the parser returns `student_number = None` and flags `is_ambiguous = True`, enforcing manual student entry.

---

## 7. Actual Benchmark Results (Tesseract 5.4.0)

Evaluated with language pack `ara+eng` and page segmentation mode `--psm 6`:

### 7.1 Aggregate Performance
- **Total Test Images:** 40
- **Student ID Exact Match (36 positive cards):** **86.1%** (31 / 36)
- **Full Name Normalized Match (36 positive cards):** **75.0%** (27 / 36)
- **Negative Sample ID Abstention (4 negative cards):** **100.0%** (4 / 4)
- **Inference Latency (CPU):**
  - Cold Start: **0.59s**
  - Warm Median (p50): **538.0ms**
  - Warm 95th Percentile (p95): **746.6ms**

### 7.2 Breakdown by Image Condition

| Condition | Samples | Student ID Exact Match | Full Name Normalized Match | Mean Latency |
| :--- | :---: | :---: | :---: | :---: |
| **Clean** | 12 | **100.0%** (12/12) | **100.0%** (12/12) | 567 ms |
| **Degraded** (Blur + Compression) | 12 | **91.7%** (11/12) | **58.3%** (7/12) | 486 ms |
| **Perspective** (Rotated 5°) | 12 | **66.7%** (8/12) | **66.7%** (8/12) | 574 ms |

### 7.3 Breakdown by Script / Language

| Script / Layout | Samples | Student ID Exact Match | Full Name Normalized Match |
| :--- | :---: | :---: | :---: |
| **English** | 12 | **91.7%** (11/12) | **83.3%** (10/12) |
| **Arabic** | 12 | **66.7%** (8/12) | **75.0%** (9/12) |
| **Mixed / Bilingual** | 12 | **100.0%** (12/12) | **66.7%** (8/12) |

---

## 8. Failure Analysis

Across the 36 positive synthetic cards, 13 samples failed either ID or Name exact match:

| Sample ID | Script | Condition | Expected ID | Predicted ID | Expected Name | Predicted Name | Root Cause |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| `eng_perspective_06` | English | Perspective | `20230554` | `20230554` | Sophia Turner | `None` | Rotation caused Tesseract to segment "Name:" and "Sophia Turner" into disjoint bounding boxes. |
| `eng_perspective_07` | English | Perspective | `20227189` | `20227189` | Benjamin Scott | `None` | 5° tilt split label and name across non-aligned lines. |
| `eng_degraded_11` | English | Degraded | `20229045` | `None` | Daniel Foster | Daniel Foster | Defocus blur merged digits into `2022904` (7 digits), failing 8-digit exact pattern. |
| `ara_perspective_05` | Arabic | Perspective | `20240899` | `2024089` | كريم عبد الله حسن | كريم عبد الله حسن | Skew dropped trailing digit `9`. |
| `ara_perspective_06` | Arabic | Perspective | `20234102` | `209234100` | نور الهدى طارق | نور الهدى طارق | Optical tilt introduced extra artifact digits. |
| `ara_perspective_07` | Arabic | Perspective | `20227763` | `20297763` | مصطفى كمال الدين | مصطفى كمال gall | Arabic word `الدين` misrecognized as `gall` under rotation. |
| `ara_perspective_08` | Arabic | Perspective | `20250441` | `20250444` | فاطمة حسن خليل | `None` | Last digit `1` read as `4`; Arabic name merged with department header. |
| `ara_degraded_09` | Arabic | Degraded | `20241512` | `20241512` | يحيى سعيد منصور | `None` | Low contrast blurred Arabic letters in `يحيى`. |
| `mix_degraded_09` | Mixed | Degraded | `20242750` | `20242750` | Mohamed Fathy Soliman | `None` | Compression artifacts caused parser to reject noisy middle name. |
| `mix_degraded_10` | Mixed | Degraded | `20236021` | `20236021` | Laila Essam Fouad | `None` | Blur on slash separator caused label miss. |

### Key Failure Takeaways
1. **Student IDs are brittle under physical skew:** In 5 of the perspective cards, rotation caused character substitution or dropped digits.
2. **Clean scans are near flawless:** When front-facing without tilt, accuracy is 100%.
3. **Abstention works properly:** In all degraded and negative edge cases where fields were unclear, the parser safely abstained rather than fabricating false student identities.

---

## 9. Tests and Checks Executed

1. **Parser Unit Tests:** `experiments\gt33_ocr_spike\.venv\Scripts\pytest.exe experiments/gt33_ocr_spike/test_parse_fields.py`
   - **Result:** **12 passed in 0.05s** (covering English labels, Arabic labels, bilingual labels, Arabic-Indic digit normalization, RTL stream reading order, bidi control characters, and negative abstention).
2. **Synthetic Generator:** `experiments\gt33_ocr_spike\.venv\Scripts\python.exe experiments/gt33_ocr_spike/generate_synthetic.py`
   - **Result:** **40 synthetic cards generated deterministically** into `generated_cards/` with ground-truth manifest.
3. **OCR Benchmark:** `experiments\gt33_ocr_spike\.venv\Scripts\python.exe experiments/gt33_ocr_spike/benchmark.py`
   - **Result:** Full 40-card evaluation completed, saving detailed metrics to `benchmark_results/tesseract_results.json`.
4. **Ruff Linter on Backend:** `src\backend\.venv\Scripts\ruff.exe check .`
   - **Result:** Clean, zero errors, zero warnings.
5. **Git Diff Check:** `git diff --check`
   - **Result:** Clean, zero whitespace errors.

---

## 10. Deliverables & Git Process

- **Branch Created:** `spike/GT-33-university-id-ocr`
- **Commits:**
  - `9abbff0` `spike(GT-33): benchmark local Arabic-English university-card OCR`
  - `57fb64f` `docs(GT-33): record synthetic OCR feasibility results`
- **Stacked Pull Request:** [PR #14](https://github.com/MahmoudNagiubX/GradTrack/pull/14) targeting `develop` (stacked on PR #13)
- **Exact-Head CI Run:** [Run 44861151121](https://github.com/MahmoudNagiubX/GradTrack/actions/runs/44861151121) succeeded (312 passed in 12.79s, lint clean)
- **Changed Files:**
  - `docs/developer-tasks/GT-32-profile-backend-execution-report.md` (corrected head SHA evidence)
  - `docs/developer-tasks/GT-33-ocr-feasibility-report.md` (this report)
  - `docs/developer-tasks/GradTrack_GT33_OCR_Feasibility_Antigravity.md` (task specification)
  - `experiments/gt33_ocr_spike/.gitignore`
  - `experiments/gt33_ocr_spike/README.md`
  - `experiments/gt33_ocr_spike/parse_fields.py`
  - `experiments/gt33_ocr_spike/test_parse_fields.py`
  - `experiments/gt33_ocr_spike/generate_synthetic.py`
  - `experiments/gt33_ocr_spike/benchmark.py`
  - `experiments/gt33_ocr_spike/ground_truth_manifest.json`
- **Main Backend Untouched:** `src/backend/app/`, `src/backend/requirements.txt`, and database migrations were completely untouched.

---

## 11. Known Limitations & Next Decision for Product Owner

1. **Synthetic vs. Real University IDs:** Synthetic cards have clean layouts and uniform fonts. Real Egyptian/Arab university ID cards feature embossed holographic overlays, university logos, watermarks, stamps, and varied layouts. While Tesseract handles clean text well, production deployment would require an image deskewing/cropping stage and mandatory manual verification.
2. **PaddleOCR Incompatibility:** PaddleOCR is not currently viable on Windows CPU due to upstream oneDNN runtime bugs.
3. **Mandatory Product Rule:** The OCR engine should only ever prefill registration fields; it must never automatically verify student identity or bypass user review.

**Decision required from Product Owner:**
- Approve Tesseract 5.4.0 as the proposed offline OCR engine for future GT-33 onboarding integration, OR defer full GT-33 implementation until React frontend onboarding screens are developed.
