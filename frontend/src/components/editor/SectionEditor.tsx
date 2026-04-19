import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { updateSection } from '../../api/sections'

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
  const saveSeq = useRef(0)

  useEffect(() => {
    setContent(initialContent)
    setLastSavedContent(initialContent)
    setSaveStatus('saved')
  }, [initialContent, sectionId])

  useEffect(() => {
    if (!sectionId || content === lastSavedContent) {
      return
    }

    const currentSeq = ++saveSeq.current
    setSaveStatus('saving')
    const timer = window.setTimeout(async () => {
      try {
        const updated = await updateSection(sectionId, { content })
        if (saveSeq.current !== currentSeq) {
          return
        }
        const savedContent = updated.content ?? content
        setLastSavedContent(savedContent)
        setSaveStatus('saved')
        queryClient.setQueryData(['project', projectId], (prev: any) => {
          if (!prev?.sections) {
            return prev
          }
          return {
            ...prev,
            sections: prev.sections.map((section: any) =>
              section.id === sectionId ? { ...section, ...updated, content: savedContent } : section,
            ),
          }
        })
      } catch (_err) {
        if (saveSeq.current === currentSeq) {
          setSaveStatus('error')
        }
      }
    }, 300)

    return () => window.clearTimeout(timer)
  }, [content, lastSavedContent, projectId, queryClient, sectionId])

  if (!sectionId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a section to start editing
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="font-semibold text-slate-100 truncate max-w-lg">{sectionTitle}</h2>
        <div className="flex items-center gap-3">
          <span
            className={`text-xs ${
              saveStatus === 'saving'
                ? 'text-yellow-400'
                : saveStatus === 'error'
                  ? 'text-red-400'
                  : 'text-slate-500'
            }`}
          >
            {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'error' ? 'Save failed' : 'Saved'}
          </span>
        </div>
      </div>

      <textarea
        className="flex-1 bg-slate-900 text-slate-100 resize-none p-4 text-sm leading-relaxed focus:outline-none font-mono border-0"
        value={content}
        placeholder="Start writing your response for this section..."
        onChange={e => setContent(e.target.value)}
      />

      <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
        <span>{content.length} chars | {content.split(/\s+/).filter(Boolean).length} words</span>
        <span>Autosave after 300ms idle</span>
      </div>
    </div>
  )
}
