# USMLE Exam Practice

A full-stack app for practicing USMLE/NBME-style exams. Upload a PDF of exam questions, then take timed practice sessions and review your results.

Uses Claude (Haiku) to parse questions from PDFs via OCR — including clinical figures like graphs, lab tables, and images.

## Stack

- **Backend** — FastAPI, SQLAlchemy, SQLite, PyMuPDF
- **Frontend** — React 18, Vite, React Router
- **AI** — Anthropic Claude Haiku (PDF parsing + figure detection)

## Setup

### Quick start (both servers)

```bash
chmod +x start.sh
./start.sh
```

This creates a Python virtualenv, installs dependencies, and starts both servers. Open `http://localhost:5174`.

### Manual setup

**Backend**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

### Environment variables

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
ALLOWED_ORIGINS=http://localhost:5174
```

---

## Features

- **PDF upload** — upload an exam PDF and the app parses it into individual questions using Claude vision
- **Answer key** — optionally upload a separate answer key PDF to enable automatic scoring
- **Practice sessions** — start a timed session, answer questions one by one, save progress and resume later
- **Results** — see your score, review correct/incorrect answers, and read explanations
- **Figure detection** — Claude automatically detects clinical figures (graphs, lab values, images) embedded in question pages

---

## API

Docs available at `http://localhost:8002/docs` when the backend is running.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/exams` | List all exam sets |
| POST | `/exams/upload` | Upload and parse a question PDF |
| GET | `/exams/upload-status/{job_id}` | Check async upload status |
| POST | `/exams/{id}/upload-answer-key` | Upload an answer key PDF |
| GET | `/exams/{id}/questions` | List questions for an exam |
| GET | `/exams/{id}/page/{page_num}` | Get a specific question page |
| DELETE | `/exams/{id}` | Delete an exam set |
| POST | `/sessions/start` | Start a new practice session |
| GET | `/sessions/{id}` | Get session state |
| POST | `/sessions/{id}/save-progress` | Save in-progress answers |
| POST | `/sessions/{id}/submit` | Submit and score a session |
| GET | `/sessions/{id}/results` | Get session results |

---

## Project structure

```
usmle-exam/
├── backend/
│   ├── main.py             ← FastAPI app, CORS, routing
│   ├── models.py           ← SQLAlchemy models
│   ├── database.py         ← DB connection setup
│   ├── routers/
│   │   ├── exams.py        ← Exam upload and question endpoints
│   │   └── sessions.py     ← Practice session endpoints
│   └── services/
│       ├── pdf_parser.py   ← PDF → questions via Claude OCR
│       └── vision.py       ← Figure detection via Claude vision
├── frontend/
│   ├── src/                ← React components and pages
│   └── vite.config.js
├── start.sh                ← One-command dev startup
└── render.yaml             ← Render deployment config
```
