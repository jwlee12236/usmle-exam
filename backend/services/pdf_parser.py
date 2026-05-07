import gc
import re
import uuid
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional

IMAGES_DIR = Path(__file__).parent.parent / "static" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Regex to detect question start — handles OCR artifacts in NBME PDFs:
#   "11 . text"  → space between number and period
#   "4 7. text"  → space inside a two-digit number
# \d\s?\d? captures 1–2 digits with an optional space between them.
# \s*\.\s+ then allows optional space before the period and requires space after.
# Decimal numbers like "14.5" are rejected because \s+ needs a space after ".".
QUESTION_START_RE = re.compile(r"^(\d\s?\d?)\s*\.\s+(.*)")

# Regex to detect answer choices after text cleaning normalizes them to "A. text"
CHOICE_RE = re.compile(r"^([A-G])\.\s+(.+)$")

# Junk lines from screenshotted NBME/UWorld interfaces that appear between questions
_JUNK_EXACT = {
    'previous', 'next', 'help', 'pause',
    'lab values calculator review',
    'national board of medical examiners',
    'time remaining:',
    '■ mark', 'mark',
    'obstetrics and gynecology self-assessment',
    'gynecology and obstetrics self-assessment',
}
_JUNK_RE = re.compile(
    r'^([Q0Oo]|r|~|~\s*p,?\s*r,?|https?://\S+|exam section\s*:.*'
    r'|\d+\s*hr\s*\d+\s*min\s*\d+\s*sec|item\s+\d+\s+of\s+\d+)$',
    re.IGNORECASE,
)

# A stem line is meaningful if it has a real word (2+ letters) or a lab-value number with a unit.
# This filters chart/graph noise like "|", ". .", "_J_", "=t+-=", "30" (bare axis label), etc.
# Uses [a-zA-Z%/±()]+ (not \w) so bare numbers like "210" or "30" don't match as their own unit.
_MEANINGFUL_RE = re.compile(
    r'[a-zA-Z]{2,}'                          # at least one real word
    r'|^[><=]?[\d,]+\.?\d*\s*[a-zA-Z%/±()]+' # numeric + unit, e.g. "30%", ">100 sec", "9500/mm3"
)

# NBME header format "Item N of 50" — used to extract question number from image-based pages
_ITEM_NUM_RE = re.compile(r'Item\s+(\d+)\s+of\s+\d+', re.IGNORECASE)

# Stem phrases that indicate a question contains a clinical image/figure that must be shown
_VISUAL_RE = re.compile(
    r'\b(shown|tracing|graph|figure|photograph|radiograph|x[\s-]?ray|mri|ct scan'
    r'|ecg|ekg|electrocardiogram|histolog|slide|biopsy|image|scan)\b',
    re.IGNORECASE,
)


def _clean_pdf_text(text: str) -> str:
    """Remove NBME/UWorld UI chrome and normalize choice format."""
    lines = text.split('\n')
    cleaned = []
    i = 0
    while i < len(lines):
        ls = lines[i].strip()

        # Drop known junk lines (nav chrome, lone radio placeholders Q/0/O, etc.)
        if ls.lower() in _JUNK_EXACT or _JUNK_RE.match(ls):
            i += 1
            continue

        # Lone radio-button placeholder followed by a choice letter on next line:
        # skip the placeholder; next iteration picks up the choice line normally.
        if re.match(r'^[Q0Oo]\s*$', ls) and i + 1 < len(lines):
            next_ls = lines[i + 1].strip()
            if re.match(r'^[A-G][.)]\s+', next_ls):
                i += 1
                continue

        cleaned.append(lines[i])
        i += 1

    text = '\n'.join(cleaned)

    # Normalize "Q A) text" / "0 A) text" → "A. text"
    text = re.sub(r'(?m)^[Q0Oo]\s+([A-G])[.)]\s+', r'\1. ', text)
    # Normalize bare "A) text" → "A. text"
    text = re.sub(r'(?m)^([A-G])\)\s+', r'\1. ', text)

    return text


def _page_is_image_based(page_text: str) -> bool:
    """True if a page has no real question content — just UI chrome or image watermarks."""
    cleaned = _clean_pdf_text(page_text)
    meaningful = [l for l in cleaned.split('\n') if l.strip() and _MEANINGFUL_RE.search(l.strip())]
    return len(meaningful) < 3


def _page_has_no_question(page_text: str) -> bool:
    """True if page has meaningful text but no question number."""
    return not any(QUESTION_START_RE.match(l.lstrip().rstrip()) for l in page_text.split('\n'))


def _detect_answer_key_format(doc) -> str:
    """
    Detect answer key format:
      'compact'    — few pages, plain text answer list (e.g. '1. A - explanation')
      'image_only' — all/most pages are screenshots, requires 100+ OCR calls (skip)
      'standard'   — full Q+A+explanation pages, current approach
    """
    n_pages = len(doc)
    if n_pages <= 15:
        return "compact"
    sample = min(8, n_pages)
    image_count = sum(1 for i in range(sample) if _page_is_image_based(doc[i].get_text("text")))
    if image_count >= sample * 0.8:
        return "image_only"
    return "standard"


