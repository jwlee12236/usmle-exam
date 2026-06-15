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

# Regex to detect answer choices after text cleaning normalizes them to "A. text".
# Covers A–Z to handle NBME Extended Matching Question banks that go up to N.
CHOICE_RE = re.compile(r"^([A-Z])\.\s+(.+)$")

# Junk lines from screenshotted NBME/UWorld interfaces that appear between questions
_JUNK_EXACT = {
    'previous', 'next', 'help', 'pause',
    'lab values calculator review',
    'national board of medical examiners',
    'time remaining:',
    '■ mark', 'mark',
    'obstetrics and gynecology self-assessment',
    'gynecology and obstetrics self-assessment',
    ',',    # lone comma — navigation separator artifact (e.g. "P , r ,")
    '.',    # lone period — punctuation artifact after last choice
    ',.',   # comma+period artifact (e.g. page 17 line 32: ",. ")
    'p',    # disabled "Previous" button extracted as bare "P" on page 1
    'on admission',          # multi-column table column header
    'now',                   # multi-column table column header (e.g. "Now" column)
}
_JUNK_RE = re.compile(
    r'^([Q0Oo]|r|~|~\s*p,?\s*r,?|https?://\S+|exam section\s*:.*'
    r'|\d+\s*hr\s*\d+\s*min\s*\d+\s*sec|item\s+\d+\s+of\s+\d+'
    r'|[\w\s\-]+self.?assessment'
    r'|\d+\s+\w+\s+after\s+\w+'   # e.g. "2 Days After Admission" column header
    r')$',
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

# Lab table detection: PDF column extraction puts all names first, then all values.
# Name lines: letters/spaces/hyphens only (no leading digit).
# Value lines: number (possibly with commas/decimals) followed by a unit.
_LAB_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9\s\-\+\(\)/²³µ°±]{1,59}$')
_LAB_VALUE_RE = re.compile(r'^[><=]?[\d,]+\.?\d*\s*[a-zA-Z%/µ³·]+')

# Stem phrases that indicate a question contains a clinical image/figure that must be shown
_VISUAL_RE = re.compile(
    r'\b(shown|tracing|graph|figure|photograph|radiograph|x[\s-]?ray|mri|ct scan'
    r'|ecg|ekg|electrocardiogram|histolog|slide|biopsy|image|scan)\b',
    re.IGNORECASE,
)


def _format_lab_tables(stem: str) -> str:
    """
    PDF column extraction puts all lab-test names first, then all values as separate lines.
    Detect runs of N name-only lines followed by N value lines (N >= 2) and interleave them
    as "Name: Value" pairs so the stem reads naturally.
    """
    lines = stem.split('\n')
    out = []
    i = 0
    while i < len(lines):
        ls = lines[i].strip()
        if _LAB_NAME_RE.match(ls):
            # Gather consecutive name-only lines
            names, j = [], i
            while j < len(lines) and _LAB_NAME_RE.match(lines[j].strip()):
                names.append(lines[j].strip())
                j += 1
            # Gather consecutive value lines immediately after
            values, k = [], j
            while k < len(lines) and _LAB_VALUE_RE.match(lines[k].strip()):
                values.append(lines[k].strip())
                k += 1
            if len(names) >= 2 and len(names) == len(values):
                for name, value in zip(names, values):
                    out.append(f"{name}: {value}")
                i = k
                continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)


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
            if re.match(r'^[A-Z][.)]\s+', next_ls):
                i += 1
                continue

        cleaned.append(lines[i])
        i += 1

    text = '\n'.join(cleaned)

    # Normalize "Q A) text" / "0 A) text" → "A. text" (EMQ banks go up to N+)
    text = re.sub(r'(?m)^[Q0Oo]\s+([A-Z])[.)]\s+', r'\1. ', text)
    # Normalize bare "A) text" → "A. text"
    text = re.sub(r'(?m)^([A-Z])\)\s+', r'\1. ', text)

    # Fix 1: Join standalone question numbers with the line that follows them.
    # Some PDFs render "31 .\nThree days after..." (number alone, text on next line).
    # QUESTION_START_RE needs text after the period, so we collapse these here.
    text = re.sub(r'(?m)^(\d{1,2})\s*\.\s*\n', r'\1. ', text)

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


