"""Deterministic Synthetic University ID Card Generator for GT-33 Feasibility Spike.

Generates a balanced corpus of synthetic university-ID-like cards:
- 12 English cards (4 clean, 4 perspective, 4 degraded)
- 12 Arabic cards (4 clean, 4 perspective, 4 degraded)
- 12 Mixed/Bilingual cards (4 clean, 4 perspective, 4 degraded)
- 4 Negative/Ambiguity cards (missing fields, conflicting numbers, visitor badge, blank)
Total: 40 synthetic cards.

All personal names, student IDs, and institutions are 100% fictional.
Never uses real university templates or actual student records.
"""

from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path
from typing import TypedDict

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SEED = 42
OUTPUT_DIR = Path(__file__).parent / "generated_cards"
MANIFEST_PATH = Path(__file__).parent / "ground_truth_manifest.json"

FONT_ARIAL = "C:/Windows/Fonts/arial.ttf"
FONT_TAHOMA = "C:/Windows/Fonts/tahoma.ttf"


class SampleMetadata(TypedDict):
    sample_id: str
    filename: str
    language: str
    condition: str
    expected_full_name: str | None
    expected_student_number: str | None
    is_negative: bool
    notes: str


ENGLISH_CARDS_DATA = [
    # Clean (0-3)
    {"name": "Alexander Clark", "id": "20240182", "faculty": "Engineering", "dept": "Computer Engineering", "cond": "clean"},
    {"name": "Jessica Morgan", "id": "20231940", "faculty": "Science", "dept": "Mathematics", "cond": "clean"},
    {"name": "Marcus Vance", "id": "20228301", "faculty": "Business", "dept": "Finance", "cond": "clean"},
    {"name": "Olivia Bennett", "id": "20250019", "faculty": "Arts", "dept": "English Literature", "cond": "clean"},
    # Perspective (4-7)
    {"name": "Ethan Hayes", "id": "20241102", "faculty": "Engineering", "dept": "Civil Engineering", "cond": "perspective"},
    {"name": "Sophia Turner", "id": "20230554", "faculty": "Medicine", "dept": "General Surgery", "cond": "perspective"},
    {"name": "Benjamin Scott", "id": "20227189", "faculty": "Computer Science", "dept": "AI & Robotics", "cond": "perspective"},
    {"name": "Chloe Davis", "id": "20250912", "faculty": "Architecture", "dept": "Urban Planning", "cond": "perspective"},
    # Degraded (8-11)
    {"name": "Lucas Wright", "id": "20241830", "faculty": "Science", "dept": "Physics", "cond": "degraded"},
    {"name": "Emily Watson", "id": "20231477", "faculty": "Pharmacy", "dept": "Clinical Pharmacy", "cond": "degraded"},
    {"name": "Daniel Foster", "id": "20229045", "faculty": "Law", "dept": "Public Law", "cond": "degraded"},
    {"name": "Natalie Reed", "id": "20250321", "faculty": "Engineering", "dept": "Mechanical", "cond": "degraded"},
]

