import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api, { staticUrl } from '../api'

const CHOICE_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

export default function Results() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [results, setResults] = useState(null)
  const [filter, setFilter] = useState('all') // all | correct | incorrect | flagged
  const [expandedQ, setExpandedQ] = useState(null)

  useEffect(() => {
    api.get(`/sessions/${sessionId}/results`).then((r) => setResults(r.data))
  }, [sessionId])

  if (!results) return <div style={styles.loading}>Loading results...</div>

  const { total, correct, answered, score_percent, time_used_seconds, questions } = results

  const filtered = questions.filter((q) => {
    if (filter === 'correct') return q.is_correct === true
    if (filter === 'incorrect') return q.is_correct === false
    if (filter === 'flagged') return q.is_flagged
    return true
  })

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <h1 style={styles.title}>Exam Results</h1>
        </div>
        <button onClick={() => navigate('/')} style={styles.homeBtn}>
          ← Back to Home
        </button>
      </div>

      {/* Score Summary */}
      <div style={styles.summaryRow}>
        <ScoreStat label="Score" value={`${score_percent}%`} highlight />
        <ScoreStat label="Correct" value={`${correct} / ${total}`} />
        <ScoreStat label="Answered" value={`${answered} / ${total}`} />
        <ScoreStat label="Omitted" value={total - answered} />
        <ScoreStat label="Time Used" value={formatTime(time_used_seconds)} />
      </div>

      {/* Filter bar */}
      <div style={styles.filterBar}>
        {['all', 'correct', 'incorrect', 'flagged'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{ ...styles.filterBtn, ...(filter === f ? styles.filterBtnActive : {}) }}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
            {f === 'correct' && ` (${questions.filter((q) => q.is_correct).length})`}
            {f === 'incorrect' && ` (${questions.filter((q) => q.is_correct === false).length})`}
            {f === 'flagged' && ` (${questions.filter((q) => q.is_flagged).length})`}
          </button>
        ))}
      </div>

      {/* Questions review */}
      <div style={styles.questionList}>
        {filtered.map((q) => (
          <QuestionReview
            key={q.question_number}
            q={q}
            expanded={expandedQ === q.question_number}
            onToggle={() => setExpandedQ(expandedQ === q.question_number ? null : q.question_number)}
          />
        ))}
        {filtered.length === 0 && (
          <div style={styles.empty}>No questions match this filter.</div>
        )}
      </div>
    </div>
  )
}

function ScoreStat({ label, value, highlight }) {
  return (
    <div style={{ ...styles.stat, ...(highlight ? styles.statHighlight : {}) }}>
      <div style={styles.statValue}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  )
}

