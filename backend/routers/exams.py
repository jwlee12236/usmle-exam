import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
import fitz
from database import get_db
import models
from services.pdf_parser import extract_questions_from_pdf

router = APIRouter(prefix="/exams", tags=["exams"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/")
def list_exam_sets(db: Session = Depends(get_db)):
    sets = db.query(models.ExamSet).order_by(models.ExamSet.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "total_questions": s.total_questions,
            "has_answer_key": s.answer_pdf_path is not None,
            "created_at": s.created_at,
        }
        for s in sets
    ]


@router.post("/upload")
async def upload_exam(
    name: str = Form(...),
    question_pdf: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Save uploaded PDF
    pdf_filename = f"{name.replace(' ', '_')}_{question_pdf.filename}"
    pdf_path = UPLOADS_DIR / pdf_filename
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(question_pdf.file, f)

    # Create exam set record first to get ID for image naming
    exam_set = models.ExamSet(name=name, question_pdf_path=str(pdf_path))
    db.add(exam_set)
    db.commit()
    db.refresh(exam_set)

    # Parse PDF
    try:
        parsed_questions = extract_questions_from_pdf(str(pdf_path), exam_set.id)
    except Exception as e:
        db.delete(exam_set)
        db.commit()
        raise HTTPException(status_code=422, detail=f"PDF parsing failed: {str(e)}")

    if not parsed_questions:
        db.delete(exam_set)
        db.commit()
        raise HTTPException(status_code=422, detail="No questions found in PDF. Check the file format.")

    # Store questions
    for q in parsed_questions:
        question = models.Question(
            exam_set_id=exam_set.id,
            question_number=q["question_number"],
            stem=q["stem"],
            choices=q["choices"],
            image_paths=q.get("image_paths", []),
            pdf_page=q.get("pdf_page"),
            correct_answer=q.get("correct_answer"),
            explanation=q.get("explanation"),
        )
        db.add(question)

    exam_set.total_questions = len(parsed_questions)
    db.commit()

    return {"id": exam_set.id, "name": name, "total_questions": len(parsed_questions)}


@router.post("/{exam_set_id}/upload-answer-key")
async def upload_answer_key(
    exam_set_id: int,
    answer_pdf: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
    if not exam_set:
        raise HTTPException(status_code=404, detail="Exam set not found")

    pdf_filename = f"answers_{exam_set_id}_{answer_pdf.filename}"
    pdf_path = UPLOADS_DIR / pdf_filename
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(answer_pdf.file, f)

    try:
        parsed = extract_questions_from_pdf(str(pdf_path), exam_set_id, has_answers=True)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Answer key parsing failed: {str(e)}")

    # Update existing questions with correct answers and explanations
    updated = 0
    for q_data in parsed:
        if not q_data.get("correct_answer"):
            continue
        question = (
            db.query(models.Question)
            .filter(
                models.Question.exam_set_id == exam_set_id,
                models.Question.question_number == q_data["question_number"],
            )
            .first()
        )
        if question:
            question.correct_answer = q_data["correct_answer"]
            question.explanation = q_data.get("explanation", "")
            updated += 1

    exam_set.answer_pdf_path = str(pdf_path)
    db.commit()

    return {"updated_questions": updated}


@router.get("/{exam_set_id}/questions")
def get_questions(exam_set_id: int, db: Session = Depends(get_db)):
    exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
    if not exam_set:
        raise HTTPException(status_code=404, detail="Exam set not found")

    questions = (
        db.query(models.Question)
        .filter(models.Question.exam_set_id == exam_set_id)
        .order_by(models.Question.question_number)
        .all()
    )
    return [
        {
            "id": q.id,
            "question_number": q.question_number,
            "stem": q.stem,
            "choices": q.choices,
            "image_paths": q.image_paths or [],
            "pdf_page": q.pdf_page,
            "has_answer": q.correct_answer is not None,
        }
        for q in questions
    ]


@router.get("/{exam_set_id}/page/{page_num}")
def render_page(exam_set_id: int, page_num: int, db: Session = Depends(get_db)):
    """Render a single PDF page as a PNG, stripping header/footer chrome."""
    exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
    if not exam_set or not exam_set.question_pdf_path:
        raise HTTPException(status_code=404, detail="Exam set not found")

    _HEADER_KW = {'exam section', 'national board', 'time remaining', '■ mark', 'obstetrics'}
    _FOOTER_KW = {'previous', 'next', 'lab values', 'help', 'pause', 'https://'}

    doc = fitz.open(exam_set.question_pdf_path)
    if page_num < 0 or page_num >= len(doc):
        doc.close()
        raise HTTPException(status_code=404, detail="Page not found")

    page = doc[page_num]
    pr = page.rect

    header_bottom = pr.height * 0.05
    footer_top = pr.height * 0.95
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        txt_lo = b[4].strip().lower()
        if any(kw in txt_lo for kw in _HEADER_KW):
            header_bottom = max(header_bottom, b[3])
        if b[1] > pr.height * 0.80 and any(kw in txt_lo for kw in _FOOTER_KW):
            footer_top = min(footer_top, b[1])

    clip = fitz.Rect(0, header_bottom, pr.width, footer_top)
    pix = page.get_pixmap(dpi=72, clip=clip)
    doc.close()

    return Response(content=pix.tobytes("png"), media_type="image/png")


@router.delete("/{exam_set_id}")
def delete_exam_set(exam_set_id: int, db: Session = Depends(get_db)):
    exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
    if not exam_set:
        raise HTTPException(status_code=404, detail="Exam set not found")
    db.delete(exam_set)
    db.commit()
    return {"deleted": True}