ARABIC_CARDS_DATA = [
    # Clean (0-3)
    {"name": "أحمد محمود علي", "id": "20242201", "faculty": "الهندسة", "dept": "هندسة الحاسبات", "cond": "clean"},
    {"name": "سارة محمد إبراهيم", "id": "20233119", "faculty": "العلوم", "dept": "الرياضيات", "cond": "clean"},
    {"name": "عمر خالد الشافعي", "id": "20226450", "faculty": "التجارة", "dept": "المحاسبة", "cond": "clean"},
    {"name": "مريم يوسف رضوان", "id": "20251788", "faculty": "الآداب", "dept": "اللغة الإنجليزية", "cond": "clean"},
    # Perspective (4-7)
    {"name": "كريم عبد الله حسن", "id": "20240899", "faculty": "الهندسة", "dept": "الهندسة المدنية", "cond": "perspective"},
    {"name": "نور الهدى طارق", "id": "20234102", "faculty": "الطب البشري", "dept": "الجراحة العامة", "cond": "perspective"},
    {"name": "مصطفى كمال الدين", "id": "20227763", "faculty": "الحاسبات والمعلومات", "dept": "الذكاء الاصطناعي", "cond": "perspective"},
    {"name": "فاطمة حسن خليل", "id": "20250441", "faculty": "الهندسة المعمارية", "dept": "التخطيط العمراني", "cond": "perspective"},
    # Degraded (8-11)
    {"name": "يحيى سعيد منصور", "id": "20241512", "faculty": "العلوم", "dept": "الفيزياء", "cond": "degraded"},
    {"name": "آية أحمد عثمان", "id": "20232980", "faculty": "الصيدلة", "dept": "الصيدلة الإكلينيكية", "cond": "degraded"},
    {"name": "زياد شريف إسماعيل", "id": "20228114", "faculty": "الحقوق", "dept": "القانون العام", "cond": "degraded"},
    {"name": "هدى عبد الرحمن سالم", "id": "20251203", "faculty": "الهندسة", "dept": "الهندسة الميكانيكية", "cond": "degraded"},
]

MIXED_CARDS_DATA = [
    # Clean (0-3)
    {"name": "Tarek Mansour", "id": "20243015", "faculty": "Engineering / الهندسة", "cond": "clean"},
    {"name": "Dina El-Sayed", "id": "20234509", "faculty": "Science / العلوم", "cond": "clean"},
    {"name": "Amr Adel Mostafa", "id": "20229871", "faculty": "Computer Science / الحاسبات", "cond": "clean"},
    {"name": "Salma Nabil Fawzy", "id": "20252104", "faculty": "Business / إدارة الأعمال", "cond": "clean"},
    # Perspective (4-7)
    {"name": "Hany Gamal Eldin", "id": "20241920", "faculty": "Engineering / الهندسة", "cond": "perspective"},
    {"name": "Reem Khaled Maher", "id": "20235611", "faculty": "Medicine / الطب", "cond": "perspective"},
    {"name": "Sherif Anwar Zaki", "id": "20228902", "faculty": "Dentistry / طب الأسنان", "cond": "perspective"},
    {"name": "Yasmin Samir Badawi", "id": "20251640", "faculty": "Pharmacy / الصيدلة", "cond": "perspective"},
    # Degraded (8-11)
    {"name": "Mohamed Fathy Soliman", "id": "20242750", "faculty": "Science / العلوم", "cond": "degraded"},
    {"name": "Laila Essam Fouad", "id": "20236021", "faculty": "Arts / الآداب", "cond": "degraded"},
    {"name": "Wael Ahmed Gaber", "id": "20229415", "faculty": "Applied Arts / الفنون التطبيقية", "cond": "degraded"},
    {"name": "Nada Taha Metwally", "id": "20252399", "faculty": "Engineering / الهندسة", "cond": "degraded"},
]

NEGATIVE_CARDS_DATA = [
    {
        "id_suffix": "neg_01_no_id",
        "lang": "english",
        "cond": "clean",
        "name": "Victoria Hughes",
        "notes": "Valid name but student ID omitted entirely; parser should return student_number=None",
        "kind": "no_id",
    },
    {
        "id_suffix": "neg_02_conflicting_ids",
        "lang": "english",
        "cond": "clean",
        "name": "Jonathan Brooks",
        "notes": "Two conflicting 8-digit numbers without ID label; parser should abstain with is_ambiguous=True",
        "kind": "conflicting_ids",
    },
    {
        "id_suffix": "neg_03_visitor_badge",
        "lang": "arabic",
        "cond": "clean",
        "name": "حازم شريف زكي",
        "notes": "Arabic visitor badge without university student matriculation number; student_number=None",
        "kind": "visitor_badge",
    },
    {
        "id_suffix": "neg_04_blank_noise",
        "lang": "mixed",
        "cond": "degraded",
        "name": None,
        "notes": "Background card texture with no student fields; parser should return None for all fields",
        "kind": "blank_noise",
    },
]


