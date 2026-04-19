import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getProject } from '../api/projects'
import { createSection, deleteSection, generateSections } from '../api/sections'
import SectionEditor from '../components/editor/SectionEditor'
import { Plus, Trash2, Wand2, Play, ArrowLeft, UserPlus, Clock } from 'lucide-react'
import { addMember } from '../api/projects'
import { useAnalysis } from '../context/AnalysisContext'

const SOURCE_BADGE: Record<string, string> = {
  auto: 'bg-indigo-900/50 text-indigo-400',
  manual: 'bg-slate-700 text-slate-400',
}

export default function ProjectWorkspacePage() {
  const { id } = useParams<{ id: string }>()
  const pid = Number(id)
  const nav = useNavigate()
  const qc = useQueryClient()

  const { getJob, startJob, isRunning } = useAnalysis()

  const [activeSectionId, setActiveSectionId] = useState<number | null>(null)
  const [newSectionTitle, setNewSectionTitle]  = useState('')
  const [addingSection, setAddingSection]      = useState(false)
  const [memberEmail, setMemberEmail]          = useState('')
  const [showMemberForm, setShowMemberForm]    = useState(false)

  const job     = getJob(pid)
  const running = isRunning(pid)

  const { data: project, isLoading } = useQuery({ queryKey: ['project', pid], queryFn: () => getProject(pid) })

  const addSectionMut = useMutation({
    mutationFn: (title: string) => createSection(pid, title),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', pid] }); setNewSectionTitle(''); setAddingSection(false) },
  })
  const delSectionMut = useMutation({
    mutationFn: deleteSection,
    onSuccess: (_, sid) => { qc.invalidateQueries({ queryKey: ['project', pid] }); if (activeSectionId === sid) setActiveSectionId(null) },
  })
  const genMut = useMutation({
    mutationFn: () => generateSections(pid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project', pid] }),
  })
  const addMemberMut = useMutation({
    mutationFn: ({ email }: { email: string }) => addMember(pid, email, 'editor'),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', pid] }); setMemberEmail(''); setShowMemberForm(false) },
  })

  async function handleRunAnalysis() {
    if (!project?.rfp_filename) { alert('Upload an RFP PDF first.'); return }
    await startJob(pid)
  }

  if (isLoading) return <div className="text-slate-500 p-8">Loading…</div>
  if (!project)  return <div className="text-red-400 p-8">Project not found.</div>

  const sections = project.sections || []
  const activeSection = sections.find((s: any) => s.id === activeSectionId)

  return (
    <div className="flex h-[calc(100vh-48px)] -m-6 mt-0">
      {/* Sidebar */}
      <div className="w-72 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
        {/* Project header */}
        <div className="p-4 border-b border-slate-800">
          <button onClick={() => nav('/projects')} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 mb-3 transition-colors">
            <ArrowLeft size={12} /> Projects
          </button>
          <h1 className="font-bold text-slate-100 text-sm leading-tight truncate">{project.title}</h1>
          {project.issuer && <p className="text-xs text-slate-500 mt-0.5">{project.issuer}</p>}
          {project.deadline && <p className="text-xs text-slate-500">Due {project.deadline}</p>}
        </div>

        {/* Analysis progress */}
        {job && (job.status === 'queued' || job.status === 'running' || job.status === 'error') && (
          <div className={`mx-3 my-2 rounded-lg p-3 ${job.status === 'error' ? 'bg-red-950/50' : 'bg-slate-800'}`}>
            <div className="flex items-center justify-between mb-1">
              <div className={`text-xs leading-relaxed ${job.status === 'error' ? 'text-red-300' : 'text-slate-300'}`}>
                {job.label}
              </div>
              <div className="flex items-center gap-1 text-[10px] text-slate-500 ml-2 shrink-0">
                <Clock size={9} />{job.elapsed}s
              </div>
            </div>
            {job.status !== 'error' && (
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden mt-1.5">
                <div className="h-full bg-indigo-500 transition-all duration-300 rounded-full" style={{ width: `${job.pct}%` }} />
              </div>
            )}
            {job.status === 'running' && job.elapsed > 45 && job.pct < 30 && (
              <div className="text-[10px] text-amber-400 mt-1.5">Waiting for Gemini API…</div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="px-3 py-2 flex gap-2 flex-wrap border-b border-slate-800">
          <button onClick={handleRunAnalysis} disabled={running} title="Run Analysis"
            className="flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-2.5 py-1.5 rounded-lg transition-colors">
            <Play size={12} /> {running ? 'Running…' : 'Analyse'}
          </button>
          <button onClick={() => genMut.mutate()} disabled={genMut.isPending} title="Generate sections from RFP"
            className="flex items-center gap-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50">
            <Wand2 size={12} /> {genMut.isPending ? 'Generating…' : 'Auto-fill'}
          </button>
          <button onClick={() => setShowMemberForm(v => !v)} title="Add member"
            className="flex items-center gap-1.5 text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-2.5 py-1.5 rounded-lg transition-colors">
            <UserPlus size={12} />
          </button>
        </div>

        {showMemberForm && (
          <div className="px-3 py-2 border-b border-slate-800 flex gap-2">
            <input value={memberEmail} onChange={e => setMemberEmail(e.target.value)} placeholder="Email"
              className="flex-1 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-100 focus:outline-none" />
            <button onClick={() => addMemberMut.mutate({ email: memberEmail })}
              className="text-xs bg-indigo-600 text-white px-2 py-1 rounded">Add</button>
          </div>
        )}

        {/* Sections list */}
        <div className="flex-1 overflow-y-auto py-2">
          {sections.map((s: any) => (
            <div key={s.id} onClick={() => setActiveSectionId(s.id)}
              className={`group flex items-center justify-between px-3 py-2 mx-2 rounded-lg cursor-pointer transition-colors
                ${activeSectionId === s.id ? 'bg-indigo-600 text-white' : 'hover:bg-slate-800 text-slate-300'}`}>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate">{s.title}</div>
                <div className="flex items-center gap-1 mt-0.5">
                  <span className={`text-[10px] px-1.5 rounded ${SOURCE_BADGE[s.source] || ''}`}>{s.source}</span>
                  {s.content && <span className="text-[10px] text-slate-500">{s.content.length}c</span>}
                </div>
              </div>
              <button onClick={e => { e.stopPropagation(); if (confirm('Delete section?')) delSectionMut.mutate(s.id) }}
                className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400 ml-1 transition-all">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        {/* Add section */}
        <div className="p-3 border-t border-slate-800">
          {addingSection ? (
            <div className="flex gap-2">
              <input autoFocus value={newSectionTitle} onChange={e => setNewSectionTitle(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && newSectionTitle.trim()) addSectionMut.mutate(newSectionTitle.trim()) }}
                placeholder="Section title…"
                className="flex-1 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-100 focus:outline-none" />
              <button onClick={() => { if (newSectionTitle.trim()) addSectionMut.mutate(newSectionTitle.trim()) }}
                className="text-xs bg-indigo-600 text-white px-2 py-1 rounded">Add</button>
              <button onClick={() => setAddingSection(false)} className="text-xs text-slate-500 px-1">✕</button>
            </div>
          ) : (
            <button onClick={() => setAddingSection(true)}
              className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 w-full transition-colors">
              <Plus size={12} /> Add section
            </button>
          )}
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 bg-slate-950">
        <SectionEditor sectionId={activeSectionId} sectionTitle={activeSection?.title || ''} />
      </div>
    </div>
  )
}
