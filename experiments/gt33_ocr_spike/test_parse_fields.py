"""Unit tests for pure deterministic OCR field parsing and normalization."""

import pytest
from parse_fields import (
    normalize_arabic_text,
    normalize_digits,
    normalize_name_for_comparison,
    parse_ocr_text,
)


def test_normalize_digits():
    assert normalize_digits("ID: ٢٠٢٤٠١٨٢") == "ID: 20240182"
    assert normalize_digits("رقم: ۰۱۲۳۴۵۶۷۸۹") == "رقم: 0123456789"
    assert normalize_digits("No change: 123456") == "No change: 123456"


def test_normalize_arabic_text():
    # Tashkeel, tatweel, alef variations, teh marbuta, alef maksura
    raw = "أَحْمَدُـ مَحْمُود الإِسْكَنْدَرَانِيّ طَلَبَةٌ وَفَتَى"
    normalized = normalize_arabic_text(raw)
    assert "احمد" in normalized
    assert "محمود" in normalized
    assert "الاسكندراني" in normalized
    assert "طلبه" in normalized
    assert "وفتي" in normalized


def test_normalize_name_for_comparison():
    assert normalize_name_for_comparison("  John  DOE  ") == "john doe"
    assert normalize_name_for_comparison("أحمد علي") == "احمد علي"
    assert normalize_name_for_comparison("Mary-Jane Watson.") == "mary-jane watson"


def test_parse_english_labeled_card():
    text = """
    FUTURE VALLEY UNIVERSITY
    Faculty of Computer Science
    Name: Alice M. Smith
    Student ID: 20240182
    Academic Year: 2024/2025
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "Alice M. Smith"
    assert res["student_number"] == "20240182"
    assert not res["is_ambiguous"]


def test_parse_arabic_labeled_card():
    text = """
    جامعة المستقبل التكنولوجية
    كلية الحاسبات والذكاء الاصطناعي
    الاسم: فاطمة أحمد علي
    الرقم الجامعي: ٢٠٢٣٠٤٩١
    السنة الدراسية: ٢٠٢٣ / ٢٠٢٤
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "فاطمة أحمد علي"
    assert res["student_number"] == "20230491"
    assert not res["is_ambiguous"]


def test_parse_bilingual_card():
    text = """
    METROPOLIS UNIVERSITY - جامعة متروبوليس
    Name / الاسم: Omar Hassan
    ID / الرقم: 20229871
    Valid Until: 2026
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "Omar Hassan"
    assert res["student_number"] == "20229871"
    assert not res["is_ambiguous"]


def test_parse_multiline_fields():
    text = """
    NATIONAL TECH ACADEMY
    Student Name:
    Ziad Tarek Mansour
    Student ID:
    20251144
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "Ziad Tarek Mansour"
    assert res["student_number"] == "20251144"


def test_parse_missing_fields_abstains():
    # Only noise/header, no name label or student ID
    text = """
    CENTRAL UNIVERSITY OF APPLIED SCIENCES
    VISITOR BADGE
    VALID FOR TODAY ONLY
    """
    res = parse_ocr_text(text)
    assert res["full_name"] is None
    assert res["student_number"] is None
    assert not res["is_ambiguous"]


def test_parse_conflicting_ids_abstains():
    # Two competing 8-digit numbers without ID label -> ambiguous
    text = """
    Name: David Miller
    Serial: 10293847
    Barcode: 99887766
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "David Miller"
    assert res["student_number"] is None
    assert res["is_ambiguous"]


def test_parse_rtl_stream_layout():
    # Value appears before the label as scanned LTR by OCR
    text = """
    جامعة المستقبل للتكنولوجيا
    بطاقة إثبات الشخصية الجامعية أحمد محمود علي الاسم: 20242201 الرقم الجامعي: هندسة الحاسبات القسم:
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "أحمد محمود علي"
    assert res["student_number"] == "20242201"


def test_parse_bidi_punctuation_and_controls():
    # Unicode bidi marks and reversed colon
    text = """
    \u200eMETROPOLIS TECH UNIVERSITY\u200f
    Name / \u200f:الاسم\u200e Tarek Mansour
    ID / \u200f:الرقم\u200e 20243015
    """
    res = parse_ocr_text(text)
    assert res["full_name"] == "Tarek Mansour"
    assert res["student_number"] == "20243015"


def test_parse_blank_input():
    res = parse_ocr_text("")
    assert res["full_name"] is None
    assert res["student_number"] is None
