import { Activity, FileLock2, History, ShieldCheck, ShieldEllipsis, Siren, Sparkles } from 'lucide-react'
import StatusBadge from '../ui/StatusBadge'

type SafetySummary = {
  totals?: Record<string, number>
  recent_events?: Array<any>
}

type PanelMode = 'ask' | 'analysis'

function countRecentEvents(summary: SafetySummary | undefined, route: string) {
  return (summary?.recent_events || []).filter((event) => event.route === route).length
}

export default function AssurancePanel({
  summary,
  mode,
}: {
  summary?: SafetySummary
  mode: PanelMode
}) {
  const totals = summary?.totals || {}
  const recentEvents = (summary?.recent_events || []).filter((event) => event.route === mode).slice(0, 3)

  const askItems = [
    {
      title: 'PII redaction',
      detail: 'Triggered when the backend redaction layer detects email, phone, SSN, credit-card, or name patterns before sending prompts outward.',
      value: totals.pii_redactions ?? 0,
      Icon: FileLock2,
      tone: 'warn' as const,
    },
    {
      title: 'Prompt-injection check',
      detail: 'Triggered when the backend matches known instruction-override patterns in the user message or retained chat history.',
      value: totals.prompt_injection_detections ?? 0,
      Icon: ShieldEllipsis,
      tone: 'info' as const,
    },
    {
      title: 'Unsafe-output fallback',
      detail: 'Triggered only if the generated answer matches the backend output blocklist and is replaced with a safe fallback response.',
      value: totals.unsafe_output_fallbacks ?? 0,
      Icon: Siren,
      tone: 'neutral' as const,
    },
  ]

  const analysisItems = [
    {
      title: 'Confidentiality event',
      detail: 'Logged when an analysis run crosses the LLM boundary and the backend records confidentiality handling for that job start.',
      value: totals.confidentiality_events ?? 0,
      Icon: FileLock2,
      tone: 'warn' as const,
    },
    {
      title: 'Recent analysis events',
      detail: 'Reflects recent safety-log entries tied to the analysis route, including run start and external processing markers.',
      value: countRecentEvents(summary, 'analysis'),
      Icon: Activity,
      tone: 'info' as const,
    },
    {
      title: 'Audit trail',
      detail: 'Every recorded safety event is persisted and surfaced in the Safety dashboard. This card is a summary, not a guarantee banner.',
      value: recentEvents.length,
      Icon: History,
      tone: 'neutral' as const,
    },
  ]

  const items = mode === 'ask' ? askItems : analysisItems
  const title = mode === 'ask' ? 'Ask route checks' : 'Analysis route log'
  const subtitle =
    mode === 'ask'
      ? 'Shows checks the backend currently applies and records for Ask.'
      : 'Shows what the backend currently records when analysis runs start.'

  return (
    <section className="surface assurance-panel">
      <div className="assurance-panel-header">
        <div className="min-w-0">
          <div className="eyebrow">Responsible AI</div>
          <h2 className="section-title assurance-panel-title mt-2 text-xl">{title}</h2>
          <p className="section-subtitle mt-3">{subtitle}</p>
        </div>
        <StatusBadge tone="info">
          <ShieldCheck size={13} />
          Backend observed
        </StatusBadge>
      </div>

      <div className="assurance-grid">
        {items.map((item) => (
          <div key={item.title} className="assurance-item">
            <div className="assurance-item-top">
              <div className="assurance-item-icon">
                <item.Icon size={16} />
              </div>
              <StatusBadge tone={item.tone}>{item.value}</StatusBadge>
            </div>
            <div className="mt-4 text-sm font-bold text-slate-950">{item.title}</div>
            <p className="mt-2 text-sm text-slate-500">{item.detail}</p>
          </div>
        ))}
      </div>

      <div className="assurance-log">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-slate-500" />
          <div className="text-sm font-bold text-slate-900">Recent {mode} audit events</div>
        </div>
        {recentEvents.length === 0 ? (
          <div className="assurance-log-empty">No recent {mode} safety events are currently in the summary feed.</div>
        ) : (
          <div className="mt-4 space-y-3">
            {recentEvents.map((event) => (
              <div key={event.id} className="assurance-log-item">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge tone="neutral">{event.event_type}</StatusBadge>
                  <span className="text-xs text-slate-400">{event.created_at}</span>
                </div>
                <div className="mt-2 text-sm font-semibold text-slate-900">{event.action_taken}</div>
                <div className="mt-1 text-xs text-slate-500">{event.context}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
