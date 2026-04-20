import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Clock3, RefreshCw } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { getProjects } from '../api/projects'
import { useAnalysis } from '../context/AnalysisContext'
import NoticePanel from '../components/governance/NoticePanel'
import RichMarkdown from '../components/ui/RichMarkdown'
import ScoreRing from '../components/ui/ScoreRing'
import StatusBadge from '../components/ui/StatusBadge'
import { CONFIDENTIALITY_NOTICE, HUMAN_REVIEW_NOTICE } from '../governance'

const VERDICT_TONE: Record<string, 'neutral' | 'info' | 'success' | 'warn' | 'danger'> = {
  Strong: 'success',
  Competitive: 'info',
  Borderline: 'warn',
  Weak: 'warn',
  'DO NOT BID': 'danger',
}

const CRITERION_TONE: Record<string, 'success' | 'danger' | 'warn' | 'neutral'> = {
  PASS: 'success',
  PRESENT: 'success',
  FAIL: 'danger',
  ABSENT: 'danger',
}

function formatElapsed(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

export default function AnalysisPage() {
  const [searchParams] = useSearchParams()
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const { getJob, startJob, isRunning } = useAnalysis()

  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [scenario, setScenario] = useState('expected')
  const [activeTab, setActiveTab] = useState<'summary' | 'criteria' | 'gaps' | 'risks'>('summary')

  const job = selectedProjectId ? getJob(selectedProjectId) : undefined
  const running = selectedProjectId ? isRunning(selectedProjectId) : false
  const result = job?.result ?? null

  const scenarioData = result?.scenarios?.[scenario] || {}
  const verdict = scenarioData?.verdict || result?.wps_summary?.verdict
  const criteria = result?.criterion_results || []
  const metRequirements = criteria.filter((item: any) => ['PASS', 'PRESENT'].includes(item.status)).length
  const totalRequirements = criteria.length
  const requirementMatchPercent = totalRequirements ? Math.round((metRequirements / totalRequirements) * 100) : 0
  const gaps = useMemo(
    () =>
      criteria.flatMap((item: any) =>
        (item.gap_signals || []).map((gap: string) => ({
          gate: item.gate_name,
          criterion: item.name,
          gap,
          rationale: item.rationale,
        })),
      ),
    [criteria],
  )
  const poisonPills = result?.poison_pills || []
  const severePills = poisonPills.filter((pill: any) => ['CRITICAL', 'HIGH'].includes(pill.severity)).length

  useEffect(() => {
    const requestedProjectId = Number(searchParams.get('projectId') || '')
    if (requestedProjectId) {
      setSelectedProjectId(requestedProjectId)
    }
  }, [searchParams])

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Analysis workspace</div>
          <h1 className="page-title">Bid scoring and requirement analysis.</h1>
          <p className="page-description">Select a project, run scoring, and review win probability, gaps, and risks.</p>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[370px_minmax(0,1fr)]">
        <aside className="space-y-6 xl:sticky xl:top-[108px] xl:h-[calc(100vh-144px)] xl:overflow-y-auto">
          <section className="surface p-6">
            <h2 className="section-title mt-2 text-xl">Analysis controls</h2>

            <div className="mt-6 space-y-4">
              <div className="field-stack">
                <label className="field-label">Project</label>
                <select
                  value={selectedProjectId ?? ''}
                  onChange={(event) => {
                    setSelectedProjectId(Number(event.target.value) || null)
                    setActiveTab('summary')
                  }}
                >
                  <option value="">Select a project</option>
                  {projects.map((project: any) => (
                    <option key={project.id} value={project.id}>
                      {project.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field-stack">
                <label className="field-label">Financial scenario</label>
                <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
                  {['conservative', 'expected', 'optimistic'].map((option) => (
                    <option key={option} value={option}>
                      {option.charAt(0).toUpperCase() + option.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <button className="primary-button w-full justify-center" disabled={!selectedProjectId || running} onClick={() => selectedProjectId && startJob(selectedProjectId, scenario)}>
                {running ? 'Running analysis...' : result ? 'Re-run analysis' : 'Run analysis'}
              </button>
            </div>
          </section>

          <section className="space-y-3">
            <NoticePanel variant="confidential" title="Confidentiality notice" compact>
              {CONFIDENTIALITY_NOTICE}
            </NoticePanel>
            <NoticePanel variant="review" title="Human review required" compact>
              {HUMAN_REVIEW_NOTICE}
            </NoticePanel>
          </section>

          {job && (job.status === 'queued' || job.status === 'running' || job.status === 'error') && (
            <section className="surface p-6">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  {job.status === 'error' ? <AlertCircle size={16} className="text-red-600" /> : <RefreshCw size={16} className="animate-spin text-slate-600" />}
                  {job.label}
                </div>
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock3 size={12} />
                  {formatElapsed(job.elapsed)}
                </div>
              </div>

              {job.status !== 'error' && (
                <>
                  <div className="status-bar mt-5">
                    <div className="status-fill" style={{ width: `${job.pct}%` }} />
                  </div>
                  <div className="mt-2 text-xs text-slate-500">{job.pct}% complete</div>
                </>
              )}

              {job.status === 'running' && job.elapsed > 45 && job.pct < 30 && (
                <div className="surface-soft mt-4 p-4 text-sm text-amber-700">
                  Waiting for the external model response. Large RFPs can take 30 to 90 seconds per chunk.
                </div>
              )}

              {job.status === 'error' && <div className="mt-4 whitespace-pre-wrap text-sm text-red-600">{job.error}</div>}
            </section>
          )}
        </aside>

        <section className="space-y-6 min-w-0">
          {!result ? (
            <div className="surface hero-card p-10 text-center">
              <div className="mx-auto max-w-xl">
                <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-950">Analysis results will appear here.</h2>
                <p className="mt-4 text-sm text-slate-500">Select a project and run analysis to see scores, gaps, and risks.</p>
              </div>
            </div>
          ) : (
            <>
              <section className="surface hero-card p-8">
                <div className="grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
                  <div className="flex items-center justify-center">
                    <ScoreRing value={metRequirements} total={totalRequirements} label="Requirements met" sublabel={`${requirementMatchPercent}% coverage`} />
                  </div>

                  <div className="space-y-6 min-w-0">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="eyebrow">Results summary</div>
                        <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">Scenario: {scenario.charAt(0).toUpperCase() + scenario.slice(1)}</h2>
                      </div>
                      <StatusBadge tone={VERDICT_TONE[verdict] || 'neutral'}>{verdict || 'No verdict'}</StatusBadge>
                    </div>

                    <div className="grid gap-4 md:grid-cols-3">
                      <div className="metric-card">
                        <div className="metric-value text-slate-950">{scenarioData?.wps?.toFixed(1) ?? '-'}</div>
                        <div className="metric-label">Win probability score</div>
                      </div>
                      <div className="metric-card">
                        <div className="metric-value text-slate-950">{gaps.length}</div>
                        <div className="metric-label">Open requirement gaps</div>
                      </div>
                      <div className="metric-card">
                        <div className="metric-value text-red-700">{severePills}</div>
                        <div className="metric-label">High-severity risks</div>
                      </div>
                    </div>

                    <div className="segmented-control">
                      {['conservative', 'expected', 'optimistic'].map((option) => (
                        <button
                          key={option}
                          onClick={() => setScenario(option)}
                          className={`segmented-button ${scenario === option ? 'segmented-button-active' : ''}`}
                        >
                          {option.charAt(0).toUpperCase() + option.slice(1)} · {result.scenarios?.[option]?.wps?.toFixed(1) ?? '-'}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className="surface p-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <h2 className="section-title mt-2 text-xl">Detailed findings</h2>
                  </div>
                  <div className="segmented-control">
                    {[
                      ['summary', 'Summary'],
                      ['criteria', 'Criteria'],
                      ['gaps', 'Gaps'],
                      ['risks', 'Poison pills'],
                    ].map(([key, label]) => (
                      <button
                        key={key}
                        onClick={() => setActiveTab(key as typeof activeTab)}
                        className={`segmented-button ${activeTab === key ? 'segmented-button-active' : ''}`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-6">
                  {activeTab === 'summary' && (
                    <div className="grid gap-4 lg:grid-cols-2">
                      <div className="surface-soft p-5">
                        <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Scenario explanation</div>
                        <div className="mt-4">
                          <RichMarkdown content={scenarioData?.explanation || 'No scenario explanation available yet.'} />
                        </div>
                        {scenarioData?.binding_constraint && (
                          <div className="mt-4">
                            <StatusBadge tone="warn">Primary driver: {scenarioData.binding_constraint}</StatusBadge>
                          </div>
                        )}
                      </div>

                      <div className="surface-soft p-5">
                        <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Submission rules</div>
                        {result.rfp_meta?.submission_rules?.length ? (
                          <div className="mt-4">
                            <RichMarkdown content={result.rfp_meta.submission_rules.map((rule: string) => `- ${rule}`).join('\n')} />
                          </div>
                        ) : (
                          <p className="mt-4 text-sm text-slate-500">No submission rules were extracted from the current RFP parse.</p>
                        )}
                      </div>

                      <div className="surface-soft p-5 lg:col-span-2">
                        <NoticePanel variant="review" title="Reviewer guidance" compact>
                          {HUMAN_REVIEW_NOTICE}
                        </NoticePanel>
                      </div>
                    </div>
                  )}

                  {activeTab === 'criteria' && (
                    <div className="grid gap-4">
                      {criteria.map((criterion: any, index: number) => (
                        <div key={index} className="surface-soft p-5">
                          <div className="flex flex-wrap items-start gap-3">
                            <StatusBadge tone={CRITERION_TONE[criterion.status] || 'neutral'}>{criterion.status || criterion.score || 'Unknown'}</StatusBadge>
                            <div className="min-w-0 flex-1">
                              <div className="text-sm font-bold text-slate-950">
                                [{criterion.gate_name}] {criterion.name}
                              </div>
                              {criterion.max_points !== undefined && criterion.max_points !== null && (
                                <div className="mt-1 text-xs text-slate-500">
                                  Score: {criterion.score ?? 0}/{criterion.max_points}
                                </div>
                              )}
                            </div>
                            {criterion.evidence_strength && <StatusBadge tone="info">{criterion.evidence_strength}</StatusBadge>}
                          </div>

                          {criterion.rationale && (
                            <div className="mt-4">
                              <RichMarkdown content={criterion.rationale} />
                            </div>
                          )}

                          <div className="mt-4 grid gap-4 lg:grid-cols-2">
                            <div className="surface-strong rounded-2xl border border-slate-100 p-4">
                              <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Matched signals</div>
                              {criterion.matched_signals?.length ? (
                                <div className="mt-3">
                                  <RichMarkdown content={criterion.matched_signals.map((signal: string) => `- ${signal}`).join('\n')} />
                                </div>
                              ) : (
                                <p className="mt-3 text-sm text-slate-500">No positive signals were retrieved.</p>
                              )}
                            </div>

                            <div className="surface-strong rounded-2xl border border-slate-100 p-4">
                              <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Gap signals</div>
                              {criterion.gap_signals?.length ? (
                                <div className="mt-3">
                                  <RichMarkdown content={criterion.gap_signals.map((signal: string) => `- ${signal}`).join('\n')} />
                                </div>
                              ) : (
                                <p className="mt-3 text-sm text-emerald-700">No uncovered gap signals for this criterion.</p>
                              )}
                            </div>
                          </div>

                          <div className="mt-4">
                            <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Supporting evidence</div>
                            {criterion.evidence_snippets?.length ? (
                              <div className="mt-3 space-y-3">
                                {criterion.evidence_snippets.map((snippet: string, snippetIndex: number) => (
                                  <div key={snippetIndex} className="surface-strong rounded-2xl border border-slate-100 p-4">
                                    <RichMarkdown content={snippet} />
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="mt-3 text-sm text-slate-500">No supporting excerpt was retrieved for this criterion.</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'gaps' && (
                    <>
                      {gaps.length === 0 ? (
                        <div className="surface-soft p-6 text-sm text-emerald-700">No gaps detected. The current response covers all scored requirements.</div>
                      ) : (
                        <div className="grid gap-4 md:grid-cols-2">
                          {gaps.map((gap: any, index: number) => (
                            <div key={index} className="surface-soft p-5">
                              <div className="flex flex-wrap gap-2">
                                <StatusBadge tone="warn">{gap.gate}</StatusBadge>
                                <StatusBadge tone="danger">Gap</StatusBadge>
                              </div>
                              <div className="mt-3 text-base font-bold text-slate-950">{gap.criterion}</div>
                              <div className="mt-2 text-sm text-red-700">{gap.gap}</div>
                              {gap.rationale && <div className="mt-3 text-sm text-slate-500">{gap.rationale}</div>}
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}

                  {activeTab === 'risks' && (
                    <>
                      {poisonPills.length === 0 ? (
                        <div className="surface-soft p-6 text-sm text-emerald-700">No poison pill clauses detected in the current analysis.</div>
                      ) : (
                        <div className="space-y-4">
                          <NoticePanel variant="review" title="Legal and commercial review" compact>
                            Poison-pill findings are AI-assisted risk signals. Confirm commercial and legal impact before using them in bid or no-bid decisions.
                          </NoticePanel>

                          {poisonPills.map((pill: any, index: number) => (
                            <div key={index} className="surface-soft p-5">
                              <div className="flex flex-wrap items-center gap-2">
                                <StatusBadge tone={pill.severity === 'CRITICAL' ? 'danger' : pill.severity === 'HIGH' ? 'warn' : 'info'}>
                                  {pill.severity}
                                </StatusBadge>
                                <StatusBadge tone="neutral">Page {pill.page_number}</StatusBadge>
                              </div>
                              <div className="mt-4">
                                <RichMarkdown content={pill.clause_text} />
                              </div>
                              {pill.reason && <div className="mt-3 text-sm text-slate-500">{pill.reason}</div>}
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </section>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
