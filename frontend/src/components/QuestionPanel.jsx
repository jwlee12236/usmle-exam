import { useState, useRef, useEffect, useCallback } from 'react'
import { staticUrl } from '../api'

const CHOICE_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

export default function QuestionPanel({
  question,
  answerState,
  onAnswer,
  onEliminate,
  onFlag,
}) {
  const { stem, choices, image_paths, question_number } = question
  const { selectedAnswer, eliminatedChoices = [], isFlagged } = answerState

  // Text highlighting via mouseup
  const stemRef = useRef(null)
  const [highlights, setHighlights] = useState([]) // not persisted for now

  const handleMouseUp = () => {
    const selection = window.getSelection()
    if (selection && selection.toString().trim().length > 0) {
      // Could implement rich highlighting here; for now just visual feedback
    }
  }

  const handleChoiceClick = (letter) => {
    if (eliminatedChoices.includes(letter)) return // can't select eliminated
    onAnswer(letter === selectedAnswer ? null : letter)
  }

  const handleChoiceDoubleClick = (letter) => {
    onEliminate(letter)
  }

  const sortedChoices = CHOICE_LETTERS.filter((l) => choices[l] !== undefined)

  return (
    <div style={styles.panel}>
      <div style={styles.questionNumber}>Question {question_number}</div>

      {/* Stem */}
      <div
        ref={stemRef}
        style={styles.stem}
        onMouseUp={handleMouseUp}
      >
        {stem}
      </div>

      {/* Inline figure — only shown when vision detection found a graph/table/image */}
      {image_paths && image_paths.length > 0 && (
        <div style={styles.imageRow}>
          {image_paths.map((src, i) => (
            <img
              key={i}
              src={staticUrl(`/static/${src}`)}
              alt={`Figure ${i + 1}`}
              style={styles.image}
              onClick={() => window.open(staticUrl(`/static/${src}`), '_blank')}
              title="Click to enlarge"
            />
          ))}
        </div>
      )}

      {/* Answer choices */}
      <div style={styles.choices}>
        {sortedChoices.map((letter) => {
          const isEliminated = eliminatedChoices.includes(letter)
          const isSelected = selectedAnswer === letter

          return (
            <ChoiceRow
              key={letter}
              letter={letter}
              text={choices[letter]}
              isSelected={isSelected}
              isEliminated={isEliminated}
              onClick={() => handleChoiceClick(letter)}
              onDoubleClick={() => handleChoiceDoubleClick(letter)}
            />
          )
        })}
      </div>

      <div style={styles.hint}>
        Double-click a choice to eliminate it. Click again to restore.
      </div>
    </div>
  )
}

function ChoiceRow({ letter, text, isSelected, isEliminated, onClick, onDoubleClick }) {
  return (
    <div
      style={{
        ...styles.choiceRow,
        ...(isSelected ? styles.choiceSelected : {}),
        ...(isEliminated ? styles.choiceEliminated : {}),
      }}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
    >
      <div style={styles.radioWrapper}>
        {isEliminated ? (
          <span style={styles.eliminatedX}>✕</span>
        ) : (
          <div style={{ ...styles.radio, ...(isSelected ? styles.radioSelected : {}) }}>
            {isSelected && <div style={styles.radioDot} />}
          </div>
        )}
      </div>
      <span style={styles.letter}>{letter}.</span>
      <span
        style={{
          ...styles.choiceText,
          ...(isEliminated ? styles.strikethrough : {}),
        }}
      >
        {text}
      </span>
    </div>
  )
}

const styles = {
  panel: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px 32px',
    background: '#fff',
  },
  questionNumber: {
    fontSize: 11,
    color: '#888',
    marginBottom: 8,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  stem: {
    fontSize: 15,
    lineHeight: 1.7,
    color: '#111',
    marginBottom: 20,
    whiteSpace: 'pre-wrap',
    cursor: 'text',
    userSelect: 'text',
  },
  imageRow: {
    marginBottom: 20,
  },
  image: {
    maxWidth: '100%',
    height: 'auto',
    border: '1px solid #ddd',
    borderRadius: 4,
    cursor: 'zoom-in',
    display: 'block',
  },
  choices: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    marginBottom: 16,
  },
  choiceRow: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '10px 14px',
    borderRadius: 4,
    cursor: 'pointer',
    border: '1px solid transparent',
    transition: 'background 0.1s',
    userSelect: 'none',
  },
  choiceSelected: {
    background: '#dbeafe',
    border: '1px solid #3b82f6',
  },
  choiceEliminated: {
    opacity: 0.55,
    background: '#f5f5f5',
  },
  radioWrapper: {
    width: 22,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2,
  },
  radio: {
    width: 18,
    height: 18,
    borderRadius: '50%',
    border: '2px solid #999',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioSelected: {
    border: '2px solid #3b82f6',
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    background: '#3b82f6',
  },
  eliminatedX: {
    color: '#c0392b',
    fontWeight: 700,
    fontSize: 14,
  },
  letter: {
    fontWeight: 600,
    fontSize: 15,
    color: '#333',
    flexShrink: 0,
    minWidth: 20,
  },
  choiceText: {
    fontSize: 15,
    color: '#111',
    lineHeight: 1.5,
  },
  strikethrough: {
    textDecoration: 'line-through',
    color: '#888',
  },
  hint: {
    fontSize: 11,
    color: '#bbb',
    marginTop: 8,
  },
}
