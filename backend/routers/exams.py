import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
import fitz
from database import get_db, SessionLocal
import models
from services.pdf_parser import extract_questions_from_pdf

router = APIRouter(prefix="/exams", tags=["exams"])

UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job store (single worker, so this is safe)
_jobs: dict = {}


def _process_answer_key(job_id: str, pdf_path: str, exam_set_id: int):
    db = SessionLocal()
    try:
        parsed = extract_questions_from_pdf(pdf_path, exam_set_id, has_answers=True)
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

        exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
        exam_set.answer_pdf_path = pdf_path
        db.commit()
        _jobs[job_id] = {"status": "done", "updated_questions": updated}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "error": str(e)}
    finally:
        db.close()


def _process_upload(job_id: str, pdf_path: str, exam_set_id: int):
    db = SessionLocal()
    try:
        parsed_questions = extract_questions_from_pdf(pdf_path, exam_set_id)
        if not parsed_questions:
            exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
            if exam_set:
                db.delete(exam_set)
                db.commit()
            _jobs[job_id] = {"status": "error", "error": "No questions found in PDF. Check the file format."}
            return

        for q in parsed_questions:
            db.add(models.Question(
                exam_set_id=exam_set_id,
                question_number=q["question_number"],
                stem=q["stem"],
                choices=q["choices"],
                image_paths=q.get("image_paths", []),
                pdf_page=q.get("pdf_page"),
                correct_answer=q.get("correct_answer"),
                explanation=q.get("explanation"),
            ))

        exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
        exam_set.total_questions = len(parsed_questions)
        db.commit()
        _jobs[job_id] = {"status": "done", "exam_set_id": exam_set_id}
    except Exception as e:
        import traceback
        print(f"[upload error] exam_set_id={exam_set_id}: {e}\n{traceback.format_exc()}")
        try:
            exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == exam_set_id).first()
            if exam_set:
                db.delete(exam_set)
                db.commit()
        except Exception:
            pass
        _jobs[job_id] = {"status": "error", "error": str(e)}
    finally:
        db.close()


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
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    question_pdf: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    pdf_filename = f"{name.replace(' ', '_')}_{question_pdf.filename}"
    pdf_path = UPLOADS_DIR / pdf_filename
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(question_pdf.file, f)

    exam_set = models.ExamSet(name=name, question_pdf_path=str(pdf_path))
    db.add(exam_set)
    db.commit()
    db.refresh(exam_set)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "exam_set_id": None, "error": None}
    background_tasks.add_task(_process_upload, job_id, str(pdf_path), exam_set.id)

    return {"job_id": job_id}


@router.get("/upload-status/{job_id}")
def upload_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{exam_set_id}/upload-answer-key")
async def upload_answer_key(
    exam_set_id: int,
    background_tasks: BackgroundTasks,
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

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing", "updated_questions": None, "error": None}
    background_tasks.add_task(_process_answer_key, job_id, str(pdf_path), exam_set_id)

    return {"job_id": job_id}


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
