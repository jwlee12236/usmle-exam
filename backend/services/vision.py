"""
Uses Claude Haiku to detect whether a PDF page contains a clinical figure
(graph, chart, lab table, image) and returns its bounding box if so.
"""
import os
import base64
import json
from pathlib import Path
from dotenv import load_dotenv
import fitz
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env")

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

_OCR_PROMPT = """\
This is a screenshot of a USMLE/NBME exam question.{hint}

Extract the question and return it in EXACTLY this format with no other text:
{number}. [full question stem]
A. [choice A]
B. [choice B]
C. [choice C]
D. [choice D]
E. [choice E]

Preserve all medical terminology, numbers, units, and symbols exactly. \
Include every answer choice shown. Do not include any UI chrome (header, navigation buttons, etc.)."""

_OCR_ANSWER_PROMPT = """\
This is a screenshot of a USMLE/NBME answer key question.{hint}

Extract the question and identify the correct answer (it may be visually highlighted, \
bolded, checked, or marked in any way).

Return in EXACTLY this format with no other text:
{number}. [full question stem]
A. [choice A]
B. [choice B]
C. [choice C]
D. [choice D]
E. [choice E]
Correct Answer: [single letter of correct answer]

Preserve all medical terminology exactly. Do not include UI chrome."""

_PROMPT = """This is a page from a medical exam (USMLE/NBME style).

Does this page contain a clinical figure embedded within the question — such as:
- A graph or chart (fetal heart rate tracing, basal body temperature chart, growth curve, etc.)
- A table of lab values (two-column layout with lab test names on the left and values on the right)
- A medical image (X-ray, CT, MRI, histology slide, photograph)

Do NOT count the question stem text, answer choices, or UI navigation (Previous/Next/Help buttons) as figures.

If a clinical figure IS present, return a bounding box that FULLY contains it:
- Include ALL labels, axes, column headers, and values — err large, not small
- For lab tables: x must start at or before the leftmost character of the left column (lab names), NOT the right column (values)
- For graphs: include the full y-axis label on the left and all x-axis tick marks on the right/bottom

Return JSON:
{"has_figure": true, "bbox": [x, y, width, height]}

Where x, y, width, height are pixel coordinates (x=0, y=0 is top-left corner).

If no clinical figure is present:
{"has_figure": false}

Return ONLY valid JSON, no other text."""


_TARGETED_ANSWER_PROMPT = """\
This is a page from a USMLE/NBME answer key.

Tell me:
1. The question number (look for "Item N of 50", a header, or the number at the start of the question)
2. The correct answer letter — it may appear as "Correct Answer: X", or be highlighted/circled/bolded among the answer choices

Reply in EXACTLY this format (nothing else):
Q[number] [letter]

Examples: "Q23 E"  or  "Q7 B"

If this page has no question (just explanation text), reply: none
If you see the question but truly cannot determine the correct answer, reply: Q[number] unknown"""


def extract_answer_from_page(page: fitz.Page) -> tuple[int, str] | None:
    """
    Targeted extraction: returns (question_number, answer_letter) or None.
    Uses a tiny max_tokens budget — fast and low-memory.
    """
    import re
    pix = page.get_pixmap(dpi=72)
    img_bytes = pix.tobytes("png")
    pix = None
    img_b64 = base64.standard_b64encode(img_bytes).decode()
    img_bytes = None

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": _TARGETED_ANSWER_PROMPT},
            ],
        }],
    )
    img_b64 = None
    text = response.content[0].text.strip()
    m = re.match(r'Q(\d+)\s+([A-Z])\b', text, re.IGNORECASE)
    if m:
        return int(m.group(1)), m.group(2).upper()
    return None


def ocr_page(page: fitz.Page, hint_number: int | None = None, has_answers: bool = False) -> str:
    """Render page as image and extract USMLE question text with Claude Haiku."""
    pix = page.get_pixmap(dpi=100)
    img_bytes = pix.tobytes("png")
    pix = None  # release pixmap memory
    img_b64 = base64.standard_b64encode(img_bytes).decode()
    img_bytes = None

    if hint_number is not None:
        hint = f" This is question number {hint_number}."
        number = str(hint_number)
    else:
        hint = " Identify the question number from the image and use it in the output."
        number = "[N]"

    prompt_template = _OCR_ANSWER_PROMPT if has_answers else _OCR_PROMPT
    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": prompt_template.format(hint=hint, number=number)},
            ],
        }],
    )
    return response.content[0].text.strip()


def detect_figure_on_page(page: fitz.Page) -> dict | None:
    """
    Render the page, downscale to 800px wide for Claude, then scale the returned
    bbox back up to native page-pixel coordinates.
    Returns {"x": int, "y": int, "w": int, "h": int} in page coords, or None.
    """
    from PIL import Image
    import io

    # Render at native res (72 DPI = 1pt/px for this screenshot PDF)
    pix = page.get_pixmap(dpi=72)
    native_w, native_h = pix.width, pix.height

    # Downscale to 800px wide so Claude can reason more accurately about layout
    target_w = 800
    scale = target_w / native_w
    target_h = int(native_h * scale)

    img = Image.frombytes("RGB", (native_w, native_h), pix.samples)
    pix = None  # release pixmap memory
    img_small = img.resize((target_w, target_h), Image.LANCZOS)
    img = None  # release original image

    buf = io.BytesIO()
    img_small.save(buf, format="PNG")
    img_small = None  # release resized image
    img_b64 = base64.standard_b64encode(buf.getvalue()).decode()
    buf = None

    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": _PROMPT + f"\n\nThe image is {target_w}x{target_h} pixels.",
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    if not result.get("has_figure"):
        return None

    bbox = result.get("bbox")
    if not bbox or len(bbox) != 4:
        return None

    # Scale bbox from downscaled image coords back to native page coords
    x, y, w, h = bbox
    return {
        "x": int(x / scale),
        "y": int(y / scale),
        "w": int(w / scale),
        "h": int(h / scale),
    }
