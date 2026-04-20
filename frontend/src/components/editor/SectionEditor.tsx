import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileEdit, LoaderCircle, TriangleAlert } from 'lucide-react'
import { updateSection } from '../../api/sections'
import StatusBadge from '../ui/StatusBadge'

interface Props {
  projectId: number
  sectionId: number | null
  sectionTitle: string
  initialContent: string
}

export default function SectionEditor({ projectId, sectionId, sectionTitle, initialContent }: Props) {
  const queryClient = useQueryClient()
  const [content, setContent] = useState(initialContent)
  const [lastSavedContent, setLastSavedContent] = useState(initialContent)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'error'>('saved')
  const saveSequence = useRef(0)

  useEffect(() => {
    setContent(initialContent)
    setLastSavedContent(initialContent)
    setSaveStatus('saved')
  }, [initialContent, sectionId])

  useEffect(() => {
    if (!sectionId || content === lastSavedContent) return

    const currentSequence = ++saveSequence.current
    setSaveStatus('saving')

    const timer = window.setTimeout(async () => {
      try {
        const updated = await updateSection(sectionId, { content })
        if (saveSequence.current !== currentSequence) return

        const savedContent = updated.content ?? content
        setLastSavedContent(savedContent)
        setSaveStatus('saved')
        queryClient.setQueryData(['project', projectId], (previous: any) => {
          if (!previous?.sections) return previous
          return {
            ...previous,
            sections: previous.sections.map((section: any) =>
              section.id === sectionId ? { ...section, ...updated, content: savedContent } : section,
            ),
          }
        })
      } catch {
        if (saveSequence.current === currentSequence) {
          setSaveStatus('error')
        }
      }
    }, 300)

    return () => window.clearTimeout(timer)
  }, [content, lastSavedContent, projectId, queryClient, sectionId])

  if (!sectionId) {
    return (
      <div className="surface h-full min-h-[680px] p-10 flex flex-col items-center justify-center text-center">
        <div className="rounded-full bg-slate-100 p-4 text-slate-700">
          <FileEdit size={28} />
        </div>
        <h2 className="mt-5 text-2xl font-bold tracking-tight text-slate-950">Select a section to begin editing</h2>
        <p className="mt-3 max-w-md text-sm text-slate-500">
          Choose a response section from the project list to draft content, refine language, and let autosave keep revisions synced.
        </p>
      </div>
    )
  }

  return (
    <div className="surface h-full min-h-[680px] overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-6 py-5">
        <div>
          <div className="eyebrow">Section editor</div>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">{sectionTitle}</h2>
        </div>
        <div className="flex items-center gap-3">
          {saveStatus === 'saving' && (
            <StatusBadge tone="info">
              <LoaderCircle size={13} className="animate-spin" />
              Saving
            </StatusBadge>
          )}
          {saveStatus === 'saved' && (
            <StatusBadge tone="success">
              <CheckCircle2 size={13} />
              Saved
            </StatusBadge>
          )}
          {saveStatus === 'error' && (
            <StatusBadge tone="danger">
              <TriangleAlert size={13} />
              Save failed
            </StatusBadge>
          )}
        </div>
      </div>

      <textarea
        className="editor-textarea"
        value={content}
        placeholder="Start drafting your response for this section..."
        onChange={(event) => setContent(event.target.value)}
      />

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-6 py-4 text-sm text-slate-500">
        <span>
          {content.length} characters | {content.split(/\s+/).filter(Boolean).length} words
        </span>
        <span>Autosave triggers after 300 ms of idle time</span>
      </div>
    </div>
  )
}
