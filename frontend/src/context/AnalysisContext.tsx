import { createContext, useContext, useRef, useState, ReactNode } from 'react'
import api from '../api/axios'

export interface JobState {
  jobId: string
  projectId: number
  status: 'queued' | 'running' | 'complete' | 'error'
  label: string
  pct: number
  elapsed: number
  result: any | null
  error: string | null
  startedAt: number
}

interface AnalysisCtx {
  getJob: (pid: number) => JobState | undefined
  startJob: (pid: number, scenario?: string) => Promise<void>
  clearJob: (pid: number) => void
  isRunning: (pid: number) => boolean
}

const Ctx = createContext<AnalysisCtx>(null!)

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Record<number, JobState>>({})
  const sources = useRef<Map<string, EventSource>>(new Map())
  const timers = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map())

  function patch(pid: number, delta: Partial<JobState>) {
    setJobs(prev => ({ ...prev, [pid]: { ...(prev[pid] as JobState), ...delta } }))
  }

  function stopTimer(pid: number) {
    const t = timers.current.get(pid)
    if (t) { clearInterval(t); timers.current.delete(pid) }
  }

  function closeSource(jobId: string) {
    sources.current.get(jobId)?.close()
    sources.current.delete(jobId)
  }

  async function startJob(pid: number, scenario = 'expected') {
    const existing = jobs[pid]
    if (existing?.jobId) closeSource(existing.jobId)
    stopTimer(pid)

    const startedAt = Date.now()
    setJobs(prev => ({
      ...prev,
      [pid]: { jobId: '', projectId: pid, status: 'queued', label: 'Queued…', pct: 0, elapsed: 0, result: null, error: null, startedAt },
    }))

    const timer = setInterval(() => {
      setJobs(prev => {
        const j = prev[pid]
        if (!j || j.status === 'complete' || j.status === 'error') return prev
        return { ...prev, [pid]: { ...j, elapsed: Math.floor((Date.now() - j.startedAt) / 1000) } }
      })
    }, 1000)
    timers.current.set(pid, timer)

    let jobId: string
    try {
      const res = await api.post('/analysis/start', { project_id: pid, financial_scenario: scenario })
      jobId = res.data.job_id
      patch(pid, { jobId })
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Failed to start analysis'
      patch(pid, { status: 'error', label: msg, error: msg })
      stopTimer(pid)
      return
    }

    const token = localStorage.getItem('bi_token') || ''
    const base = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'
    const es = new EventSource(`${base}/api/analysis/stream/${jobId}?token=${token}`)
    sources.current.set(jobId, es)

    es.onmessage = async ev => {
      const data = JSON.parse(ev.data)
      if (data.event === 'progress') {
        patch(pid, { status: 'running', label: data.label, pct: data.pct })
      } else if (data.event === 'complete') {
        try {
          const result = await api.get(`/analysis/result/${data.analysis_id}`).then(r => r.data)
          patch(pid, { status: 'complete', pct: 100, label: 'Analysis complete ✓', result })
        } catch {
          patch(pid, { status: 'complete', pct: 100, label: 'Analysis complete ✓', result: null })
        }
        closeSource(jobId)
        stopTimer(pid)
      } else if (data.event === 'error') {
        patch(pid, { status: 'error', label: data.message, error: data.message })
        closeSource(jobId)
        stopTimer(pid)
      }
    }

    es.onerror = () => {
      setJobs(prev => {
        const j = prev[pid]
        if (j?.status === 'running' || j?.status === 'queued') {
          return { ...prev, [pid]: { ...j, status: 'error', label: 'Connection lost — reload and check backend logs', error: 'SSE disconnected' } }
        }
        return prev
      })
      closeSource(jobId)
      stopTimer(pid)
    }
  }

  function clearJob(pid: number) {
    const j = jobs[pid]
    if (j?.jobId) closeSource(j.jobId)
    stopTimer(pid)
    setJobs(prev => { const n = { ...prev }; delete n[pid]; return n })
  }

  return (
    <Ctx.Provider value={{
      getJob: pid => jobs[pid],
      startJob,
      clearJob,
      isRunning: pid => { const j = jobs[pid]; return !!j && (j.status === 'queued' || j.status === 'running') },
    }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAnalysis() { return useContext(Ctx) }