def _parse_compact_answers(text: str) -> list[dict]:
    """
    Parse compact answer key format: lines like '1. A', '1. A - explanation',
    '1) B', '16. J - ...'. Handles any capital letter as an answer.
    """
    results = []
    answer_re = re.compile(r'^\s*(\d+)[.)]\s*([A-Z])\b', re.MULTILINE)
    seen = set()
    for m in answer_re.finditer(text):
        qn = int(m.group(1))
        if qn in seen:
            continue
        seen.add(qn)
        results.append({
            "question_number": qn,
            "correct_answer": m.group(2).upper(),
            "stem": "",
            "choices": {},
        })
    return results


def extract_questions_from_pdf(pdf_path: str, exam_set_id: int, has_answers: bool = False) -> list[dict]:
    from services.vision import detect_figure_on_page, ocr_page  # lazy import to avoid startup cost

    doc = fitz.open(pdf_path)

    # --- Answer key: detect format and short-circuit for compact/image_only ---
    if has_answers:
        fmt = _detect_answer_key_format(doc)
        print(f"Answer key format: {fmt} ({len(doc)} pages)")

        if fmt == "compact":
            full_text = "".join(page.get_text("text") + "\n" for page in doc)
            doc.close()
            return _parse_compact_answers(full_text)

        if fmt == "image_only":
            print("Image-only answer key — skipping OCR to avoid memory overload. Upload a text-based answer key for scoring.")
            doc.close()
            return []

    # --- Build full text and track which PDF page each question starts on ---
    full_text = ""
    question_page: dict[int, int] = {}  # question_number -> page_num

    for page_num, page in enumerate(doc):
        page_text = page.get_text("text")

        if _page_is_image_based(page_text):
            item_m = _ITEM_NUM_RE.search(page_text)
            hint_num = int(item_m.group(1)) if item_m else None
            try:
                page_text = ocr_page(page, hint_num, has_answers=has_answers)
                print(f"OCR page {page_num} (Q{hint_num}): {page_text[:80]}")
            except Exception as e:
                print(f"OCR failed for page {page_num}: {e}")
                page_text = ""
            gc.collect()
        elif has_answers and _page_has_no_question(page_text) and page.get_images():
            # Hybrid page: embedded image question + text explanation below
            item_m = _ITEM_NUM_RE.search(page_text)
            hint_num = int(item_m.group(1)) if item_m else None
            try:
                ocr_text = ocr_page(page, hint_num, has_answers=True)
                ocr_text = re.sub(r'(?m)^\[(\d+)\]', r'\1', ocr_text)
                page_text = ocr_text + "\n" + page_text
                print(f"OCR hybrid page {page_num} (Q{hint_num}): {ocr_text[:80]}")
            except Exception as e:
                print(f"OCR failed for hybrid page {page_num}: {e}")
            gc.collect()

        for line in page_text.split("\n"):
            m = QUESTION_START_RE.match(line.lstrip().rstrip())
            if m:
                qn = int(m.group(1).replace(" ", ""))
                if qn not in question_page:
                    question_page[qn] = page_num
                break
        full_text += page_text + "\n"

    full_text = _clean_pdf_text(full_text)

    if has_answers:
        questions = _parse_answer_key(full_text, {})
    else:
        questions = _parse_questions_only(full_text, {})

    # For each question, ask Claude Haiku if that page has a clinical figure.
    # If yes, crop and save just the figure region as the question image.
    # doc must stay open until all vision calls are done.
    for q in questions:
        page_num = question_page.get(q["question_number"])
        q["pdf_page"] = page_num
        q["image_paths"] = []

        if page_num is None or has_answers:
            continue

        try:
            bbox = detect_figure_on_page(doc[page_num])
        except Exception as e:
            print(f"Vision detection failed for Q{q['question_number']}: {e}")
            bbox = None
        gc.collect()

        if bbox:
            margin = 60
            pr = doc[page_num].rect
            # Detect header bottom dynamically so figure crops never include
            # the NBME header chrome (blue "Exam Section / Time Remaining" bar).
            _HEADER_KW = {'exam section', 'national board', 'time remaining', '■ mark', 'obstetrics'}
            header_bottom = pr.height * 0.05
            for b in doc[page_num].get_text("blocks"):
                if b[6] != 0:
                    continue
                if any(kw in b[4].strip().lower() for kw in _HEADER_KW):
                    header_bottom = max(header_bottom, b[3])
            # Always use full page width — Claude's bbox x/w are unreliable for
            # wide graphs and tables. Only crop vertically to remove header/footer.
            clip = fitz.Rect(
                0,
                max(header_bottom, bbox["y"] - margin),
                pr.width,
                min(pr.height, bbox["y"] + bbox["h"] + margin),
            )
            pix = doc[page_num].get_pixmap(dpi=72, clip=clip)
            image_name = f"{exam_set_id}_q{q['question_number']}_{uuid.uuid4().hex[:8]}.png"
            image_path = IMAGES_DIR / image_name
            pix.save(str(image_path))
            q["image_paths"] = [f"images/{image_name}"]

    doc.close()
    return questions


