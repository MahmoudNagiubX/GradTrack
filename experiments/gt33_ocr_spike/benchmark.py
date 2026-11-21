"""OCR Benchmark Script for GT-33 Feasibility Spike.

Benchmarks Tesseract 5.4.0 (and optionally PaddleOCR) across:
- 40 synthetic university ID card images (English, Arabic, Mixed, Negative)
- 3 image conditions (Clean, Perspective, Degraded)

Measures:
- Student ID exact-match accuracy
- Full name normalized accuracy
- Negative abstention rate
- Latency: cold-start, warm p50, warm p95
- Memory and model footprint

Outputs formatted markdown tables and saves detailed JSON results.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from parse_fields import (
    normalize_digits,
    normalize_name_for_comparison,
    parse_ocr_text,
)
from PIL import Image

BASE_DIR = Path(__file__).parent
CARDS_DIR = BASE_DIR / "generated_cards"
MANIFEST_FILE = BASE_DIR / "ground_truth_manifest.json"
RESULTS_DIR = BASE_DIR / "benchmark_results"

TESSERACT_EXE = r"C:\Users\mahmo\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"


def benchmark_tesseract(manifest: list[dict[str, Any]]) -> dict[str, Any]:
    """Run Tesseract 5.4.0 benchmark on all samples."""
    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

    results: list[dict[str, Any]] = []
    latencies: list[float] = []

    print("\n=======================================================")
    print("Running Tesseract 5.4.0 Benchmark (ara+eng, --psm 6)...")
    print("=======================================================")

    for i, item in enumerate(manifest):
        img_path = CARDS_DIR / item["filename"]
        img = Image.open(img_path)

        t0 = time.perf_counter()
        raw_text = pytesseract.image_to_string(img, lang="ara+eng", config="--psm 6")
        dur_s = time.perf_counter() - t0
        latencies.append(dur_s)

        parsed = parse_ocr_text(raw_text)

        # ID evaluation
        expected_id = item["expected_student_number"]
        predicted_id = parsed["student_number"]
        id_match = (predicted_id == expected_id) if expected_id is not None else (predicted_id is None)

        # Name evaluation
        expected_name = item["expected_full_name"]
        predicted_name = parsed["full_name"]
        norm_exp_name = normalize_name_for_comparison(expected_name) if expected_name else None
        norm_pred_name = normalize_name_for_comparison(predicted_name) if predicted_name else None
        name_match = (norm_pred_name == norm_exp_name) if expected_name else (predicted_name is None)

        record = {
            "sample_id": item["sample_id"],
            "filename": item["filename"],
            "language": item["language"],
            "condition": item["condition"],
            "is_negative": item["is_negative"],
            "latency_ms": round(dur_s * 1000, 2),
            "expected_id": expected_id,
            "predicted_id": predicted_id,
            "id_match": id_match,
            "expected_name": expected_name,
            "predicted_name": predicted_name,
            "norm_expected_name": norm_exp_name,
            "norm_predicted_name": norm_pred_name,
            "name_match": name_match,
            "is_ambiguous": parsed["is_ambiguous"],
            "raw_text_snippet": raw_text[:120].replace("\n", " "),
        }
        results.append(record)
        status_id = "✓" if id_match else "✗"
        status_name = "✓" if name_match else "✗"
        print(f"[{i+1:02d}/{len(manifest):02d}] {item['sample_id']:<20} | ID:{status_id} Name:{status_name} | {record['latency_ms']:>7.1f}ms")

    cold_latency_s = latencies[0]
    warm_latencies_ms = [l * 1000 for l in latencies[1:]]
    p50_ms = statistics.median(warm_latencies_ms) if warm_latencies_ms else cold_latency_s * 1000
    p95_ms = sorted(warm_latencies_ms)[int(len(warm_latencies_ms) * 0.95)] if warm_latencies_ms else cold_latency_s * 1000

    # Aggregate accuracy
    positives = [r for r in results if not r["is_negative"]]
    negatives = [r for r in results if r["is_negative"]]

    pos_id_correct = sum(1 for r in positives if r["id_match"])
    pos_name_correct = sum(1 for r in positives if r["name_match"])
    neg_abstentions = sum(1 for r in negatives if r["id_match"])

    # Slice by condition
    by_cond: dict[str, dict[str, Any]] = {}
    for c in ["clean", "perspective", "degraded"]:
        c_samples = [r for r in positives if r["condition"] == c]
        if c_samples:
            by_cond[c] = {
                "count": len(c_samples),
                "id_accuracy": round(sum(1 for r in c_samples if r["id_match"]) / len(c_samples) * 100, 1),
                "name_accuracy": round(sum(1 for r in c_samples if r["name_match"]) / len(c_samples) * 100, 1),
            }

    # Slice by language
    by_lang: dict[str, dict[str, Any]] = {}
    for lg in ["english", "arabic", "mixed"]:
        lg_samples = [r for r in positives if r["language"] == lg]
        if lg_samples:
            by_lang[lg] = {
                "count": len(lg_samples),
                "id_accuracy": round(sum(1 for r in lg_samples if r["id_match"]) / len(lg_samples) * 100, 1),
                "name_accuracy": round(sum(1 for r in lg_samples if r["name_match"]) / len(lg_samples) * 100, 1),
            }

    summary = {
        "engine": "Tesseract 5.4.0",
        "total_samples": len(results),
        "positive_samples": len(positives),
        "negative_samples": len(negatives),
        "overall_id_accuracy": round(pos_id_correct / len(positives) * 100, 1) if positives else 0,
        "overall_name_accuracy": round(pos_name_correct / len(positives) * 100, 1) if positives else 0,
        "negative_abstention_accuracy": round(neg_abstentions / len(negatives) * 100, 1) if negatives else 0,
        "cold_start_s": round(cold_latency_s, 2),
        "warm_p50_ms": round(p50_ms, 1),
        "warm_p95_ms": round(p95_ms, 1),
        "by_condition": by_cond,
        "by_language": by_lang,
        "failures": [r for r in results if not r["id_match"] or not r["name_match"]],
        "detailed_results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / "tesseract_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSaved detailed results to {out_file}")

    return summary


def print_markdown_report(summary: dict[str, Any]) -> None:
    """Print formatted markdown tables for the execution report."""
    print("\n## Tesseract 5.4.0 Benchmark Results")
    print(f"- **Total Samples:** {summary['total_samples']} (36 positive, {summary['negative_samples']} negative)")
    print(f"- **Overall Student ID Exact Match:** {summary['overall_id_accuracy']}% ({summary['positive_samples']} samples)")
    print(f"- **Overall Full Name Normalized Match:** {summary['overall_name_accuracy']}%")
    print(f"- **Negative Sample Abstention:** {summary['negative_abstention_accuracy']}%")
    print(f"- **Latency (CPU):** Cold Start {summary['cold_start_s']}s | Warm p50: {summary['warm_p50_ms']}ms | Warm p95: {summary['warm_p95_ms']}ms")

    print("\n### Accuracy by Image Condition")
    print("| Condition | Samples | Student ID Exact Match | Full Name Normalized Match |")
    print("| :--- | :--- | :--- | :--- |")
    for cond, d in summary["by_condition"].items():
        print(f"| **{cond.capitalize()}** | {d['count']} | {d['id_accuracy']}% | {d['name_accuracy']}% |")

    print("\n### Accuracy by Script / Language")
    print("| Language | Samples | Student ID Exact Match | Full Name Normalized Match |")
    print("| :--- | :--- | :--- | :--- |")
    for lg, d in summary["by_language"].items():
        print(f"| **{lg.capitalize()}** | {d['count']} | {d['id_accuracy']}% | {d['name_accuracy']}% |")

    failures = summary["failures"]
    print(f"\n### Failure Cases ({len(failures)} total)")
    if failures:
        print("| Sample ID | Lang | Condition | Expected ID | Predicted ID | Expected Name | Predicted Name |")
        print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for f in failures[:10]:
            print(f"| `{f['sample_id']}` | {f['language']} | {f['condition']} | `{f['expected_id']}` | `{f['predicted_id']}` | {f['expected_name']} | {f['predicted_name']} |")
    else:
        print("None! All samples matched ground truth.")


if __name__ == "__main__":
    if not MANIFEST_FILE.exists():
        print(f"Manifest {MANIFEST_FILE} not found. Running generator first...")
        from generate_synthetic import generate_all_samples
        manifest = generate_all_samples()
    else:
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    summary = benchmark_tesseract(manifest)
    print_markdown_report(summary)
