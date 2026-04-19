import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getProjects, createProject, deleteProject } from '../api/projects'
import { Plus, Trash2, ExternalLink, Clock, Users } from 'lucide-react'
const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-slate-700 text-slate-300',
  active: 'bg-indigo-900 text-indigo-300',
  submitted: 'bg-blue-900 text-blue-300',
  won: 'bg-green-900 text-green-300',
  lost: 'bg-red-900 text-red-300',
}

const initialForm = {
  title: '',
  issuer: '',
  rfp_id: '',
  deadline: '',
  status: 'draft',
}

type CreateProjectForm = typeof initialForm
type CreateProjectErrors = Partial<Record<'title' | 'rfp_pdf' | 'response_pdf', string>>

function validateProjectForm(form: CreateProjectForm, rfpFile: File | null, respFile: File | null): CreateProjectErrors {
  const errors: CreateProjectErrors = {}
  if (!form.title.trim()) errors.title = 'Project title is required.'
  if (!rfpFile) errors.rfp_pdf = 'RFP / Tender PDF is required.'
  if (!respFile) errors.response_pdf = 'Bid Response PDF is required.'
  return errors
}

function canCreateProject(form: CreateProjectForm, rfpFile: File | null, respFile: File | null) {
  return Boolean(form.title.trim() && rfpFile && respFile)
}

export default function ProjectsPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { data: projects = [], isLoading } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(initialForm)
  const [formErrors, setFormErrors] = useState<CreateProjectErrors>({})
  const [rfpFile, setRfpFile] = useState<File | null>(null)
  const [respFile, setRespFile] = useState<File | null>(null)

  const createMut = useMutation({
    mutationFn: (fd: FormData) => createProject(fd),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      setShowForm(false)
      setForm(initialForm)
      setFormErrors({})
      setRfpFile(null)
      setRespFile(null)
    },
  })
  const deleteMut = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })

  function updateField<K extends keyof CreateProjectForm>(key: K, value: CreateProjectForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const nextErrors = validateProjectForm(form, rfpFile, respFile)
    setFormErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => fd.append(k, v.trim()))
    if (rfpFile) fd.append('rfp_pdf', rfpFile)
    if (respFile) fd.append('response_pdf', respFile)
    createMut.mutate(fd)
  }

  const createDisabled = createMut.isPending || !canCreateProject(form, rfpFile, respFile)

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Response Projects</h1>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={16} /> New Project
        </button>
      </div>

      {showForm && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 mb-6">
          <h2 className="font-semibold mb-4 text-slate-100">Create Project</h2>
          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <input
                  required
                  placeholder="Project Title *"
                  value={form.title}
                  onChange={(e) => updateField('title', e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                />
                {formErrors.title && <p className="mt-1 text-xs text-red-400">{formErrors.title}</p>}
              </div>
              <input
                placeholder="Issuer / Client"
                value={form.issuer}
                onChange={(e) => updateField('issuer', e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
              <input
                placeholder="RFP ID (e.g. RFP-168)"
                value={form.rfp_id}
                onChange={(e) => updateField('rfp_id', e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
              <input
                type="date"
                placeholder="Deadline"
                value={form.deadline}
                onChange={(e) => updateField('deadline', e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="text-xs text-slate-300 block mb-1">
                  RFP / Tender PDF <span className="text-red-400">*</span>
                </span>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setRfpFile(e.target.files?.[0] || null)}
                  className="text-sm text-slate-300 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600"
                />
                {formErrors.rfp_pdf && <p className="mt-1 text-xs text-red-400">{formErrors.rfp_pdf}</p>}
              </label>
              <label className="block">
                <span className="text-xs text-slate-300 block mb-1">
                  Bid Response PDF <span className="text-red-400">*</span>
                </span>
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setRespFile(e.target.files?.[0] || null)}
                  className="text-sm text-slate-300 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600"
                />
                {formErrors.response_pdf && <p className="mt-1 text-xs text-red-400">{formErrors.response_pdf}</p>}
              </label>
            </div>
            {createMut.isError && (
              <p className="text-red-400 text-sm">
                {(createMut.error as any)?.response?.data?.detail || 'Failed to create project.'}
              </p>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createDisabled}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
              >
                {createMut.isPending ? 'Creating...' : 'Create Project'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false)
                  setForm(initialForm)
                  setFormErrors({})
                  setRfpFile(null)
                  setRespFile(null)
                }}
                className="text-slate-400 hover:text-slate-200 text-sm px-4 py-2 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="text-slate-500 text-sm py-8 text-center">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="text-slate-500 text-sm py-12 text-center">No projects yet.</div>
      ) : (
        <div className="space-y-3">
          {projects.map((p: any) => (
            <div
              key={p.id}
              className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4 flex items-center justify-between hover:border-slate-700 transition-colors"
            >
              <div>
                <div className="font-medium text-slate-100 flex items-center gap-2">
                  {p.title}
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[p.status] || ''}`}
                  >
                    {p.status}
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1 flex gap-4">
                  {p.issuer && <span>{p.issuer}</span>}
                  {p.deadline && (
                    <span className="flex items-center gap-1">
                      <Clock size={10} />
                      {p.deadline}
                    </span>
                  )}
                  <span className="flex items-center gap-1">
                    <Users size={10} />
                    {p.member_count} member{p.member_count !== 1 ? 's' : ''}
                  </span>
                  <span>{p.section_count} section{p.section_count !== 1 ? 's' : ''}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => nav(`/projects/${p.id}/workspace`)}
                  className="flex items-center gap-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <ExternalLink size={12} /> Open
                </button>
                <button
                  onClick={() => {
                    if (confirm('Delete this project?')) deleteMut.mutate(p.id)
                  }}
                  className="text-slate-600 hover:text-red-400 p-1.5 rounded transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
