from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ExamSet(Base):
    __tablename__ = "exam_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    question_pdf_path = Column(String)
    answer_pdf_path = Column(String, nullable=True)
    total_questions = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("Question", back_populates="exam_set", cascade="all, delete-orphan")
    sessions = relationship("ExamSession", back_populates="exam_set", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_set_id = Column(Integer, ForeignKey("exam_sets.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    stem = Column(Text, nullable=False)
    choices = Column(JSON, nullable=False)  # {"A": "text", "B": "text", ...}
    correct_answer = Column(String, nullable=True)  # "A", "B", etc.
    explanation = Column(Text, nullable=True)
    image_paths = Column(JSON, nullable=True)  # list of image file paths
    pdf_page = Column(Integer, nullable=True)  # 0-based page index in the source PDF

    exam_set = relationship("ExamSet", back_populates="questions")


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    exam_set_id = Column(Integer, ForeignKey("exam_sets.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    time_limit_seconds = Column(Integer, default=4500)  # 75 minutes
    time_remaining_seconds = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)

    exam_set = relationship("ExamSet", back_populates="sessions")
    answers = relationship("SessionAnswer", back_populates="session", cascade="all, delete-orphan")


class SessionAnswer(Base):
    __tablename__ = "session_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    selected_answer = Column(String, nullable=True)
    eliminated_choices = Column(JSON, default=list)  # ["A", "C"]
    is_flagged = Column(Boolean, default=False)
    time_spent_seconds = Column(Integer, default=0)

    session = relationship("ExamSession", back_populates="answers")
    question = relationship("Question")
