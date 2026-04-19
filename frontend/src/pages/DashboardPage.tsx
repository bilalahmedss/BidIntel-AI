import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getProjects } from '../api/projects'
import { FolderKanban, Clock, Users, ChevronRight } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-700 text-slate-300',
  active: 'bg-indigo-900 text-indigo-300',
  submitted: 'bg-blue-900 text-blue-300',
  won: 'bg-green-900 text-green-300',
  lost: 'bg-red-900 text-red-300',
}

export default function DashboardPage() {
  const { user } = useAuth()
  const nav = useNavigate()
  const { data: projects = [], isLoading } = useQuery({ queryKey: ['projects'], queryFn: getProjects })

  const active = projects.filter((p: any) => p.status === 'active').length
  const submitted = projects.filter((p: any) => p.status === 'submitted').length

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100">
          Welcome back, {user?.full_name || user?.email?.split('@')[0]} 👋
        </h1>
        <p className="text-slate-400 mt-1">Here's your bid pipeline at a glance.</p>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: 'Total Projects', value: projects.length, color: 'text-indigo-400' },
          { label: 'Active', value: active, color: 'text-green-400' },
          { label: 'Submitted', value: submitted, color: 'text-blue-400' },
        ].map(s => (
          <div key={s.label} className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className={`text-3xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-slate-400 text-sm mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <h2 className="font-semibold flex items-center gap-2"><FolderKanban size={16} /> Recent Projects</h2>
          <button onClick={() => nav('/projects')} className="text-xs text-indigo-400 hover:text-indigo-300">View all →</button>
        </div>
        {isLoading ? (
          <div className="p-6 text-slate-500 text-sm">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="p-6 text-slate-500 text-sm">No projects yet. <button onClick={() => nav('/projects')} className="text-indigo-400 hover:underline">Create one →</button></div>
        ) : (
          <div className="divide-y divide-slate-800">
            {projects.slice(0, 8).map((p: any) => (
              <div key={p.id} onClick={() => nav(`/projects/${p.id}/workspace`)}
                className="flex items-center justify-between px-5 py-4 hover:bg-slate-800/50 cursor-pointer transition-colors">
                <div>
                  <div className="font-medium text-slate-100">{p.title}</div>
                  <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-3">
                    {p.issuer && <span>{p.issuer}</span>}
                    {p.deadline && <span className="flex items-center gap-1"><Clock size={11} />{p.deadline}</span>}
                    <span className="flex items-center gap-1"><Users size={11} />{p.member_count}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[p.status] || 'bg-slate-700 text-slate-300'}`}>
                    {p.status}
                  </span>
                  <ChevronRight size={14} className="text-slate-600" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
