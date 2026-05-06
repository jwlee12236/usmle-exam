import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8002',
})

export default api

export const staticUrl = (path) =>
  `${import.meta.env.VITE_API_URL || 'http://localhost:8002'}${path}`
