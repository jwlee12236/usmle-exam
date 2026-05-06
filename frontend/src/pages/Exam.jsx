import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api'
import ExamHeader from '../components/ExamHeader'
import QuestionPanel from '../components/QuestionPanel'
import LabValues from '../components/LabValues'
import QuestionNavigator from '../components/QuestionNavigator'
import { useTimer } from '../hooks/useTimer'

const SAVE_INTERVAL = 15000

export default function Exam() {
  const { sessionId } = useParams()
  const navigate = useNavigate()

  const [session, setSession] = useState(null)
  const [questions, setQuestions] = useState([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [showLabValues, setShowLabValues] = useState(false)
  const [showNavigator, setShowNavigator] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const questionStartTimeRef = useRef(Date.now())
  const timeSpentRef = useRef({})
  const submitCalledRef = useRef(false)

  const handleTimeUp = useCallback(() => {
    if (submitCalledRef.current) return
    submitCalledRef.current = true
    alert('Time is up! Your exam will now be submitted.')
    doSubmit()
  }, [])

  const timer = useTimer(4500, handleTimeUp)

  // Load session + questions
  useEffect(() => {
    const load = async () => {
      try {
        const sessionRes = await api.get(`/sessions/${sessionId}`)
        const s = sessionRes.data
        const questionsRes = await api.get(`/exams/${s.exam_set_id}/questions`)

        setSession(s)
        setQuestions(questionsRes.data)

        const restored = {}
        Object.entries(s.answers || {}).forEach(([qn, ans]) => {
          restored[parseInt(qn)] = {
            selectedAnswer: ans.selected_answer,
            eliminatedChoices: ans.eliminated_choices || [],
            isFlagged: ans.is_flagged,
          }
          timeSpentRef.current[parseInt(qn)] = ans.time_spent_seconds || 0
        })
        setAnswers(restored)
        timer.reset(s.time_remaining_seconds)
        timer.start()
        setLoading(false)
      } catch (err) {
        console.error('Failed to load exam:', err)
      }
    }
    load()
  }, [sessionId])

  // Auto-save
  useEffect(() => {
    if (loading) return
    const interval = setInterval(() => {
      saveProgress()
    }, SAVE_INTERVAL)
    return () => clearInterval(interval)
  }, [loading, answers, timer.secondsLeft])

  // Track time per question
  useEffect(() => {
    questionStartTimeRef.current = Date.now()
  }, [currentIndex])

  const accumulateTimeForCurrent = () => {
    if (!questions[currentIndex]) return
    const qn = questions[currentIndex].question_number
    const elapsed = Math.floor((Date.now() - questionStartTimeRef.current) / 1000)
    timeSpentRef.current[qn] = (timeSpentRef.current[qn] || 0) + elapsed
    questionStartTimeRef.current = Date.now()
  }

  const buildPayload = (currentAnswers) => {
    return questions.map((q) => {
      const ans = currentAnswers[q.question_number] || {}
      return {
        question_id: q.id,
        question_number: q.question_number,
        selected_answer: ans.selectedAnswer || null,
        eliminated_choices: ans.eliminatedChoices || [],
        is_flagged: ans.isFlagged || false,
        time_spent_seconds: timeSpentRef.current[q.question_number] || 0,
      }
    })
  }

  const saveProgress = async () => {
    accumulateTimeForCurrent()
    try {
      await api.post(`/sessions/${sessionId}/save-progress`, {
        time_remaining_seconds: timer.secondsLeft,
        answers: buildPayload(answers),
      })
    } catch {}
  }

  const doSubmit = async () => {
    setSubmitting(true)
    timer.pause()
    accumulateTimeForCurrent()
    try {
      await api.post(`/sessions/${sessionId}/submit`, {
        time_remaining_seconds: timer.secondsLeft,
        answers: buildPayload(answers),
      })
      navigate(`/results/${sessionId}`)
    } catch {
      alert('Submission failed. Please try again.')
      setSubmitting(false)
      submitCalledRef.current = false
    }
  }

  const handleAnswer = (letter) => {
    const qn = questions[currentIndex].question_number
    setAnswers((prev) => ({
      ...prev,
      [qn]: { ...(prev[qn] || {}), selectedAnswer: letter },
    }))
  }

  const handleEliminate = (letter) => {
    const qn = questions[currentIndex].question_number
    setAnswers((prev) => {
      const cur = prev[qn] || {}
      const elim = cur.eliminatedChoices || []
      const newElim = elim.includes(letter) ? elim.filter((l) => l !== letter) : [...elim, letter]
      const newSelected = newElim.includes(cur.selectedAnswer) ? null : cur.selectedAnswer
      return { ...prev, [qn]: { ...cur, eliminatedChoices: newElim, selectedAnswer: newSelected } }
    })
  }

  const handleFlag = () => {
    const qn = questions[currentIndex].question_number
    setAnswers((prev) => {
      const cur = prev[qn] || {}
      return { ...prev, [qn]: { ...cur, isFlagged: !cur.isFlagged } }
    })
  }

  const goTo = (index) => {
    accumulateTimeForCurrent()
    setCurrentIndex(index)
  }

  const handleSubmitClick = async () => {
    if (submitting || submitCalledRef.current) return
    const unanswered = questions.filter((q) => !answers[q.question_number]?.selectedAnswer).length
    if (unanswered > 0) {
      const ok = window.confirm(`You have ${unanswered} unanswered question(s). Submit anyway?`)
      if (!ok) return
    }
    submitCalledRef.current = true
    await doSubmit()
  }

  if (loading) return <div style={styles.loading}>Loading exam...</div>

  const currentQuestion = questions[currentIndex]
  const currentAnswerState = answers[currentQuestion?.question_number] || {}

  return (
    <div style={styles.page}>
      <ExamHeader
        currentIndex={currentIndex}
        total={questions.length}
        isFlagged={!!currentAnswerState.isFlagged}
        onToggleFlag={handleFlag}
        onPrev={() => goTo(currentIndex - 1)}
        onNext={() => goTo(currentIndex + 1)}
        onLabValues={() => setShowLabValues((v) => !v)}
        timerDisplay={timer.formatted()}
        timerWarning={timer.secondsLeft <= 300}
        onSubmit={handleSubmitClick}
        onNavigatorOpen={() => setShowNavigator(true)}
      />

      <div style={styles.body}>
        <QuestionPanel
          question={currentQuestion}
          answerState={currentAnswerState}
          onAnswer={handleAnswer}
          onEliminate={handleEliminate}
          onFlag={handleFlag}
        />
        {showLabValues && <LabValues onClose={() => setShowLabValues(false)} />}
      </div>

      {showNavigator && (
        <QuestionNavigator
          questions={questions}
          answers={answers}
          currentIndex={currentIndex}
          onSelect={goTo}
          onClose={() => setShowNavigator(false)}
        />
      )}

      {submitting && (
        <div style={styles.overlay}>
          <div style={styles.overlayMsg}>Submitting your exam...</div>
        </div>
      )}
    </div>
  )
}

const styles = {
  page: {
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: '#fff',
    overflow: 'hidden',
  },
  body: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  loading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    fontSize: 18,
    color: '#555',
  },
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 200,
  },
  overlayMsg: {
    background: '#fff',
    padding: '28px 48px',
    borderRadius: 10,
    fontSize: 18,
    fontWeight: 600,
  },
}