def render_arabic_text(text: str) -> str:
    """Reshape and reorder Arabic text for proper RTL display with Pillow."""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def draw_card_base(width: int = 856, height: int = 540, accent_color: tuple[int, int, int] = (24, 76, 120)) -> Image.Image:
    """Create a crisp card base with header, rounded frame, photo placeholder and chip."""
    card = Image.new("RGB", (width, height), (252, 252, 254))
    draw = ImageDraw.Draw(card)

    # Outer border
    draw.rounded_rectangle([(10, 10), (width - 10, height - 10)], radius=18, outline=(180, 190, 205), width=2)

    # Top header bar
    draw.rectangle([(12, 12), (width - 12, 90)], fill=accent_color)
    draw.rectangle([(12, 90), (width - 12, 96)], fill=(212, 175, 55))  # Gold accent line

    # Photo placeholder
    photo_box = [(40, 130), (200, 330)]
    draw.rectangle(photo_box, fill=(225, 230, 238), outline=(160, 175, 195), width=2)
    # Head and shoulder silhouette
    draw.ellipse([(90, 160), (150, 220)], fill=(180, 195, 215))
    draw.pieslice([(60, 230), (180, 320)], start=180, end=0, fill=(180, 195, 215))

    # Bottom footer accent
    draw.rectangle([(12, height - 35), (width - 12, height - 12)], fill=(240, 243, 248))

    return card


def apply_perspective_distortion(card: Image.Image, angle: float = 4.5) -> Image.Image:
    """Rotate card slightly and place on a neutral surface background."""
    # Rotate with smooth bicubic resampling
    rotated = card.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)

    # Create background desk surface (1000 x 700)
    bg_w = max(rotated.width + 120, 1050)
    bg_h = max(rotated.height + 120, 750)
    bg = Image.new("RGB", (bg_w, bg_h), (232, 228, 222))

    # Subtle drop shadow
    shadow_mask = Image.new("L", rotated.size, 0)
    draw_mask = ImageDraw.Draw(shadow_mask)
    draw_mask.rectangle([(0, 0), rotated.size], fill=80)
    shadow_blurred = shadow_mask.filter(ImageFilter.GaussianBlur(8))

    paste_x = (bg_w - rotated.width) // 2
    paste_y = (bg_h - rotated.height) // 2

    bg.paste((20, 20, 20), (paste_x + 6, paste_y + 8), shadow_blurred)
    bg.paste(rotated, (paste_x, paste_y))
    return bg


def apply_degradation(card: Image.Image) -> Image.Image:
    """Apply mild Gaussian blur and simulated camera compression artifacts."""
    # Gentle blur simulating smartphone slight defocus
    blurred = card.filter(ImageFilter.GaussianBlur(0.9))

    # Save and reload through low-quality JPEG to introduce DCT compression artifacts
    temp_path = OUTPUT_DIR / "_temp_degraded.jpg"
    blurred.save(temp_path, "JPEG", quality=38)
    degraded = Image.open(temp_path).copy()
    if temp_path.exists():
        temp_path.unlink()
    return degraded


