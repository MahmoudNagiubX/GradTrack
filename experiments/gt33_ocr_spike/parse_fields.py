"""Deterministic text parsing and normalization for university card OCR fields.

Extracts suggestions for:
- full_name (English or Arabic)
- student_number (normalized to ASCII digits)

Abstains (returns None) when fields are missing or ambiguous.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict


class ParsedFields(TypedDict):
    full_name: str | None
    student_number: str | None
    raw_name_match: str | None
    raw_id_match: str | None
    is_ambiguous: bool


# Arabic-Indic to Western ASCII digits mapping
ARABIC_INDIC_DIGITS = {
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}


def strip_bidi_controls(text: str) -> str:
    """Strip Unicode bidirectional formatting characters and zero-width spaces."""
    return re.sub(r"[\u200e\u200f\u200b\u202a-\u202e\u2066-\u2069]", "", text)


def normalize_digits(text: str) -> str:
    """Convert Eastern Arabic and Persian digits to standard ASCII digits."""
    text = strip_bidi_controls(text)
    for eastern, western in ARABIC_INDIC_DIGITS.items():
        text = text.replace(eastern, western)
    return text


def normalize_arabic_text(text: str) -> str:
    """Normalize Arabic text for robust comparison.

    - Strips tashkeel (diacritics) and tatweel (kashida).
    - Normalizes alef variations (أ, إ, آ, ٱ -> ا).
    - Normalizes teh marbuta (ة -> ه) and alef maksura (ى -> ي).
    - Normalizes Unicode composition.
    """
    text = unicodedata.normalize("NFKC", text)
    # Remove kashida / tatweel
    text = text.replace("\u0640", "")
    # Remove tashkeel / harakat
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    # Normalize alefs
    text = re.sub(r"[أإآٱ]", "ا", text)
    # Normalize teh marbuta to ha
    text = text.replace("ة", "ه")
    # Normalize alef maksura to ya
    text = text.replace("ى", "ي")
    # Normalize multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name_for_comparison(text: str) -> str:
    """Normalize names (English or Arabic) for fair ground-truth comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = normalize_arabic_text(text)
    # Lowercase Latin letters
    text = text.lower()
    # Remove leading/trailing non-word punctuation
    text = re.sub(r"^[^\w\s]+|[^\w\s]+$", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Label regular expressions with word boundaries and flexible punctuation placement
NAME_LABELS = [
    # English
    r"\b(?:student\s+)?name\b\s*[:\-\.\|]",
    r"\bfull\s*name\b\s*[:\-\.\|]",
    # Arabic (matches 'الاسم:', ':الاسم', 'اسم الطالب:', ':اسم الطالب', etc.)
    r"[:\-\.\|]?\s*(?:اسم\s+الطالب|اسم\s+الطالبة|الاسم\s+بالكامل|الاسم\s+الرباعي|الاسم\s+الثلاثي|الاسم)\s*[:\-\.\|]?",
    # Bilingual combined
    r"\bname\b\s*/\s*[:\-\.\|]?\s*الاسم\s*[:\-\.\|]?",
    r"الاسم\s*/\s*[:\-\.\|]?\s*\bname\b\s*[:\-\.\|]?",
]

ID_LABELS = [
    # English
    r"\b(?:student\s+)?(?:id|no|number|code)\b\s*(?:no\.?|#)?\s*[:\-\.\|]",
    r"\buniversity\s*id\b\s*[:\-\.\|]",
    r"\bacademic\s*id\b\s*[:\-\.\|]",
    r"\bid\s*card\s*no\.?\b\s*[:\-\.\|]",
    r"\breg(?:istration)?\s*no\.?\b\s*[:\-\.\|]",
    # Arabic
    r"[:\-\.\|]?\s*(?:الرقم\s+الجامعي|رقم\s+القيد|رقم\s+الطالب|رقم\s+الكارنيه|كود\s+الطالب|رقم\s+الهوية|الرقم\s+الاكاديمي|رقم\s+التسجيل)\s*[:\-\.\|]?",
    # Bilingual combined
    r"\bid\b\s*/\s*[:\-\.\|]?\s*الرقم\s*[:\-\.\|]?",
    r"الرقم\s*/\s*[:\-\.\|]?\s*\bid\b\s*[:\-\.\|]?",
]

# Valid student ID digit pattern: 6 to 12 digits
STUDENT_ID_REGEX = re.compile(r"\b\d{6,12}\b")

# Noise patterns to filter out of name candidates
RAW_NOISE_WORDS = {
    "university", "faculty", "college", "department", "engineering", "science",
    "student", "card", "identity", "valid", "until", "expire", "expiry",
    "academic", "year", "date", "serial", "barcode", "pass", "badge",
    "جامعة", "جامعي", "جامعية", "كلية", "قسم", "هندسة", "علوم", "حاسبات", "معلومات",
    "طالب", "طالبة", "كارنيه", "بطاقة", "اثبات", "إثبات", "شخصية", "جمهورية", "مصر", "العربية",
    "وزارة", "التعليم", "الرقم", "رقم", "قيد", "كود", "عام", "دراسي", "تاريخ",
    "id", "no", "number",
}
NOISE_WORDS = {normalize_arabic_text(w.lower()) for w in RAW_NOISE_WORDS}


def is_noise_word(word: str) -> bool:
    """Check if word is noise (supporting Arabic 'ال' prefix and normalized form)."""
    w = normalize_arabic_text(word.lower().strip())
    if w in NOISE_WORDS:
        return True
    # Strip Arabic 'ال' prefix and kashida
    w_clean = re.sub(r"^ال", "", w)
    if w_clean in NOISE_WORDS:
        return True
    return False


def clean_name_candidate(candidate: str) -> str | None:
    """Validate and clean a raw name candidate."""
    if not candidate:
        return None

    # Reject if candidate contains 4+ consecutive digits (like student IDs or years)
    if re.search(r"\b\d{4,}\b", candidate):
        return None

    # Strip colons, pipes, slashes, digits, and edge punctuation, while keeping letters, spaces and middle initials
    candidate = re.sub(r"[\d\:\/\|\(\)\[\]\{\}]", "", candidate).strip()
    candidate = re.sub(r"^[^\w]+|[^\w\.]+$", "", candidate).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    words = candidate.split()

    if len(words) < 2 or len(words) > 6:
        return None

    # Filter out lines that are obvious university headers or noise
    noise_count = sum(1 for w in words if is_noise_word(w))
    if noise_count >= 1:
        return None

    return candidate


def parse_ocr_text(raw_text: str) -> ParsedFields:
    """Deterministically parse full_name and student_number from raw OCR text.

    Returns ParsedFields dict with values or None when ambiguous/missing.
    """
    if not raw_text or not raw_text.strip():
        return ParsedFields(
            full_name=None,
            student_number=None,
            raw_name_match=None,
            raw_id_match=None,
            is_ambiguous=False,
        )

    # Normalize line breaks and Eastern digits
    normalized_text = normalize_digits(raw_text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]

    parsed_name: str | None = None
    raw_name_match: str | None = None
    parsed_id: str | None = None
    raw_id_match: str | None = None
    is_ambiguous = False

    # 1. Search for explicitly labeled fields
    name_label_regex = re.compile(r"(" + "|".join(NAME_LABELS) + r")", re.IGNORECASE)
    id_label_regex = re.compile(r"(" + "|".join(ID_LABELS) + r")", re.IGNORECASE)

    for i, line in enumerate(lines):
        # Check for Name label
        if not parsed_name:
            m_name = name_label_regex.search(line)
            if m_name:
                # 1) Try text after label (standard LTR)
                after = line[m_name.end():].strip()
                cleaned_after = clean_name_candidate(after)
                if cleaned_after:
                    parsed_name = cleaned_after
                    raw_name_match = after
                # 2) If after is empty/invalid, try next line (multi-line layout)
                elif not after and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    cleaned_next = clean_name_candidate(next_line)
                    if cleaned_next:
                        parsed_name = cleaned_next
                        raw_name_match = next_line
                # 3) If still not found, try text BEFORE label (Arabic RTL reading order in LTR stream)
                if not parsed_name:
                    before = line[:m_name.start()].strip()
                    if before:
                        words = [w for w in before.split() if w.strip()]
                        non_noise = [w for w in words if not is_noise_word(w) and not re.search(r"\d", w)]
                        if len(non_noise) >= 2:
                            candidate = " ".join(non_noise[-4:])
                            cleaned_before = clean_name_candidate(candidate)
                            if cleaned_before:
                                parsed_name = cleaned_before
                                raw_name_match = candidate

        # Check for ID label
        if not parsed_id:
            m_id = id_label_regex.search(line)
            if m_id:
                # 1) Try text after label
                after = line[m_id.end():].strip()
                digits_found = STUDENT_ID_REGEX.findall(after)
                if len(digits_found) == 1:
                    parsed_id = digits_found[0]
                    raw_id_match = after
                elif len(digits_found) > 1:
                    is_ambiguous = True
                elif not after and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    next_digits = STUDENT_ID_REGEX.findall(next_line)
                    if len(next_digits) == 1:
                        parsed_id = next_digits[0]
                        raw_id_match = next_line
                    elif len(next_digits) > 1:
                        is_ambiguous = True

                # 2) If not in after, try before label (RTL layout)
                if not parsed_id and not is_ambiguous:
                    before = line[:m_id.start()].strip()
                    before_digits = STUDENT_ID_REGEX.findall(before)
                    if len(before_digits) == 1:
                        parsed_id = before_digits[0]
                        raw_id_match = before
                    elif len(before_digits) > 1:
                        is_ambiguous = True

    # 2. If ID was not labeled, search for standalone 6-12 digit numbers
    if not parsed_id:
        all_candidate_numbers: list[str] = []
        for line in lines:
            matches = STUDENT_ID_REGEX.findall(line)
            for num in matches:
                # Discard common years unless they look like 8-digit matriculation IDs
                if len(num) == 4 and (num.startswith("19") or num.startswith("20")):
                    continue
                all_candidate_numbers.append(num)

        unique_numbers = list(dict.fromkeys(all_candidate_numbers))
        if len(unique_numbers) == 1:
            parsed_id = unique_numbers[0]
            raw_id_match = parsed_id
        elif len(unique_numbers) > 1:
            # Multiple candidate IDs with no label -> abstain (ambiguous)
            is_ambiguous = True
            parsed_id = None

    # 3. If Name was not labeled, abstain (do not guess random header lines as names)
    return ParsedFields(
        full_name=parsed_name,
        student_number=parsed_id,
        raw_name_match=raw_name_match,
        raw_id_match=raw_id_match,
        is_ambiguous=is_ambiguous,
    )
