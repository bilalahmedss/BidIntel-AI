import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, BriefcaseBusiness, CalendarClock, FileText, Users } from 'lucide-react'
import { getProjects } from '../api/projects'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/ui/StatusBadge'

const STATUS_TONE: Record<string, 'neutral' | 'info' | 'success' | 'warn' | 'danger'> = {
  draft: 'neutral',
  active: 'info',
  submitted: 'success',
  won: 'success',
  lost: 'danger',
}

export default function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { data: projects = [], isLoading } = useQuery({ queryKey: ['projects'], queryFn: getProjects })

  const active = projects.filter((project: any) => project.status === 'active').length
  const submitted = projects.filter((project: any) => project.status === 'submitted').length
  const totalCollaborators = projects.reduce((sum: number, project: any) => sum + (project.member_count || 0), 0)
  const dueSoon = projects.filter((project: any) => project.deadline).slice(0, 4)

  return (
    <div className="page dashboard-grid">
      <section className="dashboard-hero">
        <div className="surface surface-strong dashboard-hero-main">
          <div>
            <div className="eyebrow">Control center</div>
            <h1 className="page-title">Welcome back, {user?.full_name || user?.email?.split('@')[0]}.</h1>
            <p className="page-description">An overview of your active bids and upcoming deadlines.</p>
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-3">
              <button className="primary-button" onClick={() => navigate('/projects')}>
                <BriefcaseBusiness size={16} />
                Open project portfolio
              </button>
              <StatusBadge tone="neutral">{projects.length} tracked bid{projects.length === 1 ? '' : 's'}</StatusBadge>
            </div>

            <div className="dashboard-ribbon">
              {[
                { label: 'Total projects', value: projects.length, tone: 'text-slate-950', Icon: BriefcaseBusiness },
                { label: 'Active pursuits', value: active, tone: 'text-slate-950', Icon: CalendarClock },
                { label: 'Submitted bids', value: submitted, tone: 'text-emerald-700', Icon: FileText },
                { label: 'Collaborators', value: totalCollaborators, tone: 'text-slate-700', Icon: Users },
              ].map((item) => (
                <div key={item.label} className="dashboard-ribbon-card">
                  <item.Icon size={16} className="text-slate-400" />
                  <div className={`dashboard-ribbon-value mt-4 ${item.tone}`}>{item.value}</div>
                  <div className="dashboard-ribbon-label">{item.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="surface dashboard-sidecard">
          <div className="eyebrow">Portfolio health</div>
          <div className="mt-6 space-y-6">
            <div>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-900">Active pursuits</span>
                <span className="text-slate-500">{active}</span>
              </div>
              <div className="status-bar">
                <div className="status-fill" style={{ width: `${projects.length ? (active / projects.length) * 100 : 0}%` }} />
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-900">Submitted bids</span>
                <span className="text-slate-500">{submitted}</span>
              </div>
              <div className="status-bar">
                <div className="status-fill" style={{ width: `${projects.length ? (submitted / projects.length) * 100 : 0}%` }} />
              </div>
            </div>

          </div>
        </div>
      </section>

      <section className="dashboard-panels">
        <div className="surface dashboard-panel">
          <div className="page-header">
            <div>
              <div className="eyebrow">Recent work</div>
              <h2 className="section-title mt-2 text-xl">Project portfolio</h2>
            </div>
            <button className="secondary-button" onClick={() => navigate('/projects')}>
              View all
              <ArrowRight size={15} />
            </button>
          </div>

          {isLoading ? (
            <div className="dashboard-empty mt-6 text-sm text-slate-500">Loading portfolio...</div>
          ) : projects.length === 0 ? (
            <div className="dashboard-empty mt-6">
              <div>
                <div className="text-lg font-bold text-slate-900">No projects yet</div>
                <p className="mt-2 text-sm text-slate-500">Create your first project to start uploading RFPs and scoring responses.</p>
              </div>
            </div>
          ) : (
            <div className="mt-6 space-y-3">
              {projects.slice(0, 6).map((project: any) => (
                <button
                  key={project.id}
                  onClick={() => navigate(`/projects/${project.id}/workspace`)}
                  className="surface-soft w-full p-4 text-left transition hover:-translate-y-0.5 hover:shadow-lg"
                >
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="text-base font-bold text-slate-950">{project.title}</div>
                    <StatusBadge tone={STATUS_TONE[project.status] || 'neutral'}>{project.status}</StatusBadge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-4 text-sm text-slate-500">
                    {project.issuer && <span>{project.issuer}</span>}
                    {project.deadline && <span>Due {project.deadline}</span>}
                    <span>{project.member_count} collaborators</span>
                    <span>{project.section_count} sections</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="surface dashboard-panel">
          <div className="eyebrow">Next actions</div>
          <h2 className="section-title mt-2 text-xl">Upcoming deadlines</h2>

          {dueSoon.length === 0 ? (
            <div className="dashboard-empty mt-6 text-sm text-slate-500">
              Add project deadlines to surface your next submission milestones here.
            </div>
          ) : (
            <div className="mt-6 space-y-3">
              {dueSoon.map((project: any) => (
                <div key={project.id} className="surface-soft p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-bold text-slate-950">{project.title}</div>
                      <div className="mt-1 text-sm text-slate-500">{project.issuer || 'No issuer listed'}</div>
                    </div>
                    <StatusBadge tone="warn">{project.deadline}</StatusBadge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
