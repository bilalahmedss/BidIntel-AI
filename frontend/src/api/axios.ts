import axios from 'axios'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('bi_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})
export default api
export const sseUrl = (path: string) => {
  const token = localStorage.getItem('bi_token') || ''
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  return `${base}/api${path}?token=${token}`
}
