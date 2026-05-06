import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Exam from './pages/Exam'
import Results from './pages/Results'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/exam/:sessionId" element={<Exam />} />
      <Route path="/results/:sessionId" element={<Results />} />
    </Routes>
  )
}
