export default function QuestionNavigator({ questions, answers, currentIndex, onSelect, onClose }) {
  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <span style={styles.title}>Question Navigator</span>
          <button onClick={onClose} style={styles.closeBtn}>✕</button>
        </div>

        <div style={styles.legend}>
          <span style={styles.legendItem}><span style={{ ...styles.dot, background: '#3b82f6' }} /> Selected</span>
          <span style={styles.legendItem}><span style={{ ...styles.dot, background: '#22c55e' }} /> Answered</span>
          <span style={styles.legendItem}><span style={{ ...styles.dot, background: '#fbbf24' }} /> Flagged</span>
          <span style={styles.legendItem}><span style={{ ...styles.dot, background: '#e5e7eb' }} /> Unanswered</span>
        </div>

        <div style={styles.grid}>
          {questions.map((q, i) => {
            const ans = answers[q.question_number] || {}
            const isAnswered = !!ans.selectedAnswer
            const isFlagged = !!ans.isFlagged
            const isCurrent = i === currentIndex

            let bg = '#e5e7eb'
            if (isCurrent) bg = '#3b82f6'
            else if (isFlagged) bg = '#fbbf24'
            else if (isAnswered) bg = '#22c55e'

            return (
              <button
                key={q.question_number}
                onClick={() => { onSelect(i); onClose() }}
                style={{ ...styles.cell, background: bg, color: isCurrent || isAnswered ? '#fff' : '#111' }}
              >
                {q.question_number}
                {isFlagged && !isCurrent && <span style={styles.flagMark}>🚩</span>}
              </button>
            )
          })}
        </div>

        <div style={styles.footer}>
          <button onClick={onClose} style={styles.doneBtn}>Done</button>
        </div>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
  },
  panel: {
    background: '#fff',
    borderRadius: 8,
    width: 520,
    maxHeight: '80vh',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
  },
  header: {
    padding: '14px 20px',
    borderBottom: '1px solid #e5e7eb',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontWeight: 700,
    fontSize: 16,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    fontSize: 18,
    cursor: 'pointer',
    color: '#555',
  },
  legend: {
    display: 'flex',
    gap: 16,
    padding: '10px 20px',
    borderBottom: '1px solid #e5e7eb',
    flexWrap: 'wrap',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
    color: '#555',
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: '50%',
    display: 'inline-block',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(10, 1fr)',
    gap: 6,
    padding: 20,
    overflowY: 'auto',
  },
  cell: {
    aspectRatio: '1',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 600,
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  flagMark: {
    position: 'absolute',
    top: -4,
    right: -4,
    fontSize: 8,
  },
  footer: {
    padding: '12px 20px',
    borderTop: '1px solid #e5e7eb',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  doneBtn: {
    background: '#1a3a5c',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    padding: '8px 24px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: 14,
  },
}
