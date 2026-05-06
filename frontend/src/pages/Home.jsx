import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'

export default function Home() {
  const navigate = useNavigate()
  const [examSets, setExamSets] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadingAnswers, setUploadingAnswers] = useState(null)
  const [examName, setExamName] = useState('')
  const [questionFile, setQuestionFile] = useState(null)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(null)

  useEffect(() => {
    fetchExamSets()
  }, [])

  const fetchExamSets = async () => {
    const res = await api.get('/exams/')
    setExamSets(res.data)
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!questionFile || !examName.trim()) {
      setError('Please provide a name and select a PDF file.')
      return
    }
    setError('')
    setUploading(true)
    const form = new FormData()
    form.append('name', examName.trim())
    form.append('question_pdf', questionFile)
    try {
      const { data } = await api.post('/exams/upload', form)
      const { job_id } = data

      // Poll for completion
      await new Promise((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const { data: job } = await api.get(`/exams/upload-status/${job_id}`)
            if (job.status === 'done') {
              clearInterval(interval)
              resolve()
            } else if (job.status === 'error') {
              clearInterval(interval)
              reject(new Error(job.error || 'Upload failed.'))
            }
          } catch (err) {
            clearInterval(interval)
            reject(err)
          }
        }, 3000)
      })

      setExamName('')
      setQuestionFile(null)
      fetchExamSets()
    } catch (err) {
      setError(err.message || err.response?.data?.detail || 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleAnswerKeyUpload = async (examSetId, file) => {
    setUploadingAnswers(examSetId)
    const form = new FormData()
    form.append('answer_pdf', file)
    try {
      const { data } = await api.post(`/exams/${examSetId}/upload-answer-key`, form)
      const { job_id } = data

      await new Promise((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const { data: job } = await api.get(`/exams/upload-status/${job_id}`)
            if (job.status === 'done') {
              clearInterval(interval)
              resolve()
            } else if (job.status === 'error') {
              clearInterval(interval)
              reject(new Error(job.error || 'Answer key upload failed.'))
            }
          } catch (err) {
            clearInterval(interval)
            reject(err)
          }
        }, 3000)
      })

      fetchExamSets()
    } catch (err) {
      alert(err.message || err.response?.data?.detail || 'Answer key upload failed.')
    } finally {
      setUploadingAnswers(null)
    }
  }

  const startExam = async (examSetId) => {
    setStarting(examSetId)
    try {
      const res = await api.post('/sessions/start', { exam_set_id: examSetId })
      navigate(`/exam/${res.data.session_id}`)
    } catch {
      alert('Failed to start exam.')
    } finally {
      setStarting(null)
    }
  }

  const deleteExam = async (id) => {
    if (!confirm('Delete this exam set? This cannot be undone.')) return
    await api.delete(`/exams/${id}`)
    fetchExamSets()
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>USMLE Exam Practice</h1>
        <p style={styles.subtitle}>Upload a question PDF to start a timed practice session</p>
      </div>

      <div style={styles.content}>
        {/* Upload Form */}
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>Upload New Exam Set</h2>
          <form onSubmit={handleUpload} style={styles.form}>
            <label style={styles.label}>Exam Name</label>
            <input
              type="text"
              placeholder="e.g. USMLE Step 1 Block 3"
              value={examName}
              onChange={(e) => setExamName(e.target.value)}
              style={styles.input}
            />
            <label style={styles.label}>Question PDF</label>
            <input
              type="file"
              accept=".pdf"
              onChange={(e) => setQuestionFile(e.target.files[0])}
              style={styles.fileInput}
            />
            {error && <div style={styles.error}>{error}</div>}
            <button type="submit" disabled={uploading} style={styles.btn}>
              {uploading ? 'Processing... (may take a few minutes)' : 'Upload & Parse'}
            </button>
          </form>
        </div>

        {/* Exam Sets List */}
        {examSets.length > 0 && (
          <div style={styles.card}>
            <h2 style={styles.cardTitle}>Your Exam Sets</h2>
            <div style={styles.examList}>
              {examSets.map((set) => (
                <div key={set.id} style={styles.examRow}>
                  <div style={styles.examInfo}>
                    <div style={styles.examName}>{set.name}</div>
                    <div style={styles.examMeta}>
                      {set.total_questions} questions
                      {set.has_answer_key && (
                        <span style={styles.answerKeyBadge}>✓ Answer Key</span>
                      )}
                    </div>
                  </div>
                  <div style={styles.examActions}>
                    {!set.has_answer_key && (
                      <label style={styles.uploadAnswerBtn}>
                        {uploadingAnswers === set.id ? 'Uploading...' : '+ Answer Key'}
                        <input
                          type="file"
                          accept=".pdf"
                          style={{ display: 'none' }}
                          onChange={(e) => handleAnswerKeyUpload(set.id, e.target.files[0])}
                        />
                      </label>
                    )}
                    <button
                      onClick={() => startExam(set.id)}
                      disabled={starting === set.id}
                      style={styles.startBtn}
                    >
                      {starting === set.id ? 'Starting...' : 'Start Exam'}
                    </button>
                    <button onClick={() => deleteExam(set.id)} style={styles.deleteBtn}>
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    background: '#f3f6fb',
  },
  header: {
    background: '#1a3a5c',
    color: '#fff',
    padding: '40px 0 32px',
    textAlign: 'center',
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    opacity: 0.8,
  },
  content: {
    maxWidth: 720,
    margin: '0 auto',
    padding: '32px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
  },
  card: {
    background: '#fff',
    borderRadius: 10,
    padding: 28,
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 700,
    marginBottom: 20,
    color: '#1a3a5c',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  label: {
    fontSize: 13,
    fontWeight: 600,
    color: '#444',
  },
  input: {
    padding: '10px 14px',
    border: '1px solid #ddd',
    borderRadius: 6,
    fontSize: 14,
    outline: 'none',
  },
  fileInput: {
    fontSize: 13,
    color: '#444',
  },
  error: {
    color: '#c0392b',
    fontSize: 13,
    background: '#fdf2f2',
    padding: '8px 12px',
    borderRadius: 4,
  },
  btn: {
    background: '#1a3a5c',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    padding: '11px 0',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 4,
  },
  examList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  examRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 16px',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
  },
  examInfo: {},
  examName: {
    fontWeight: 600,
    fontSize: 15,
    marginBottom: 3,
  },
  examMeta: {
    fontSize: 12,
    color: '#888',
    display: 'flex',
    gap: 10,
    alignItems: 'center',
  },
  answerKeyBadge: {
    background: '#dcfce7',
    color: '#16a34a',
    padding: '2px 8px',
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 600,
  },
  examActions: {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  uploadAnswerBtn: {
    background: '#f0f9ff',
    border: '1px solid #93c5fd',
    color: '#2563eb',
    borderRadius: 5,
    padding: '6px 12px',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  startBtn: {
    background: '#1a3a5c',
    color: '#fff',
    border: 'none',
    borderRadius: 5,
    padding: '8px 18px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  deleteBtn: {
    background: '#fef2f2',
    border: '1px solid #fca5a5',
    color: '#dc2626',
    borderRadius: 5,
    padding: '6px 10px',
    fontSize: 13,
    cursor: 'pointer',
  },
}
