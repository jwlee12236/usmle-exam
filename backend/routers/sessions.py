from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
import models

router = APIRouter(prefix="/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    exam_set_id: int
    time_limit_seconds: int = 4500  # 75 minutes


class SaveAnswerRequest(BaseModel):
    question_id: int
    question_number: int
    selected_answer: Optional[str] = None
    eliminated_choices: list[str] = []
    is_flagged: bool = False
    time_spent_seconds: int = 0


class SaveProgressRequest(BaseModel):
    time_remaining_seconds: int
    answers: list[SaveAnswerRequest]


@router.post("/start")
def start_session(req: StartSessionRequest, db: Session = Depends(get_db)):
    exam_set = db.query(models.ExamSet).filter(models.ExamSet.id == req.exam_set_id).first()
    if not exam_set:
        raise HTTPException(status_code=404, detail="Exam set not found")

    session = models.ExamSession(
        exam_set_id=req.exam_set_id,
        time_limit_seconds=req.time_limit_seconds,
        time_remaining_seconds=req.time_limit_seconds,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "time_limit_seconds": session.time_limit_seconds}


@router.get("/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answers = {a.question_number: a for a in session.answers}

    return {
        "session_id": session.id,
        "exam_set_id": session.exam_set_id,
        "time_limit_seconds": session.time_limit_seconds,
        "time_remaining_seconds": session.time_remaining_seconds,
        "completed": session.completed,
        "started_at": session.started_at,
        "answers": {
            qn: {
                "question_id": a.question_id,
                "selected_answer": a.selected_answer,
                "eliminated_choices": a.eliminated_choices or [],
                "is_flagged": a.is_flagged,
                "time_spent_seconds": a.time_spent_seconds,
            }
            for qn, a in answers.items()
        },
    }


@router.post("/{session_id}/save-progress")
def save_progress(session_id: int, req: SaveProgressRequest, db: Session = Depends(get_db)):
    session = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.completed:
        raise HTTPException(status_code=400, detail="Session already completed")

    session.time_remaining_seconds = req.time_remaining_seconds

    existing = {a.question_number: a for a in session.answers}

    for ans in req.answers:
        if ans.question_number in existing:
            record = existing[ans.question_number]
            record.selected_answer = ans.selected_answer
            record.eliminated_choices = ans.eliminated_choices
            record.is_flagged = ans.is_flagged
            record.time_spent_seconds = ans.time_spent_seconds
        else:
            record = models.SessionAnswer(
                session_id=session_id,
                question_id=ans.question_id,
                question_number=ans.question_number,
                selected_answer=ans.selected_answer,
                eliminated_choices=ans.eliminated_choices,
                is_flagged=ans.is_flagged,
                time_spent_seconds=ans.time_spent_seconds,
            )
            db.add(record)

    db.commit()
    return {"saved": True}


@router.post("/{session_id}/submit")
def submit_session(session_id: int, req: SaveProgressRequest, db: Session = Depends(get_db)):
    session = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save final answers
    session.time_remaining_seconds = req.time_remaining_seconds
    session.completed = True
    session.ended_at = datetime.now(timezone.utc)

    existing = {a.question_number: a for a in session.answers}
    for ans in req.answers:
        if ans.question_number in existing:
            record = existing[ans.question_number]
            record.selected_answer = ans.selected_answer
            record.eliminated_choices = ans.eliminated_choices
            record.is_flagged = ans.is_flagged
            record.time_spent_seconds = ans.time_spent_seconds
        else:
            record = models.SessionAnswer(
                session_id=session_id,
                question_id=ans.question_id,
                question_number=ans.question_number,
                selected_answer=ans.selected_answer,
                eliminated_choices=ans.eliminated_choices,
                is_flagged=ans.is_flagged,
                time_spent_seconds=ans.time_spent_seconds,
            )
            db.add(record)

    db.commit()
    return {"submitted": True, "session_id": session_id}


@router.get("/{session_id}/results")
def get_results(session_id: int, db: Session = Depends(get_db)):
    session = db.query(models.ExamSession).filter(models.ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    questions = (
        db.query(models.Question)
        .filter(models.Question.exam_set_id == session.exam_set_id)
        .order_by(models.Question.question_number)
        .all()
    )
    answers_map = {a.question_number: a for a in session.answers}

    total = len(questions)
    correct = 0
    answered = 0
    results = []

    for q in questions:
        ans = answers_map.get(q.question_number)
        selected = ans.selected_answer if ans else None
        is_correct = selected == q.correct_answer if q.correct_answer else None

        if selected:
            answered += 1
        if is_correct:
            correct += 1

        results.append({
            "question_number": q.question_number,
            "stem": q.stem,
            "choices": q.choices,
            "image_paths": q.image_paths or [],
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "selected_answer": selected,
            "is_correct": is_correct,
            "is_flagged": ans.is_flagged if ans else False,
            "eliminated_choices": ans.eliminated_choices if ans else [],
            "time_spent_seconds": ans.time_spent_seconds if ans else 0,
        })

    time_used = session.time_limit_seconds - (session.time_remaining_seconds or 0)

    return {
        "session_id": session_id,
        "exam_set_id": session.exam_set_id,
        "total": total,
        "answered": answered,
        "correct": correct,
        "score_percent": round((correct / total) * 100, 1) if total > 0 else 0,
        "time_used_seconds": time_used,
        "questions": results,
    }