def create_english_card(data: dict, index: int) -> tuple[Image.Image, SampleMetadata]:
    sample_id = f"eng_{data['cond']}_{index:02d}"
    filename = f"{sample_id}.png"

    card = draw_card_base(accent_color=(20, 60, 110))
    draw = ImageDraw.Draw(card)

    font_header = ImageFont.truetype(FONT_ARIAL, 28)
    font_sub = ImageFont.truetype(FONT_ARIAL, 18)
    font_label = ImageFont.truetype(FONT_ARIAL, 22)
    font_value = ImageFont.truetype(FONT_ARIAL, 22)

    # University header
    draw.text((30, 22), "FUTURE VALLEY UNIVERSITY", fill=(255, 255, 255), font=font_header)
    draw.text((30, 58), "OFFICIAL STUDENT IDENTITY CARD", fill=(220, 235, 255), font=font_sub)

    # Fields
    x_label = 240
    y_start = 140
    line_spacing = 45

    draw.text((x_label, y_start), "Name:", fill=(100, 110, 125), font=font_label)
    draw.text((x_label + 90, y_start), data["name"], fill=(15, 23, 42), font=font_value)

    draw.text((x_label, y_start + line_spacing), "Student ID:", fill=(100, 110, 125), font=font_label)
    draw.text((x_label + 130, y_start + line_spacing), data["id"], fill=(15, 23, 42), font=font_value)

    draw.text((x_label, y_start + line_spacing * 2), "Faculty:", fill=(100, 110, 125), font=font_label)
    draw.text((x_label + 100, y_start + line_spacing * 2), data["faculty"], fill=(15, 23, 42), font=font_value)

    draw.text((x_label, y_start + line_spacing * 3), "Department:", fill=(100, 110, 125), font=font_label)
    draw.text((x_label + 140, y_start + line_spacing * 3), data["dept"], fill=(15, 23, 42), font=font_value)

    draw.text((30, 512), "Academic Year 2024 / 2025 • Valid until Graduation", fill=(120, 130, 145), font=font_sub)

    # Apply condition
    cond = data["cond"]
    if cond == "perspective":
        img = apply_perspective_distortion(card, angle=5.0)
    elif cond == "degraded":
        img = apply_degradation(card)
    else:
        img = card

    meta: SampleMetadata = {
        "sample_id": sample_id,
        "filename": filename,
        "language": "english",
        "condition": cond,
        "expected_full_name": data["name"],
        "expected_student_number": data["id"],
        "is_negative": False,
        "notes": f"English fictional card ({cond})",
    }
    return img, meta


def create_arabic_card(data: dict, index: int) -> tuple[Image.Image, SampleMetadata]:
    sample_id = f"ara_{data['cond']}_{index:02d}"
    filename = f"{sample_id}.png"

    card = draw_card_base(accent_color=(15, 75, 45))  # Green header
    draw = ImageDraw.Draw(card)

    font_header = ImageFont.truetype(FONT_ARIAL, 28)
    font_sub = ImageFont.truetype(FONT_ARIAL, 18)
    font_body = ImageFont.truetype(FONT_ARIAL, 22)

    # Arabic header (rendered with proper reshaping)
    h_text = render_arabic_text("جامعة المستقبل للتكنولوجيا")
    sub_text = render_arabic_text("بطاقة إثبات الشخصية الجامعية")
    draw.text((40, 20), h_text, fill=(255, 255, 255), font=font_header)
    draw.text((40, 58), sub_text, fill=(215, 245, 225), font=font_sub)

    # Fields
    x_start = 240
    y_start = 140
    line_spacing = 45

    name_label = render_arabic_text("الاسم:")
    name_val = render_arabic_text(data["name"])
    draw.text((x_start, y_start), name_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 70, y_start), name_val, fill=(15, 23, 42), font=font_body)

    id_label = render_arabic_text("الرقم الجامعي:")
    id_val = data["id"]
    draw.text((x_start, y_start + line_spacing), id_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 150, y_start + line_spacing), id_val, fill=(15, 23, 42), font=font_body)

    fac_label = render_arabic_text("الكلية:")
    fac_val = render_arabic_text(data["faculty"])
    draw.text((x_start, y_start + line_spacing * 2), fac_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 80, y_start + line_spacing * 2), fac_val, fill=(15, 23, 42), font=font_body)

    dept_label = render_arabic_text("القسم:")
    dept_val = render_arabic_text(data["dept"])
    draw.text((x_start, y_start + line_spacing * 3), dept_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 80, y_start + line_spacing * 3), dept_val, fill=(15, 23, 42), font=font_body)

    footer_text = render_arabic_text("العام الجامعي ٢٠٢٤ / ٢٠٢٥ • صالحة طوال فترة الدراسة")
    draw.text((40, 510), footer_text, fill=(120, 130, 145), font=font_sub)

    # Apply condition
    cond = data["cond"]
    if cond == "perspective":
        img = apply_perspective_distortion(card, angle=-4.5)
    elif cond == "degraded":
        img = apply_degradation(card)
    else:
        img = card

    meta: SampleMetadata = {
        "sample_id": sample_id,
        "filename": filename,
        "language": "arabic",
        "condition": cond,
        "expected_full_name": data["name"],
        "expected_student_number": data["id"],
        "is_negative": False,
        "notes": f"Arabic fictional card ({cond})",
    }
    return img, meta


