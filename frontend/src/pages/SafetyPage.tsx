import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, FileWarning, FlaskConical } from 'lucide-react'
import { getSafetySummary } from '../api/safety'

export default function SafetyPage() {
  const { data, isLoading } = useQuery({ queryKey: ['safety', 'summary'], queryFn: getSafetySummary })

  if (isLoading) return <div className="text-slate-500 p-8">Loading safety dashboard...</div>

  const totals = data?.totals || {}
  const routeBreakdown = Object.entries(data?.route_breakdown || {})
  const entityBreakdown = Object.entries(data?.entity_breakdown || {})
  const recentEvents = data?.recent_events || []
  const redTeam = data?.red_team || {}

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100">Safety Dashboard</h1>
        <p className="text-slate-400 mt-1">Governance, safety events, confidentiality posture, and red-team coverage.</p>
      </div>

      <div className="grid grid-cols-5 gap-4 mb-8">
        {[
          { label: 'PII Redactions', value: totals.pii_redactions ?? 0, color: 'text-indigo-400' },
          { label: 'Unsafe Fallbacks', value: totals.unsafe_output_fallbacks ?? 0, color: 'text-red-400' },
          { label: 'Prompt Injections', value: totals.prompt_injection_detections ?? 0, color: 'text-amber-400' },
          { label: 'History Redactions', value: totals.history_redactions ?? 0, color: 'text-cyan-400' },
          { label: 'Confidentiality Events', value: totals.confidentiality_events ?? 0, color: 'text-emerald-400' },
        ].map(card => (
          <div key={card.label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className={`text-3xl font-bold ${card.color}`}>{card.value}</div>
            <div className="text-slate-400 text-sm mt-1">{card.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        <div className="col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck size={16} className="text-indigo-400" />
            <h2 className="font-semibold">Confidentiality Posture</h2>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">{data?.confidentiality?.notice}</p>
          <p className="text-xs text-slate-500 mt-3">{data?.confidentiality?.human_review_notice}</p>

          <div className="grid grid-cols-2 gap-4 mt-5">
            <div className="bg-slate-800 rounded-lg p-4">
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">Route Breakdown</div>
              <div className="space-y-2">
                {routeBreakdown.length === 0 && <div className="text-sm text-slate-500">No events recorded yet.</div>}
                {routeBreakdown.map(([route, count]) => (
                  <div key={route} className="flex items-center justify-between text-sm">
                    <span className="capitalize text-slate-300">{route}</span>
                    <span className="text-indigo-400 font-semibold">{String(count)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">Entity Breakdown</div>
              <div className="space-y-2">
                {entityBreakdown.length === 0 && <div className="text-sm text-slate-500">No PII redactions recorded yet.</div>}
                {entityBreakdown.map(([entity, count]) => (
                  <div key={entity} className="flex items-center justify-between text-sm">
                    <span className="text-slate-300">{entity}</span>
                    <span className="text-cyan-400 font-semibold">{String(count)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical size={16} className="text-fuchsia-400" />
            <h2 className="font-semibold">Red-Team Suite</h2>
          </div>
          <div className="space-y-3">
            <div className="text-sm text-slate-300">
              Status: <span className={`${redTeam.status === 'pass' ? 'text-emerald-400' : redTeam.status === 'fail' ? 'text-red-400' : 'text-amber-400'} font-semibold capitalize`}>{redTeam.status || 'not_run'}</span>
            </div>
            <div className="text-sm text-slate-400">Cases: {redTeam.total_cases ?? 0}</div>
            <div className="text-sm text-emerald-400">Passed: {redTeam.passed ?? 0}</div>
            <div className="text-sm text-red-400">Failed: {redTeam.failed ?? 0}</div>
            {redTeam.last_run && <div className="text-xs text-slate-500">Last run: {redTeam.last_run}</div>}
            <div className="bg-slate-800 rounded-lg p-3 text-xs text-slate-400 leading-relaxed">
              {redTeam.summary || 'Run the backend red-team tests to generate the latest report artifacts for demo screenshots.'}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-slate-800">
          <FileWarning size={16} className="text-amber-400" />
          <h2 className="font-semibold">Recent Audit Events</h2>
        </div>
        {recentEvents.length === 0 ? (
          <div className="p-6 text-slate-500 text-sm">No safety events recorded yet.</div>
        ) : (
          <div className="divide-y divide-slate-800">
            {recentEvents.map((event: any) => (
              <div key={event.id} className="grid grid-cols-6 gap-4 px-5 py-4 text-sm">
                <div className="text-slate-400">{event.created_at}</div>
                <div className="capitalize text-slate-300">{event.route}</div>
                <div className="text-slate-300">{event.context}</div>
                <div className="text-indigo-300">{event.event_type}</div>
                <div className="text-slate-400">{event.entity_types?.join(', ') || '-'}</div>
                <div className="text-slate-500">{event.action_taken}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