def _parse_questions_only(text: str, page_images: dict) -> list[dict]:
    lines = text.split("\n")
    questions = []
    current_q: Optional[dict] = None
    current_section = "stem"

    for line in lines:
        # lstrip so leading whitespace from embedded charts/tables doesn't block matching
        ls = line.lstrip().rstrip()

        q_match = QUESTION_START_RE.match(ls)
        if q_match:
            q_num = int(q_match.group(1).replace(" ", ""))
            current_num = current_q["question_number"] if current_q else 0
            # Only advance forward — rejects numbered lists in stems that repeat
            # a number <= the current question (e.g. "2." inside Q3 is ignored)
            if q_num > current_num:
                if current_q:
                    current_q["stem"] = current_q["stem"].strip()
                    questions.append(current_q)
                rest = q_match.group(2).strip()
                current_q = {
                    "question_number": q_num,
                    "stem": rest + "\n" if rest else "",
                    "choices": {},
                    "image_paths": [],
                }
                current_section = "stem"
                continue

        if current_q is None:
            continue

        choice_match = CHOICE_RE.match(ls)
        if choice_match:
            current_section = "choices"
            current_q["choices"][choice_match.group(1)] = choice_match.group(2).strip()
        elif current_section == "stem" and ls and _MEANINGFUL_RE.search(ls):
            # Only add lines that contain real words or lab values — drops chart/graph noise
            current_q["stem"] += ls + "\n"
        elif current_section == "choices" and ls and current_q["choices"]:
            last_letter = list(current_q["choices"].keys())[-1]
            current_q["choices"][last_letter] += " " + ls

    if current_q:
        current_q["stem"] = current_q["stem"].strip()
        questions.append(current_q)

    return questions


def _parse_answer_key(text: str, page_images: dict) -> list[dict]:
    """
    Parse answer key PDF that contains questions + correct answers + explanations.
    Expected format after each question block: correct answer clearly marked,
    followed by explanation text.
    """
    questions = _parse_questions_only(text, page_images)

    # Try to find answer + explanation sections
    # Look for patterns like "Answer: E" or "The correct answer is E"
    answer_re = re.compile(
        r"(?:Answer:|Correct answer:|The correct answer is)\s*([A-G])",
        re.IGNORECASE
    )

    lines = text.split("\n")
    # Build a map of question_number -> (correct_answer, explanation)
    answer_map = {}
    current_q_num = None
    capture_explanation = False
    explanation_lines = []
    found_answer = None

    for line in lines:
        line_stripped = line.strip()

        q_match = QUESTION_START_RE.match(line.lstrip().rstrip())
        if q_match:
            # Save previous
            if current_q_num is not None and found_answer:
                answer_map[current_q_num] = {
                    "correct_answer": found_answer,
                    "explanation": " ".join(explanation_lines).strip(),
                }
            current_q_num = int(q_match.group(1).replace(" ", ""))
            found_answer = None
            explanation_lines = []
            capture_explanation = False
            continue

        ans_match = answer_re.search(line_stripped)
        if ans_match and current_q_num is not None and not found_answer:
            found_answer = ans_match.group(1).upper()
            capture_explanation = True
            # Capture rest of line as start of explanation
            rest = line_stripped[ans_match.end():].strip(" .-:")
            if rest:
                explanation_lines.append(rest)
            continue

        if capture_explanation and line_stripped:
            explanation_lines.append(line_stripped)

    if current_q_num is not None and found_answer:
        answer_map[current_q_num] = {
            "correct_answer": found_answer,
            "explanation": " ".join(explanation_lines).strip(),
        }

    # Merge into questions
    for q in questions:
        qn = q["question_number"]
        if qn in answer_map:
            q["correct_answer"] = answer_map[qn]["correct_answer"]
            q["explanation"] = answer_map[qn]["explanation"]

    return questions


def _assign_images_to_questions(questions: list[dict], page_image_lists: list[list]):
    """
    Naively distribute images across questions.
    Each page's images are assigned to the question whose number
    falls closest to that page.
    """
    if not questions or not page_image_lists:
        return

    flat_images = [img for page_imgs in page_image_lists for img in page_imgs]
    questions_per_image = max(1, len(questions) // max(1, len(flat_images)))

    img_idx = 0
    for i, q in enumerate(questions):
        if img_idx < len(flat_images) and i % questions_per_image == 0:
            q["image_paths"].append(flat_images[img_idx])
            img_idx += 1
