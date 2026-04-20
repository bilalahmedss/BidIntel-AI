import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Plus, Trash2, UserPlus } from 'lucide-react'
import { addMember, getProject } from '../api/projects'
import { createSection, deleteSection } from '../api/sections'
import SectionEditor from '../components/editor/SectionEditor'
import NoticePanel from '../components/governance/NoticePanel'
import StatusBadge from '../components/ui/StatusBadge'
import { CONFIDENTIALITY_NOTICE } from '../governance'

const SOURCE_TONE: Record<string, 'neutral' | 'info'> = {
  manual: 'neutral',
  auto: 'info',
}

function formatSectionSource(source: string) {
  if (source === 'auto') return 'Imported'
  if (source === 'manual') return 'Drafted'
  return source
}

export default function ProjectWorkspacePage() {
  const { id } = useParams<{ id: string }>()
  const projectId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [activeSectionId, setActiveSectionId] = useState<number | null>(null)
  const [newSectionTitle, setNewSectionTitle] = useState('')
  const [addingSection, setAddingSection] = useState(false)
  const [memberEmail, setMemberEmail] = useState('')
  const [showMemberForm, setShowMemberForm] = useState(false)

  const { data: project, isLoading } = useQuery({ queryKey: ['project', projectId], queryFn: () => getProject(projectId) })

  const addSectionMutation = useMutation({
    mutationFn: (title: string) => createSection(projectId, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      setNewSectionTitle('')
      setAddingSection(false)
    },
  })

  const deleteSectionMutation = useMutation({
    mutationFn: deleteSection,
    onSuccess: (_, sectionId) => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      if (activeSectionId === sectionId) setActiveSectionId(null)
    },
  })

  const addMemberMutation = useMutation({
    mutationFn: ({ email }: { email: string }) => addMember(projectId, email, 'editor'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      setMemberEmail('')
      setShowMemberForm(false)
    },
  })

  if (isLoading) return <div className="page"><div className="surface p-8 text-sm text-slate-500">Loading project workspace...</div></div>
  if (!project) return <div className="page"><div className="surface p-8 text-sm text-red-600">Project not found.</div></div>

  const sections = project.sections || []
  const activeSection = sections.find((section: any) => section.id === activeSectionId)
  const collaboratorCount = project.member_count ?? 0

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Project workspace</div>
          <h1 className="page-title">{project.title}</h1>
          <p className="page-description">Edit response sections, manage collaborators, and open analysis from here.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone="neutral">{sections.length} section{sections.length === 1 ? '' : 's'}</StatusBadge>
          <button className="ghost-button" onClick={() => navigate('/projects')}>
            <ArrowLeft size={15} />
            Back to projects
          </button>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="surface p-6 xl:sticky xl:top-[108px] xl:h-[calc(100vh-144px)] xl:overflow-y-auto">
          <div className="eyebrow">Project record</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusBadge tone="neutral">{project.issuer || 'No issuer listed'}</StatusBadge>
            {project.deadline && <StatusBadge tone="neutral">Due {project.deadline}</StatusBadge>}
            <StatusBadge tone="neutral">{collaboratorCount} collaborator{collaboratorCount === 1 ? '' : 's'}</StatusBadge>
          </div>

          <div className="mt-5 space-y-3">
            <NoticePanel variant="confidential" title="Confidential by default" compact>
              {CONFIDENTIALITY_NOTICE}
            </NoticePanel>

            <div className="surface-soft p-4">
              <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Project actions</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="primary-button" onClick={() => navigate(`/analysis?projectId=${projectId}`)}>
                  <ArrowRight size={15} />
                  Open analysis workspace
                </button>
                <button className="secondary-button" onClick={() => setShowMemberForm((current) => !current)}>
                  <UserPlus size={15} />
                  Add member
                </button>
              </div>
            </div>
          </div>

          {showMemberForm && (
            <div className="surface-soft mt-4 p-4">
              <div className="field-stack">
                <label className="field-label">Invite collaborator</label>
                <input value={memberEmail} onChange={(event) => setMemberEmail(event.target.value)} placeholder="proposal.manager@company.com" />
              </div>
              <div className="mt-3 flex gap-2">
                <button className="primary-button" onClick={() => addMemberMutation.mutate({ email: memberEmail })}>
                  Add member
                </button>
                <button className="secondary-button" onClick={() => setShowMemberForm(false)}>
                  Close
                </button>
              </div>
            </div>
          )}

          <div className="mt-6">
            <div className="flex items-center justify-between gap-3">
              <h2 className="section-title text-xl">Response sections</h2>
              <button className="ghost-button" onClick={() => setAddingSection((current) => !current)}>
                <Plus size={14} />
                Add section
              </button>
            </div>

            {addingSection && (
              <div className="surface-soft mt-4 p-4">
                <div className="field-stack">
                  <label className="field-label">Section title</label>
                  <input
                    autoFocus
                    value={newSectionTitle}
                    onChange={(event) => setNewSectionTitle(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && newSectionTitle.trim()) {
                        addSectionMutation.mutate(newSectionTitle.trim())
                      }
                    }}
                    placeholder="Executive summary"
                  />
                </div>
                <div className="mt-3 flex gap-2">
                  <button className="primary-button" onClick={() => newSectionTitle.trim() && addSectionMutation.mutate(newSectionTitle.trim())}>
                    Save section
                  </button>
                  <button className="secondary-button" onClick={() => setAddingSection(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            <div className="mt-4 space-y-3">
              {sections.map((section: any) => (
                <div
                  key={section.id}
                  onClick={() => setActiveSectionId(section.id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      setActiveSectionId(section.id)
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className={`surface-soft w-full cursor-pointer p-4 text-left transition ${
                    activeSectionId === section.id ? 'ring-2 ring-slate-300 shadow-lg' : 'hover:-translate-y-0.5 hover:shadow-lg'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-slate-950">{section.title}</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <StatusBadge tone={SOURCE_TONE[section.source] || 'neutral'}>{formatSectionSource(section.source)}</StatusBadge>
                        {section.content && <StatusBadge tone="neutral">{section.content.length} chars</StatusBadge>}
                      </div>
                    </div>
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        if (confirm('Delete section?')) deleteSectionMutation.mutate(section.id)
                      }}
                      className="ghost-button shrink-0"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <div className="min-w-0">
          <SectionEditor
            projectId={projectId}
            sectionId={activeSectionId}
            sectionTitle={activeSection?.title || ''}
            initialContent={activeSection?.content || ''}
          />
        </div>
      </div>
    </div>
  )
}