def _fill_gap(
    doc: fitz.Document,
    gap_qn: int,
    question_page: dict,
    page_to_q: dict,
    questions_map: dict,
    ocr_structured,
) -> None:
    """Re-OCR candidate pages between known neighbors to recover a missing question."""
    lower_q = max((q for q in question_page if q < gap_qn), default=None)
    upper_q = min((q for q in question_page if q > gap_qn), default=None)

    if lower_q is not None and upper_q is not None:
        lo, hi = question_page[lower_q], question_page[upper_q]
        candidates = [p for p in range(lo + 1, hi) if p not in page_to_q]
    elif lower_q is not None:
        lo = question_page[lower_q]
        candidates = [p for p in [lo + 1, lo + 2] if p < len(doc) and p not in page_to_q]
    elif upper_q is not None:
        hi = question_page[upper_q]
        candidates = [p for p in [hi - 1, hi - 2] if p >= 0 and p not in page_to_q]
    else:
        return

    for page_num in candidates:
        try:
            sq = ocr_structured(doc[page_num], gap_qn)
        except Exception:
            sq = None
        gc.collect()
        fitz.TOOLS.store_shrink(100)
        if sq and sq["question_number"] == gap_qn:
            questions_map[gap_qn] = {
                "question_number": gap_qn,
                "stem": sq["stem"],
                "choices": sq["choices"],
                "image_paths": [],
            }
            question_page[gap_qn] = page_num
            page_to_q[page_num] = gap_qn
            print(f"  Gap-fill: Q{gap_qn} recovered from page {page_num}")
            return

    print(f"  Gap-fill: Q{gap_qn} not found in {len(candidates)} candidate page(s)")


