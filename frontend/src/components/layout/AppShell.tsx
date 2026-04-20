import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import Sidebar from './Sidebar'
import { getSafetySummary } from '../../api/safety'

export default function AppShell({ children }: { children: ReactNode }) {
  const { data } = useQuery({ queryKey: ['safety', 'summary'], queryFn: getSafetySummary })
  const recentEvents = data?.recent_events?.length ?? 0

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-frame">
        <header className="app-topbar">
          <div>
            <div className="eyebrow">Bid intelligence workspace</div>
            <div className="mt-2">
              <div className="text-2xl font-extrabold tracking-tight text-slate-950">BidIntel AI</div>
              <p className="m-0 text-sm text-slate-500">Professional bid analysis, response drafting, and governance controls in one workspace.</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 justify-end">
            <Link to="/safety" className="ui-badge ui-badge-info">
              <ShieldCheck size={14} />
              Backend Guardrails
            </Link>
            <div className="ui-badge ui-badge-neutral">Safety log: {recentEvents} recent event{recentEvents === 1 ? '' : 's'}</div>
          </div>
        </header>
        <main className="app-main">{children}</main>
      </div>
    </div>
  )
}
