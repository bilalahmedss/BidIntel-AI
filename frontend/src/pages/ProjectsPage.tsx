import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, FolderPlus, Trash2, UploadCloud } from 'lucide-react'
import { createProject, deleteProject, getProjects } from '../api/projects'
import StatusBadge from '../components/ui/StatusBadge'

const STATUS_TONE: Record<string, 'neutral' | 'info' | 'success' | 'warn' | 'danger'> = {
  draft: 'neutral',
  active: 'info',
  submitted: 'success',
  won: 'success',
  lost: 'danger',
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

function validateProjectForm(form: CreateProjectForm, rfpFile: File | null, responseFile: File | null): CreateProjectErrors {
  const errors: CreateProjectErrors = {}
  if (!form.title.trim()) errors.title = 'Project title is required.'
  if (!rfpFile) errors.rfp_pdf = 'RFP or tender PDF is required.'
  if (!responseFile) errors.response_pdf = 'Bid response PDF is required.'
  return errors
}

function canCreateProject(form: CreateProjectForm, rfpFile: File | null, responseFile: File | null) {
  return Boolean(form.title.trim() && rfpFile && responseFile)
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: projects = [], isLoading } = useQuery({ queryKey: ['projects'], queryFn: getProjects })

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState<CreateProjectErrors>({})
  const [rfpFile, setRfpFile] = useState<File | null>(null)
  const [responseFile, setResponseFile] = useState<File | null>(null)

  const createMutation = useMutation({
    mutationFn: (payload: FormData) => createProject(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowForm(false)
      setForm(initialForm)
      setErrors({})
      setRfpFile(null)
      setResponseFile(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  })

  function updateField<K extends keyof CreateProjectForm>(key: K, value: CreateProjectForm[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const nextErrors = validateProjectForm(form, rfpFile, responseFile)
    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) return

    const payload = new FormData()
    Object.entries(form).forEach(([key, value]) => payload.append(key, value.trim()))
    if (rfpFile) payload.append('rfp_pdf', rfpFile)
    if (responseFile) payload.append('response_pdf', responseFile)
    createMutation.mutate(payload)
  }

  const createDisabled = createMutation.isPending || !canCreateProject(form, rfpFile, responseFile)

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Project portfolio</div>
          <h1 className="page-title">Create, upload, and manage bid response projects.</h1>
          <p className="page-description">
            Each project keeps the RFP, bid response, ownership details, and editable response workspace tied together in one place.
          </p>
        </div>
        <button className="primary-button" onClick={() => setShowForm((current) => !current)}>
          <FolderPlus size={16} />
          {showForm ? 'Hide project form' : 'New response project'}
        </button>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.95fr)_minmax(0,1.25fr)]">
        <section className="surface p-6">
          <div className="eyebrow">Input pane</div>
          <h2 className="section-title mt-2 text-xl">Project intake</h2>
          <p className="section-subtitle">Capture the project record and upload the source documents used for analysis.</p>

          {showForm ? (
            <form onSubmit={handleSubmit} className="mt-6 space-y-5">
              <div className="field-stack">
                <label className="field-label">Project title</label>
                <input value={form.title} onChange={(event) => updateField('title', event.target.value)} placeholder="National health data modernization bid" />
                {errors.title && <div className="text-sm text-red-600">{errors.title}</div>}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="field-stack">
                  <label className="field-label">Issuer or client</label>
                  <input value={form.issuer} onChange={(event) => updateField('issuer', event.target.value)} placeholder="Ministry of Health" />
                </div>
                <div className="field-stack">
                  <label className="field-label">RFP ID</label>
                  <input value={form.rfp_id} onChange={(event) => updateField('rfp_id', event.target.value)} placeholder="RFP-168" />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="field-stack">
                  <label className="field-label">Submission deadline</label>
                  <input type="date" value={form.deadline} onChange={(event) => updateField('deadline', event.target.value)} />
                </div>
                <div className="field-stack">
                  <label className="field-label">Lifecycle status</label>
                  <select value={form.status} onChange={(event) => updateField('status', event.target.value)}>
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="submitted">Submitted</option>
                    <option value="won">Won</option>
                    <option value="lost">Lost</option>
                  </select>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="upload-zone cursor-pointer">
                  <UploadCloud size={28} className="text-slate-700" />
                  <div className="text-sm font-bold text-slate-900">Upload RFP or tender PDF</div>
                  <div className="text-xs text-slate-500">{rfpFile ? rfpFile.name : 'Attach the original solicitation document'}</div>
                  <input type="file" accept=".pdf" className="hidden" onChange={(event) => setRfpFile(event.target.files?.[0] || null)} />
                </label>

                <label className="upload-zone cursor-pointer">
                  <UploadCloud size={28} className="text-slate-700" />
                  <div className="text-sm font-bold text-slate-900">Upload bid response PDF</div>
                  <div className="text-xs text-slate-500">{responseFile ? responseFile.name : 'Attach the response you want scored'}</div>
                  <input type="file" accept=".pdf" className="hidden" onChange={(event) => setResponseFile(event.target.files?.[0] || null)} />
                </label>
              </div>

              {(errors.rfp_pdf || errors.response_pdf) && (
                <div className="surface-soft p-4 text-sm text-red-600">
                  {errors.rfp_pdf && <div>{errors.rfp_pdf}</div>}
                  {errors.response_pdf && <div>{errors.response_pdf}</div>}
                </div>
              )}

              {createMutation.isError && (
                <div className="surface-soft p-4 text-sm text-red-600">
                  {(createMutation.error as any)?.response?.data?.detail || 'Failed to create project.'}
                </div>
              )}

              <div className="flex flex-wrap gap-3">
                <button type="submit" disabled={createDisabled} className="primary-button">
                  {createMutation.isPending ? 'Creating project...' : 'Create project'}
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    setShowForm(false)
                    setForm(initialForm)
                    setErrors({})
                    setRfpFile(null)
                    setResponseFile(null)
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div className="surface-soft mt-6 p-6">
              <div className="text-base font-bold text-slate-950">Ready for a new bid?</div>
              <p className="mt-2 text-sm text-slate-500">
                Open the intake form to register a project and upload the RFP and response PDFs. Analysis can then be run from the Analysis tab.
              </p>
              <button className="primary-button mt-5" onClick={() => setShowForm(true)}>
                <FolderPlus size={16} />
                Start a new project
              </button>
            </div>
          )}
        </section>

        <section className="surface p-6">
          <div className="page-header">
            <div>
              <div className="eyebrow">Project directory</div>
              <h2 className="section-title mt-2 text-xl">Active response projects</h2>
              <p className="section-subtitle">Open any project workspace to manage sections, collaborators, and response drafting.</p>
            </div>
            <div className="ui-badge ui-badge-neutral">{projects.length} project{projects.length === 1 ? '' : 's'}</div>
          </div>

          {isLoading ? (
            <div className="surface-soft mt-6 p-6 text-sm text-slate-500">Loading projects...</div>
          ) : projects.length === 0 ? (
            <div className="surface-soft mt-6 p-8 text-center">
              <div className="text-lg font-bold text-slate-950">No projects created yet</div>
              <p className="mt-2 text-sm text-slate-500">Your uploaded RFPs and bid responses will appear here once a project is created.</p>
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              {projects.map((project: any) => (
                <div key={project.id} className="surface-soft p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="text-lg font-bold text-slate-950">{project.title}</div>
                        <StatusBadge tone={STATUS_TONE[project.status] || 'neutral'}>{project.status}</StatusBadge>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-4 text-sm text-slate-500">
                        {project.issuer && <span>{project.issuer}</span>}
                        {project.deadline && <span>Due {project.deadline}</span>}
                        <span>{project.member_count} collaborators</span>
                        <span>{project.section_count} sections</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button className="secondary-button" onClick={() => navigate(`/projects/${project.id}/workspace`)}>
                        Open project
                        <ArrowRight size={15} />
                      </button>
                      <button
                        className="ghost-button"
                        onClick={() => {
                          if (confirm('Delete this project?')) deleteMutation.mutate(project.id)
                        }}
                      >
                        <Trash2 size={14} />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