def extract_questions_from_pdf(pdf_path: str, exam_set_id: int, has_answers: bool = False) -> list[dict]:
    from services.vision import detect_figure_on_page, ocr_page, ocr_page_structured  # lazy import to avoid startup cost

    doc = fitz.open(pdf_path)

    # --- Answer key: two-phase approach (text pass → targeted OCR for gaps) ---
    if has_answers:
        from services.vision import extract_answer_from_page
        fmt = _detect_answer_key_format(doc)
        print(f"Answer key format: {fmt} ({len(doc)} pages)")

        if fmt == "compact":
            full_text = "".join(page.get_text("text") + "\n" for page in doc)
            doc.close()
            return _parse_compact_answers(full_text)

        # Phase 1: pure text extraction — no API calls
        answer_map: dict[int, str] = {}   # question_num -> answer_letter
        page_for_q: dict[int, int] = {}   # question_num -> page_num (for OCR fallback)

        _answer_re = re.compile(
            r"(?:Correct answer|Answer|The correct answer is)[:\s]+([A-G])\b",
            re.IGNORECASE,
        )

        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            # Track which question is on this page
            for line in page_text.split("\n"):
                m = QUESTION_START_RE.match(line.lstrip().rstrip())
                if m:
                    qn = int(m.group(1).replace(" ", ""))
                    if qn not in page_for_q:
                        page_for_q[qn] = page_num
                    break
            # Extract answer from text if present
            ans_m = _answer_re.search(page_text)
            if ans_m:
                # Associate with question number found on this page (or previous)
                current_q = None
                for line in page_text.split("\n"):
                    m = QUESTION_START_RE.match(line.lstrip().rstrip())
                    if m:
                        current_q = int(m.group(1).replace(" ", ""))
                        break
                if current_q:
                    answer_map[current_q] = ans_m.group(1).upper()

        # Phase 2: targeted OCR only for pages we couldn't get from text
        if fmt == "image_only":
            # All pages need OCR — check every page
            pages_to_check = list(range(len(doc)))
        else:
            # Standard: only OCR the pages of questions still missing answers
            missing_qnums = set(page_for_q.keys()) - set(answer_map.keys())
            pages_to_check = [page_for_q[qn] for qn in missing_qnums if qn in page_for_q]
            # Also check pages not mapped to any question (might have answers we missed)
            mapped_pages = set(page_for_q.values())
            for pnum in range(len(doc)):
                if pnum not in mapped_pages:
                    pages_to_check.append(pnum)

        print(f"Targeted OCR: {len(pages_to_check)} pages")
        for pnum in pages_to_check:
            try:
                result = extract_answer_from_page(doc[pnum])
                if result:
                    qn, letter = result
                    if qn not in answer_map:
                        answer_map[qn] = letter
                        print(f"  OCR page {pnum} → Q{qn}: {letter}")
            except Exception as e:
                print(f"  OCR failed page {pnum}: {e}")
            gc.collect()
            fitz.TOOLS.store_shrink(100)

        doc.close()
        return [
            {"question_number": qn, "correct_answer": letter, "stem": "", "choices": {}}
            for qn, letter in sorted(answer_map.items())
        ]

    # --- Question PDF ---
    page_texts: list[str] = []
    structured_questions: dict[int, dict] = {}   # qn → {stem, choices} from structured OCR
    question_page: dict[int, int] = {}           # question_number → page_num

    for page_num, page in enumerate(doc):
        page_text = page.get_text("text")

        if _page_is_image_based(page_text):
            item_m = _ITEM_NUM_RE.search(page_text)
            hint_num = int(item_m.group(1)) if item_m else None

            sq = None
            try:
                sq = ocr_page_structured(page, hint_num)
            except Exception as e:
                print(f"Structured OCR failed page {page_num}: {e}")

            if sq:
                qn = sq["question_number"]
                structured_questions[qn] = sq
                question_page[qn] = page_num
                print(f"Structured OCR page {page_num} → Q{qn}")
            else:
                # Fall back to plain OCR → regex parse
                try:
                    page_text = ocr_page(page, hint_num)
                    print(f"OCR fallback page {page_num} (Q{hint_num}): {page_text[:80]}")
                except Exception as e:
                    print(f"OCR failed page {page_num}: {e}")
                    page_text = ""
                for line in page_text.split("\n"):
                    m = QUESTION_START_RE.match(line.lstrip().rstrip())
                    if m:
                        qn = int(m.group(1).replace(" ", ""))
                        if qn not in question_page:
                            question_page[qn] = page_num
                        break
                page_texts.append(page_text)

            gc.collect()
            fitz.TOOLS.store_shrink(100)
        else:
            for line in page_text.split("\n"):
                m = QUESTION_START_RE.match(line.lstrip().rstrip())
                if m:
                    qn = int(m.group(1).replace(" ", ""))
                    if qn not in question_page:
                        question_page[qn] = page_num
                    break
            page_texts.append(page_text)

    # Parse text-based and OCR-fallback pages via regex
    full_text = _clean_pdf_text("\n".join(page_texts))
    page_texts.clear()
    text_questions = _parse_questions_only(full_text, {})

    # Structured (JSON) questions take priority over regex-parsed ones
    questions_map: dict[int, dict] = {q["question_number"]: q for q in text_questions}
    for qn, sq in structured_questions.items():
        questions_map[qn] = {
            "question_number": qn,
            "stem": sq["stem"],
            "choices": sq["choices"],
            "image_paths": [],
        }

    # Gap detection: find missing numbers and re-OCR candidate pages
    if questions_map:
        found = set(questions_map.keys())
        missing = sorted(set(range(min(found), max(found) + 1)) - found)
        if missing:
            print(f"Gap detection: missing questions {missing}")
            page_to_q = {v: k for k, v in question_page.items()}
            for gap_qn in missing:
                _fill_gap(doc, gap_qn, question_page, page_to_q, questions_map, ocr_page_structured)

    questions = sorted(questions_map.values(), key=lambda q: q["question_number"])

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
        fitz.TOOLS.store_shrink(100)

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
                    current_q["stem"] = _format_lab_tables(current_q["stem"].strip())
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
            letter = choice_match.group(1)
            # Fix 2: Extended choices (H+) are only accepted once already in the choices
            # section. This prevents stem sentences starting with a capital letter + ". "
            # from being misread as a choice before any A-G choices have been seen.
            if letter <= 'G' or current_section == "choices":
                current_section = "choices"
                current_q["choices"][letter] = choice_match.group(2).strip()
            elif _MEANINGFUL_RE.search(ls):
                current_q["stem"] += ls + "\n"
        elif current_section == "stem" and ls and _MEANINGFUL_RE.search(ls):
            # Only add lines that contain real words or lab values — drops chart/graph noise
            current_q["stem"] += ls + "\n"
        # NBME choices are always single-line — do not append post-choice content.
        # Table chrome (second column values, column headers) appears after choices
        # in the PDF text layer and must not bleed into the last answer choice.

    if current_q:
        current_q["stem"] = _format_lab_tables(current_q["stem"].strip())
        questions.append(current_q)

    # Fix 3: EMQ follow-on propagation.
    # In NBME Extended Matching Questions the lead question (e.g. Q15) carries choices
    # A–H; follow-ons (Q16, Q17) share that bank and have no choices of their own.
    # Any question that parsed with zero choices inherits the preceding question's bank.
    for i in range(1, len(questions)):
        if not questions[i]["choices"] and questions[i - 1]["choices"]:
            questions[i]["choices"] = dict(questions[i - 1]["choices"])

    # Sort choices alphabetically. Two-column EMQ PDFs extract as A,J,B,K,C,L...
    # due to column-order text extraction; sort restores the expected A,B,C... order.
    for q in questions:
        q["choices"] = dict(sorted(q["choices"].items()))

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
