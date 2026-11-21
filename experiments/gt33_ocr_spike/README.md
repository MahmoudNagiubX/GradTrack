# GT-33 University ID OCR Feasibility Spike

This directory contains the experimental code, synthetic generator, parsing logic, and benchmark suite for the **GT-33 University ID OCR Feasibility Spike**.

> **Note:** This spike is an offline feasibility evaluation only. It does **not** introduce persistent database models, FastAPI endpoints, or UI screens to GradTrack. It processes **100% synthetic, fictional university cards** and never uses real student records.

---

## 1. Directory Structure

```text
experiments/gt33_ocr_spike/
├── .gitignore                    # Excludes .venv, generated images, and result dumps
├── README.md                     # Reproducible setup, instructions, and candidate findings
├── parse_fields.py               # Pure deterministic text parsing and Arabic/Latin normalization
├── test_parse_fields.py          # Fast pytest unit tests for parser logic and abstention
├── generate_synthetic.py         # Deterministic synthetic ID card generator (40 cards)
├── benchmark.py                  # Benchmark script for Tesseract 5.4.0 (and candidate evaluation)
└── ground_truth_manifest.json    # Deterministic metadata and labels for synthetic cards
```

---

## 2. Environment Setup

### Prerequisites
- Windows 11 x86_64
- CPython 3.12 (isolated virtualenv managed by `uv`)
- Tesseract OCR 5.4.0 (`tesseract.exe`) installed in user directory:
  `C:\Users\mahmo\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`
- Tesseract language data: `eng.traineddata` (4.1 MB) and `ara.traineddata` (2.5 MB) in `tessdata/`

### Virtual Environment & Dependencies
```powershell
# Create isolated Python 3.12 virtual environment
uv venv experiments/gt33_ocr_spike/.venv --python 3.12

# Install lightweight spike dependencies
uv pip install --python experiments/gt33_ocr_spike/.venv/Scripts/python.exe pillow pytesseract arabic-reshaper python-bidi pytest
```

---

## 3. Running the Spike

### Step 1: Run Parser Unit Tests
```powershell
experiments\gt33_ocr_spike\.venv\Scripts\pytest.exe experiments/gt33_ocr_spike/test_parse_fields.py
```

### Step 2: Generate Synthetic ID Cards
```powershell
experiments\gt33_ocr_spike\.venv\Scripts\python.exe experiments/gt33_ocr_spike/generate_synthetic.py
```
This deterministically generates 40 cards into `generated_cards/`:
- 12 English cards (4 clean, 4 perspective, 4 degraded)
- 12 Arabic cards (4 clean, 4 perspective, 4 degraded)
- 12 Mixed/Bilingual cards (4 clean, 4 perspective, 4 degraded)
- 4 Negative/Ambiguity cards (missing ID, conflicting numbers, visitor badge, blank noise)

### Step 3: Run the Benchmark
```powershell
experiments\gt33_ocr_spike\.venv\Scripts\python.exe experiments/gt33_ocr_spike/benchmark.py
```
This evaluates Tesseract 5.4.0 (`ara+eng`, `--psm 6`), measures latency (cold start, warm p50, warm p95), accuracy per condition and script, and outputs formatted results.
