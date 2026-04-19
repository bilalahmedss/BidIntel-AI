import api from './axios'
import { sseUrl } from './axios'

export const startAnalysis   = (project_id: number, financial_scenario = 'expected') =>
  api.post('/analysis/start', { project_id, financial_scenario }).then(r => r.data)
export const getAnalysisList = (pid: number) => api.get(`/analysis/project/${pid}`).then(r => r.data)
export const getAnalysisResult = (aid: number) => api.get(`/analysis/result/${aid}`).then(r => r.data)

export function streamAnalysis(jobId: string, onEvent: (e: object) => void, onDone: () => void) {
  const es = new EventSource(sseUrl(`/analysis/stream/${jobId}`))
  es.onmessage = ev => {
    const data = JSON.parse(ev.data)
    onEvent(data)
    if (data.event === 'complete' || data.event === 'error') { es.close(); onDone() }
  }
  es.onerror = () => { es.close(); onDone() }
  return () => es.close()
}