def create_mixed_card(data: dict, index: int) -> tuple[Image.Image, SampleMetadata]:
    sample_id = f"mix_{data['cond']}_{index:02d}"
    filename = f"{sample_id}.png"

    card = draw_card_base(accent_color=(90, 40, 110))  # Purple header
    draw = ImageDraw.Draw(card)

    font_header = ImageFont.truetype(FONT_ARIAL, 26)
    font_sub = ImageFont.truetype(FONT_ARIAL, 17)
    font_body = ImageFont.truetype(FONT_ARIAL, 21)

    h_en = "METROPOLIS TECH UNIVERSITY"
    h_ar = render_arabic_text("جامعة متروبوليس للعلوم")
    draw.text((30, 20), f"{h_en} | {h_ar}", fill=(255, 255, 255), font=font_header)
    draw.text((30, 58), "STUDENT CARD • بطاقة الطالب الجامعية", fill=(235, 215, 245), font=font_sub)

    x_start = 240
    y_start = 140
    line_spacing = 45

    name_label = f"Name / {render_arabic_text('الاسم')}:"
    draw.text((x_start, y_start), name_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 160, y_start), data["name"], fill=(15, 23, 42), font=font_body)

    id_label = f"ID / {render_arabic_text('الرقم')}:"
    draw.text((x_start, y_start + line_spacing), id_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 130, y_start + line_spacing), data["id"], fill=(15, 23, 42), font=font_body)

    fac_label = "Faculty / الكلية:"
    draw.text((x_start, y_start + line_spacing * 2), fac_label, fill=(100, 110, 125), font=font_body)
    draw.text((x_start + 160, y_start + line_spacing * 2), data["faculty"], fill=(15, 23, 42), font=font_body)

    draw.text((30, 510), "Academic Year 2024/2025 • Valid until Graduation", fill=(120, 130, 145), font=font_sub)

    cond = data["cond"]
    if cond == "perspective":
        img = apply_perspective_distortion(card, angle=5.5)
    elif cond == "degraded":
        img = apply_degradation(card)
    else:
        img = card

    meta: SampleMetadata = {
        "sample_id": sample_id,
        "filename": filename,
        "language": "mixed",
        "condition": cond,
        "expected_full_name": data["name"],
        "expected_student_number": data["id"],
        "is_negative": False,
        "notes": f"Mixed/bilingual card ({cond})",
    }
    return img, meta


