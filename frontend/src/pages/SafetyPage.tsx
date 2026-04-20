import { useQuery } from '@tanstack/react-query'
import { FileWarning, FlaskConical, ShieldCheck } from 'lucide-react'
import { getSafetySummary } from '../api/safety'
import StatusBadge from '../components/ui/StatusBadge'

export default function SafetyPage() {
  const { data, isLoading } = useQuery({ queryKey: ['safety', 'summary'], queryFn: getSafetySummary })

  if (isLoading) {
    return (
      <div className="page">
        <div className="surface p-8 text-sm text-slate-500">Loading safety dashboard...</div>
      </div>
    )
  }

  const totals = data?.totals || {}
  const routeBreakdown = Object.entries(data?.route_breakdown || {})
  const entityBreakdown = Object.entries(data?.entity_breakdown || {})
  const recentEvents = data?.recent_events || []
  const redTeam = data?.red_team || {}

  const maxRouteCount = Math.max(1, ...routeBreakdown.map(([, count]) => Number(count)))
  const maxEntityCount = Math.max(1, ...entityBreakdown.map(([, count]) => Number(count)))

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Safety operations</div>
          <h1 className="page-title">Monitor confidentiality controls, guardrails, and audit activity.</h1>
          <p className="page-description">
            This dashboard highlights redactions, unsafe-output fallbacks, prompt-injection detections, and recent audit events from the backend safety layer.
          </p>
        </div>
        <StatusBadge tone="info">
          <ShieldCheck size={13} />
          Guardrails online
        </StatusBadge>
      </section>

      <section className="metric-grid md:grid-cols-2 xl:grid-cols-5">
        {[
          { label: 'PII redactions', value: totals.pii_redactions ?? 0, tone: 'text-slate-900' },
          { label: 'Unsafe fallbacks', value: totals.unsafe_output_fallbacks ?? 0, tone: 'text-red-700' },
          { label: 'Prompt injections', value: totals.prompt_injection_detections ?? 0, tone: 'text-amber-700' },
          { label: 'History redactions', value: totals.history_redactions ?? 0, tone: 'text-slate-800' },
          { label: 'Confidentiality events', value: totals.confidentiality_events ?? 0, tone: 'text-emerald-700' },
        ].map((card) => (
          <div key={card.label} className="metric-card">
            <div className={`metric-value ${card.tone}`}>{card.value}</div>
            <div className="metric-label">{card.label}</div>
          </div>
        ))}
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.9fr)]">
        <section className="surface p-6">
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} className="text-slate-700" />
            <div>
              <h2 className="section-title text-xl">Confidentiality posture</h2>
              <p className="section-subtitle">{data?.confidentiality?.notice}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="surface-soft p-5">
              <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Route breakdown</div>
              <div className="mt-4 space-y-4">
                {routeBreakdown.length === 0 && <div className="text-sm text-slate-500">No events recorded yet.</div>}
                {routeBreakdown.map(([route, count]) => (
                  <div key={route}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="font-semibold capitalize text-slate-900">{route}</span>
                      <span className="text-slate-500">{String(count)}</span>
                    </div>
                    <div className="status-bar">
                      <div className="status-fill" style={{ width: `${(Number(count) / maxRouteCount) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="surface-soft p-5">
              <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Entity breakdown</div>
              <div className="mt-4 space-y-4">
                {entityBreakdown.length === 0 && <div className="text-sm text-slate-500">No PII redactions recorded yet.</div>}
                {entityBreakdown.map(([entity, count]) => (
                  <div key={entity}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="font-semibold text-slate-900">{entity}</span>
                      <span className="text-slate-500">{String(count)}</span>
                    </div>
                    <div className="status-bar">
                      <div className="status-fill" style={{ width: `${(Number(count) / maxEntityCount) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="surface-soft mt-4 p-5 text-sm text-slate-500">{data?.confidentiality?.human_review_notice}</div>
        </section>

        <section className="surface p-6">
          <div className="flex items-center gap-2">
            <FlaskConical size={18} className="text-slate-700" />
            <div>
              <h2 className="section-title text-xl">Red-team suite</h2>
              <p className="section-subtitle">Coverage status for the backend red-team test artifacts.</p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone={redTeam.status === 'pass' ? 'success' : redTeam.status === 'fail' ? 'danger' : 'warn'}>
                {redTeam.status || 'not_run'}
              </StatusBadge>
              <StatusBadge tone="neutral">{redTeam.total_cases ?? 0} cases</StatusBadge>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1">
              <div className="surface-soft p-4">
                <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Passed</div>
                <div className="mt-2 text-2xl font-extrabold tracking-tight text-emerald-700">{redTeam.passed ?? 0}</div>
              </div>
              <div className="surface-soft p-4">
                <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Failed</div>
                <div className="mt-2 text-2xl font-extrabold tracking-tight text-red-700">{redTeam.failed ?? 0}</div>
              </div>
            </div>

            {redTeam.last_run && <div className="text-sm text-slate-500">Last run: {redTeam.last_run}</div>}
            <div className="surface-soft p-4 text-sm text-slate-600">
              {redTeam.summary || 'Run the backend red-team tests to generate the latest report artifacts.'}
            </div>
          </div>
        </section>
      </div>

      <section className="surface p-6">
        <div className="flex items-center gap-2">
          <FileWarning size={18} className="text-amber-600" />
          <div>
            <h2 className="section-title text-xl">Recent audit events</h2>
            <p className="section-subtitle">Latest safety interventions captured by the audit log.</p>
          </div>
        </div>

        {recentEvents.length === 0 ? (
          <div className="surface-soft mt-6 p-6 text-sm text-slate-500">No safety events recorded yet.</div>
        ) : (
          <div className="mt-6 divide-y divide-slate-100">
            {recentEvents.map((event: any) => (
              <div key={event.id} className="event-row">
                <div className="text-sm text-slate-500">{event.created_at}</div>
                <div>
                  <StatusBadge tone="neutral">{event.route}</StatusBadge>
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-950">{event.context}</div>
                  <div className="mt-1 text-xs text-slate-500">{event.entity_types?.join(', ') || 'No entity types'}</div>
                </div>
                <div className="text-sm text-slate-800">{event.event_type}</div>
                <div className="text-sm text-slate-600">{event.action_taken}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
