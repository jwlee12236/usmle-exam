import { useState } from 'react'
import { LAB_VALUES } from '../data/labValues'

const TABS = Object.keys(LAB_VALUES)

export default function LabValues({ onClose }) {
  const [activeTab, setActiveTab] = useState('Serum')
  const [search, setSearch] = useState('')

  const rows = LAB_VALUES[activeTab].filter(
    (row) =>
      search === '' ||
      row.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerTitle}>⚗ Lab Values</span>
        <button onClick={onClose} style={styles.closeBtn}>✕</button>
      </div>

      <div style={styles.searchRow}>
        <input
          type="text"
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={styles.searchInput}
        />
      </div>

      <div style={styles.tabs}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setSearch('') }}
            style={{
              ...styles.tab,
              ...(activeTab === tab ? styles.tabActive : {}),
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>{activeTab}</th>
              <th style={styles.th}>Reference Range</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} style={i % 2 === 0 ? styles.rowEven : styles.rowOdd}>
                <td style={styles.td}>{row.name}</td>
                <td style={styles.td}>{row.range}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={2} style={{ ...styles.td, color: '#888', textAlign: 'center' }}>
                  No results found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const styles = {
  container: {
    width: 480,
    height: '100%',
    background: '#fff',
    borderLeft: '1px solid #ccc',
    display: 'flex',
    flexDirection: 'column',
    fontSize: 14,
  },
  header: {
    background: '#f0f0f0',
    padding: '10px 14px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #ccc',
  },
  headerTitle: {
    fontWeight: 600,
    fontSize: 15,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontSize: 16,
    color: '#555',
    padding: '2px 6px',
  },
  searchRow: {
    padding: '8px 14px',
    borderBottom: '1px solid #e0e0e0',
  },
  searchInput: {
    width: '100%',
    padding: '6px 10px',
    border: '1px solid #ccc',
    borderRadius: 4,
    fontSize: 13,
    outline: 'none',
  },
  tabs: {
    display: 'flex',
    gap: 4,
    padding: '6px 14px',
    borderBottom: '1px solid #e0e0e0',
  },
  tab: {
    padding: '5px 12px',
    border: '1px solid #ccc',
    borderRadius: 4,
    background: '#fff',
    cursor: 'pointer',
    fontSize: 12,
    color: '#333',
  },
  tabActive: {
    background: '#1a3a5c',
    color: '#fff',
    borderColor: '#1a3a5c',
  },
  tableWrapper: {
    overflowY: 'auto',
    flex: 1,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    background: '#d8e4f0',
    padding: '8px 14px',
    textAlign: 'left',
    fontWeight: 600,
    fontSize: 13,
    borderBottom: '1px solid #ccc',
    position: 'sticky',
    top: 0,
  },
  td: {
    padding: '6px 14px',
    fontSize: 13,
    borderBottom: '1px solid #eee',
    verticalAlign: 'top',
  },
  rowEven: { background: '#f7f9fc' },
  rowOdd: { background: '#fff' },
}
