import { useState } from 'react'

export default function ExamHeader({
  currentIndex,
  total,
  isFlagged,
  onToggleFlag,
  onPrev,
  onNext,
  onLabValues,
  timerDisplay,
  timerWarning,
  onSubmit,
  onNavigatorOpen,
}) {
  return (
    <div style={styles.header}>
      {/* Left section */}
      <div style={styles.left}>
        <button onClick={onNavigatorOpen} style={styles.iconBtn} title="Question Navigator">
          ☰
        </button>
        <div style={styles.itemInfo}>
          <div style={styles.itemNumber}>Item {currentIndex + 1} of {total}</div>
        </div>
        <button
          onClick={onToggleFlag}
          style={{ ...styles.markBtn, ...(isFlagged ? styles.markBtnActive : {}) }}
          title="Flag for review"
        >
          <span style={styles.flagIcon}>{isFlagged ? '🚩' : '🏳'}</span>
          <span>Mark</span>
        </button>
      </div>

      {/* Center navigation */}
      <div style={styles.center}>
        <NavButton onClick={onPrev} disabled={currentIndex === 0} label="◁" text="Previous" />
        <NavButton onClick={onNext} disabled={currentIndex === total - 1} label="▷" text="Next" />
        <div style={styles.divider} />
        <button onClick={onLabValues} style={styles.toolBtn}>
          <span style={styles.toolIcon}>🧪</span>
          <span style={styles.toolLabel}>Lab Values</span>
        </button>
      </div>

      {/* Right section: timer + submit */}
      <div style={styles.right}>
        <div style={{ ...styles.timer, ...(timerWarning ? styles.timerWarning : {}) }}>
          ⏱ {timerDisplay}
        </div>
        <button onClick={onSubmit} style={styles.submitBtn}>
          Submit Exam
        </button>
      </div>
    </div>
  )
}

function NavButton({ onClick, disabled, label, text }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{ ...styles.navBtn, opacity: disabled ? 0.35 : 1 }}>
      <span style={styles.navIcon}>{label}</span>
      <span style={styles.toolLabel}>{text}</span>
    </button>
  )
}

const styles = {
  header: {
    background: '#1a3a5c',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 16px',
    height: 56,
    flexShrink: 0,
    userSelect: 'none',
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    minWidth: 220,
  },
  center: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
    minWidth: 220,
    justifyContent: 'flex-end',
  },
  iconBtn: {
    background: 'none',
    border: 'none',
    color: '#fff',
    fontSize: 20,
    cursor: 'pointer',
    padding: '4px 6px',
  },
  itemInfo: {
    lineHeight: 1.3,
  },
  itemNumber: {
    fontWeight: 700,
    fontSize: 14,
  },
  markBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    background: 'none',
    border: '1px solid rgba(255,255,255,0.4)',
    borderRadius: 4,
    color: '#fff',
    cursor: 'pointer',
    padding: '4px 10px',
    fontSize: 13,
  },
  markBtnActive: {
    background: 'rgba(255,200,0,0.2)',
    borderColor: '#ffd700',
  },
  flagIcon: {
    fontSize: 14,
  },
  navBtn: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    background: 'none',
    border: 'none',
    color: '#fff',
    cursor: 'pointer',
    padding: '6px 14px',
    fontSize: 12,
    gap: 1,
  },
  navIcon: {
    fontSize: 18,
  },
  toolBtn: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    background: 'none',
    border: 'none',
    color: '#fff',
    cursor: 'pointer',
    padding: '6px 12px',
    fontSize: 12,
    gap: 1,
  },
  toolIcon: {
    fontSize: 18,
  },
  toolLabel: {
    fontSize: 11,
    marginTop: 1,
  },
  divider: {
    width: 1,
    height: 36,
    background: 'rgba(255,255,255,0.25)',
    margin: '0 4px',
  },
  timer: {
    fontWeight: 700,
    fontSize: 16,
    background: 'rgba(255,255,255,0.15)',
    padding: '5px 14px',
    borderRadius: 4,
    letterSpacing: 1,
  },
  timerWarning: {
    background: '#c0392b',
    animation: 'pulse 1s ease-in-out infinite',
  },
  submitBtn: {
    background: '#2980b9',
    border: 'none',
    color: '#fff',
    padding: '7px 16px',
    borderRadius: 4,
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: 13,
  },
}