def create_negative_card(data: dict) -> tuple[Image.Image, SampleMetadata]:
    sample_id = data["id_suffix"]
    filename = f"{sample_id}.png"
    kind = data["kind"]

    if kind == "no_id":
        card = draw_card_base(accent_color=(120, 50, 40))
        draw = ImageDraw.Draw(card)
        font_header = ImageFont.truetype(FONT_ARIAL, 26)
        font_body = ImageFont.truetype(FONT_ARIAL, 22)
        draw.text((30, 25), "CAMPUS LIBRARY ACCESS PASS", fill=(255, 255, 255), font=font_header)
        draw.text((240, 160), "Name:", fill=(100, 110, 125), font=font_body)
        draw.text((330, 160), data["name"], fill=(15, 23, 42), font=font_body)
        draw.text((240, 220), "Card Type: Temporary Library Access", fill=(100, 110, 125), font=font_body)
        draw.text((240, 280), "Expires: 2024-12-31", fill=(100, 110, 125), font=font_body)
        img = card
        exp_id = None
        exp_name = data["name"]

    elif kind == "conflicting_ids":
        card = draw_card_base(accent_color=(50, 70, 90))
        draw = ImageDraw.Draw(card)
        font_header = ImageFont.truetype(FONT_ARIAL, 26)
        font_body = ImageFont.truetype(FONT_ARIAL, 22)
        draw.text((30, 25), "SECURITY ACCESS BADGE", fill=(255, 255, 255), font=font_header)
        draw.text((240, 150), "Name:", fill=(100, 110, 125), font=font_body)
        draw.text((330, 150), data["name"], fill=(15, 23, 42), font=font_body)
        draw.text((240, 210), "Serial: 10293847", fill=(100, 110, 125), font=font_body)
        draw.text((240, 270), "Barcode: 99887766", fill=(100, 110, 125), font=font_body)
        img = card
        exp_id = None
        exp_name = data["name"]

    elif kind == "visitor_badge":
        card = draw_card_base(accent_color=(180, 80, 20))
        draw = ImageDraw.Draw(card)
        font_header = ImageFont.truetype(FONT_ARIAL, 28)
        font_body = ImageFont.truetype(FONT_ARIAL, 22)
        draw.text((40, 25), render_arabic_text("بطاقة زائر مؤقتة - جامعة النيل"), fill=(255, 255, 255), font=font_header)
        draw.text((240, 160), render_arabic_text("الاسم:"), fill=(100, 110, 125), font=font_body)
        draw.text((320, 160), render_arabic_text(data["name"]), fill=(15, 23, 42), font=font_body)
        draw.text((240, 220), render_arabic_text("نوع التصريح: تصريح زيارة يومي"), fill=(100, 110, 125), font=font_body)
        img = card
        exp_id = None
        exp_name = data["name"]

    else:  # blank_noise
        card = Image.new("RGB", (856, 540), (230, 232, 235))
        draw = ImageDraw.Draw(card)
        for i in range(15):
            draw.line([(0, i * 36), (856, i * 36 + 20)], fill=(215, 218, 222), width=1)
        img = apply_degradation(card)
        exp_id = None
        exp_name = None

    meta: SampleMetadata = {
        "sample_id": sample_id,
        "filename": filename,
        "language": data["lang"],
        "condition": data["cond"],
        "expected_full_name": exp_name,
        "expected_student_number": exp_id,
        "is_negative": True,
        "notes": data["notes"],
    }
    return img, meta


def generate_all_samples() -> list[SampleMetadata]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)
    manifest: list[SampleMetadata] = []

    print(f"Generating synthetic university ID card corpus into {OUTPUT_DIR}...")

    # 1. English cards (12)
    for i, item in enumerate(ENGLISH_CARDS_DATA):
        img, meta = create_english_card(item, i + 1)
        img.save(OUTPUT_DIR / meta["filename"])
        manifest.append(meta)

    # 2. Arabic cards (12)
    for i, item in enumerate(ARABIC_CARDS_DATA):
        img, meta = create_arabic_card(item, i + 1)
        img.save(OUTPUT_DIR / meta["filename"])
        manifest.append(meta)

    # 3. Mixed cards (12)
    for i, item in enumerate(MIXED_CARDS_DATA):
        img, meta = create_mixed_card(item, i + 1)
        img.save(OUTPUT_DIR / meta["filename"])
        manifest.append(meta)

    # 4. Negative cards (4)
    for item in NEGATIVE_CARDS_DATA:
        img, meta = create_negative_card(item)
        img.save(OUTPUT_DIR / meta["filename"])
        manifest.append(meta)

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {len(manifest)} cards and manifest {MANIFEST_PATH}")
    return manifest


if __name__ == "__main__":
    generate_all_samples()
