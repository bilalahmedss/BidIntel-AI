import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProjects } from '../api/projects'
import { getAnalysisResult } from '../api/analysis'
import { useAnalysis } from '../context/AnalysisContext'
import ReactMarkdown from 'react-markdown'
import { AlertCircle, Clock, RefreshCw } from 'lucide-react'

export default function AnalysisPage() {
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const { getJob, startJob, isRunning } = useAnalysis()

  const [selectedPid, setSelectedPid] = useState<number | null>(null)
  const [scenario, setScenario]       = useState('expected')
  const [activeTab, setActiveTab]     = useState('wps')

  const job = selectedPid ? getJob(selectedPid) : undefined
  const running = selectedPid ? isRunning(selectedPid) : false
  const result  = job?.result ?? null

  const wps     = result?.scenarios?.[scenario]?.wps
  const verdict = result?.scenarios?.[scenario]?.verdict || result?.wps_summary?.verdict

  const VERDICT_COLORS: Record<string, string> = {
    'Strong': 'text-green-400', 'Competitive': 'text-blue-400',
    'Borderline': 'text-yellow-400', 'Weak': 'text-orange-400', 'DO NOT BID': 'text-red-400',
  }

  function formatElapsed(s: number) {
    if (s < 60) return `${s}s`
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Analysis</h1>

      {/* Config */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Project</label>
            <select value={selectedPid ?? ''} onChange={e => { setSelectedPid(Number(e.target.value) || null); setActiveTab('wps') }}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none">
              <option value="">Select a project…</option>
              {projects.map((p: any) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Financial Scenario</label>
            <select value={scenario} onChange={e => setScenario(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none">
              {['conservative', 'expected', 'optimistic'].map(s =>
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
          </div>
        </div>
        <button onClick={() => selectedPid && startJob(selectedPid, scenario)}
          disabled={running || !selectedPid}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-6 py-2 rounded-lg transition-colors">
          {running ? 'Running…' : result ? 'Re-run Analysis' : 'Run Analysis'}
        </button>
      </div>

      {/* Progress */}
      {job && (job.status === 'queued' || job.status === 'running' || job.status === 'error') && (
        <div className={`border rounded-xl p-5 mb-6 ${job.status === 'error' ? 'bg-red-950/40 border-red-800' : 'bg-slate-900 border-slate-800'}`}>
          {/* Header row */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {job.status === 'error'
                ? <AlertCircle size={14} className="text-red-400" />
                : <RefreshCw size={14} className="text-indigo-400 animate-spin" />}
              <span className={`text-sm font-medium ${job.status === 'error' ? 'text-red-300' : 'text-slate-200'}`}>
                {job.label}
              </span>
            </div>
            <div className="flex items-center gap-1 text-xs text-slate-500">
              <Clock size={11} />
              <span>{formatElapsed(job.elapsed)}</span>
            </div>
          </div>

          {/* Progress bar */}
          {job.status !== 'error' && (
            <>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 transition-all duration-500 rounded-full"
                  style={{ width: `${job.pct}%` }} />
              </div>
              <div className="text-xs text-slate-500 mt-2">{job.pct}%</div>
            </>
          )}

          {/* Stall warning */}
          {job.status === 'running' && job.elapsed > 45 && job.pct < 30 && (
            <div className="mt-3 text-xs text-amber-400 bg-amber-900/20 rounded px-3 py-2">
              Waiting for Gemini API response — this can take 30–90 s per chunk on the free tier. If stuck &gt;2 min, check your API quota at console.cloud.google.com.
            </div>
          )}

          {/* Error detail */}
          {job.status === 'error' && (
            <div className="mt-2 text-xs text-red-400 font-mono whitespace-pre-wrap bg-red-950/40 rounded p-3">
              {job.error}
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          {/* WPS hero */}
          <div className="px-6 py-5 border-b border-slate-800 flex items-center gap-8">
            <div>
              <div className="text-xs text-slate-400 mb-1">Win Probability Score</div>
              <div className="text-4xl font-bold text-indigo-400">{wps?.toFixed(1) ?? '—'}</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 mb-1">Verdict</div>
              <div className={`text-2xl font-bold ${VERDICT_COLORS[verdict] || 'text-slate-300'}`}>{verdict || '—'}</div>
            </div>
            <div className="flex gap-6 ml-auto">
              {['conservative', 'expected', 'optimistic'].map(s => (
                <button key={s} onClick={() => setScenario(s)}
                  className={`text-center px-2 py-1 rounded transition-colors ${scenario === s ? 'bg-indigo-900/40' : 'hover:bg-slate-800'}`}>
                  <div className="text-xs text-slate-500 capitalize">{s}</div>
                  <div className="text-lg font-semibold text-slate-300">
                    {result.scenarios?.[s]?.wps?.toFixed(1) ?? '—'}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-slate-800 px-2">
            {[['wps', 'Summary'], ['criteria', 'Criteria'], ['gaps', 'Gaps'], ['pills', 'Poison Pills']].map(([k, l]) => (
              <button key={k} onClick={() => setActiveTab(k)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors
                  ${activeTab === k ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
                {l}
              </button>
            ))}
          </div>

          <div className="p-5">
            {activeTab === 'wps' && (
              <div className="space-y-3">
                {result.rfp_meta?.submission_rules?.length > 0 && (
                  <div>
                    <h3 className="font-medium text-sm mb-2 text-slate-300">Submission Rules</h3>
                    <ul className="space-y-1">{result.rfp_meta.submission_rules.map((r: string, i: number) =>
                      <li key={i} className="text-sm text-slate-400">• {r}</li>)}</ul>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'criteria' && (
              <div className="space-y-3">
                {(result.criterion_results || []).map((c: any, i: number) => (
                  <div key={i} className={`border rounded-lg p-4 ${c.status === 'PASS' || c.status === 'PRESENT' ? 'border-green-800 bg-green-900/10' : 'border-red-800 bg-red-900/10'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <span>{c.status === 'PASS' || c.status === 'PRESENT' ? '✅' : '❌'}</span>
                      <span className="font-medium text-sm text-slate-200">[{c.gate_name}] {c.name}</span>
                      {c.score !== undefined && <span className="ml-auto text-xs text-slate-400">{c.score}/{c.max_points} pts</span>}
                    </div>
                    {c.matched_signals?.length > 0 && (
                      <div className="text-xs text-green-400 space-y-0.5">{c.matched_signals.map((s: string, j: number) => <div key={j}>✓ {s}</div>)}</div>
                    )}
                    {c.gap_signals?.length > 0 && (
                      <div className="text-xs text-red-400 space-y-0.5 mt-1">{c.gap_signals.map((s: string, j: number) => <div key={j}>⚠ {s}</div>)}</div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'gaps' && (() => {
              const gaps = (result.criterion_results || []).flatMap((c: any) =>
                (c.gap_signals || []).map((g: string) => ({ gate: c.gate_name, criterion: c.name, gap: g }))
              )
              return gaps.length === 0
                ? <p className="text-green-400 text-sm">No gaps — your response covers all requirements.</p>
                : <div className="space-y-2">
                    <p className="text-yellow-400 text-sm mb-3">{gaps.length} gap{gaps.length !== 1 ? 's' : ''} found</p>
                    {gaps.map((g: any, i: number) => (
                      <div key={i} className="bg-slate-800 rounded-lg p-3 text-sm">
                        <span className="text-slate-500 text-xs">[{g.gate}] {g.criterion}</span>
                        <div className="text-red-300 mt-1">⚠ {g.gap}</div>
                      </div>
                    ))}
                  </div>
            })()}

            {activeTab === 'pills' && (() => {
              const pills = result.poison_pills || []
              if (!pills.length) return <p className="text-green-400 text-sm">No poison pill clauses detected.</p>
              return (
                <div className="space-y-3">
                  <div className="flex gap-4 mb-4">
                    {['CRITICAL', 'HIGH', 'MEDIUM'].map(s => {
                      const count = pills.filter((p: any) => p.severity === s).length
                      const color = s === 'CRITICAL' ? 'text-red-400' : s === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
                      return <div key={s}><span className={`font-bold ${color}`}>{count}</span><span className="text-slate-400 text-xs ml-1">{s}</span></div>
                    })}
                  </div>
                  {pills.map((p: any, i: number) => (
                    <div key={i} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded ${p.severity === 'CRITICAL' ? 'bg-red-900 text-red-300' : p.severity === 'HIGH' ? 'bg-orange-900 text-orange-300' : 'bg-yellow-900 text-yellow-300'}`}>{p.severity}</span>
                        <span className="text-xs text-slate-400">Page {p.page_number}</span>
                      </div>
                      <p className="text-sm text-slate-300">{p.clause_text}</p>
                      {p.reason && <p className="text-xs text-slate-500 mt-2">{p.reason}</p>}
                    </div>
                  ))}
                </div>
              )
            })()}
          </div>
        </div>
      )}
    </div>
  )
}
