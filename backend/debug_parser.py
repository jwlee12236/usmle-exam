"""
Run from backend/ dir:  python debug_parser.py <path_to_pdf>
Prints every candidate question boundary found and whether it was accepted/skipped.
"""
import sys
import re
import fitz

QUESTION_START_RE = re.compile(r"^(\d\s?\d?)\s*\.\s+(.*)")

def main(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text")
    doc.close()

    lines = full_text.split("\n")
    current_num = 0
    accepted = []
    skipped = []

    for i, line in enumerate(lines):
        ls = line.lstrip().rstrip()
        m = QUESTION_START_RE.match(ls)
        if m:
            q_num = int(m.group(1).replace(" ", ""))
            rest = m.group(2)[:60]  # first 60 chars of question text
            if q_num > current_num:
                accepted.append((q_num, rest, i))
                current_num = q_num
            else:
                skipped.append((q_num, rest, i, f"current={current_num}"))

    print(f"\n=== ACCEPTED ({len(accepted)}) ===")
    for q_num, rest, lineno in accepted:
        print(f"  Q{q_num:2d} (line {lineno:4d}): {rest}")

    print(f"\n=== SKIPPED ({len(skipped)}) ===")
    for q_num, rest, lineno, reason in skipped:
        print(f"  Q{q_num:2d} (line {lineno:4d}) [{reason}]: {rest}")

    # Show which question numbers are missing from accepted
    found_nums = {q for q, _, _ in accepted}
    if found_nums:
        expected = set(range(min(found_nums), max(found_nums) + 1))
        missing = sorted(expected - found_nums)
        if missing:
            print(f"\n=== MISSING from sequence: {missing} ===")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_parser.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