function QuestionReview({ q, expanded, onToggle }) {
  const isCorrect = q.is_correct
  const hasAnswer = q.correct_answer !== null

  const sortedChoices = CHOICE_LETTERS.filter((l) => q.choices[l] !== undefined)

  return (
    <div style={{ ...styles.qCard, ...(isCorrect === true ? styles.qCorrect : isCorrect === false ? styles.qIncorrect : {}) }}>
      <div style={styles.qHeader} onClick={onToggle}>
        <div style={styles.qHeaderLeft}>
          <span style={styles.qNum}>Q{q.question_number}</span>
          {q.is_flagged && <span style={styles.flagBadge}>🚩 Flagged</span>}
          {hasAnswer && (
            <span style={isCorrect ? styles.correctBadge : styles.incorrectBadge}>
              {isCorrect ? '✓ Correct' : '✗ Incorrect'}
            </span>
          )}
          {!hasAnswer && <span style={styles.naBadge}>No answer key</span>}
        </div>
        <div style={styles.qHeaderRight}>
          {q.selected_answer
            ? <span>Your answer: <strong>{q.selected_answer}</strong></span>
            : <span style={{ color: '#888' }}>Omitted</span>}
          {hasAnswer && q.selected_answer !== q.correct_answer && (
            <span style={{ marginLeft: 12, color: '#16a34a' }}>Correct: <strong>{q.correct_answer}</strong></span>
          )}
          <span style={styles.expand}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={styles.qBody}>
          <div style={styles.qStem}>{q.stem}</div>

          {q.image_paths && q.image_paths.length > 0 && (
            <div style={styles.imageRow}>
              {q.image_paths.map((src, i) => (
                <img key={i} src={staticUrl(`/static/${src}`)} alt="" style={styles.image} />
              ))}
            </div>
          )}

          <div style={styles.choiceList}>
            {sortedChoices.map((letter) => {
              const isChosen = q.selected_answer === letter
              const isAnswer = q.correct_answer === letter
              const isEliminated = q.eliminated_choices?.includes(letter)

              let bg = 'transparent'
              let border = '1px solid #e5e7eb'
              if (isAnswer && hasAnswer) { bg = '#dcfce7'; border = '1px solid #86efac' }
              else if (isChosen && !isAnswer) { bg = '#fee2e2'; border = '1px solid #fca5a5' }

              return (
                <div key={letter} style={{ ...styles.choiceRow, background: bg, border }}>
                  <span style={styles.choiceLetter}>{letter}.</span>
                  <span style={{ ...styles.choiceText, textDecoration: isEliminated ? 'line-through' : 'none', color: isEliminated ? '#aaa' : '#111' }}>
                    {q.choices[letter]}
                  </span>
                  {isAnswer && hasAnswer && <span style={styles.correctMark}>✓</span>}
                  {isChosen && !isAnswer && <span style={styles.incorrectMark}>✗</span>}
                </div>
              )
            })}
          </div>

          {q.explanation && (
            <div style={styles.explanation}>
              <div style={styles.explanationTitle}>Explanation</div>
              <div style={styles.explanationText}>{q.explanation}</div>
            </div>
          )}

          <div style={styles.timeMeta}>
            Time spent: {formatTime(q.time_spent_seconds)}
          </div>
        </div>
      )}
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
    padding: '20px 32px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerLeft: {},
  title: {
    fontSize: 24,
    fontWeight: 700,
  },
  homeBtn: {
    background: 'rgba(255,255,255,0.15)',
    border: '1px solid rgba(255,255,255,0.3)',
    color: '#fff',
    padding: '8px 18px',
    borderRadius: 6,
    cursor: 'pointer',
    fontSize: 14,
  },
  summaryRow: {
    display: 'flex',
    gap: 16,
    padding: '24px 32px',
    flexWrap: 'wrap',
  },
  stat: {
    background: '#fff',
    borderRadius: 10,
    padding: '18px 28px',
    textAlign: 'center',
    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
    minWidth: 100,
    flex: 1,
  },
  statHighlight: {
    background: '#1a3a5c',
    color: '#fff',
  },
  statValue: {
    fontSize: 28,
    fontWeight: 700,
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 12,
    opacity: 0.7,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  filterBar: {
    display: 'flex',
    gap: 8,
    padding: '0 32px 16px',
  },
  filterBtn: {
    padding: '7px 16px',
    border: '1px solid #d1d5db',
    borderRadius: 20,
    background: '#fff',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
    color: '#374151',
  },
  filterBtnActive: {
    background: '#1a3a5c',
    color: '#fff',
    borderColor: '#1a3a5c',
  },
  questionList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: '0 32px 32px',
  },
  qCard: {
    background: '#fff',
    borderRadius: 8,
    border: '1px solid #e5e7eb',
    overflow: 'hidden',
  },
  qCorrect: {
    borderLeft: '4px solid #22c55e',
  },
  qIncorrect: {
    borderLeft: '4px solid #ef4444',
  },
  qHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 18px',
    cursor: 'pointer',
    gap: 12,
  },
  qHeaderLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  qNum: {
    fontWeight: 700,
    fontSize: 15,
    color: '#1a3a5c',
  },
  flagBadge: {
    fontSize: 12,
    color: '#b45309',
  },
  correctBadge: {
    background: '#dcfce7',
    color: '#15803d',
    fontSize: 12,
    padding: '2px 8px',
    borderRadius: 10,
    fontWeight: 600,
  },
  incorrectBadge: {
    background: '#fee2e2',
    color: '#dc2626',
    fontSize: 12,
    padding: '2px 8px',
    borderRadius: 10,
    fontWeight: 600,
  },
  naBadge: {
    background: '#f3f4f6',
    color: '#6b7280',
    fontSize: 12,
    padding: '2px 8px',
    borderRadius: 10,
  },
  qHeaderRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: '#555',
  },
  expand: {
    marginLeft: 12,
    fontSize: 11,
    color: '#aaa',
  },
  qBody: {
    padding: '0 18px 18px',
    borderTop: '1px solid #f0f0f0',
  },
  qStem: {
    fontSize: 14,
    lineHeight: 1.7,
    color: '#111',
    padding: '14px 0 12px',
    whiteSpace: 'pre-wrap',
  },
  imageRow: {
    display: 'flex',
    gap: 10,
    marginBottom: 12,
  },
  image: {
    maxWidth: '100%',
    maxHeight: 250,
    objectFit: 'contain',
    border: '1px solid #ddd',
    borderRadius: 4,
  },
  choiceList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    marginBottom: 14,
  },
  choiceRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    borderRadius: 5,
    fontSize: 14,
  },
  choiceLetter: {
    fontWeight: 700,
    color: '#444',
    minWidth: 20,
  },
  choiceText: {
    flex: 1,
    lineHeight: 1.4,
  },
  correctMark: {
    color: '#16a34a',
    fontWeight: 700,
  },
  incorrectMark: {
    color: '#dc2626',
    fontWeight: 700,
  },
  explanation: {
    background: '#f0f7ff',
    border: '1px solid #bfdbfe',
    borderRadius: 6,
    padding: '12px 16px',
    marginBottom: 10,
  },
  explanationTitle: {
    fontWeight: 700,
    fontSize: 13,
    color: '#1d4ed8',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  explanationText: {
    fontSize: 14,
    lineHeight: 1.6,
    color: '#1e3a5f',
  },
  timeMeta: {
    fontSize: 12,
    color: '#aaa',
  },
  empty: {
    textAlign: 'center',
    padding: 40,
    color: '#888',
    fontSize: 15,
  },
  loading: {
    display: 'flex',
    height: '100vh',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 18,
    color: '#555',
  },
}
