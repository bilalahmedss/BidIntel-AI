import { useEffect } from 'react'
import { useSectionSocket } from '../../hooks/useWebSocket'

interface Props { sectionId: number | null; sectionTitle: string }

export default function SectionEditor({ sectionId, sectionTitle }: Props) {
  const { content, handleChange, presence, lockHolder, saveStatus, requestLock, releaseLock } =
    useSectionSocket(sectionId)

  const isLockedByOther = lockHolder !== null

  if (!sectionId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        Select a section to start editing
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="font-semibold text-slate-100 truncate max-w-lg">{sectionTitle}</h2>
        <div className="flex items-center gap-3">
          {/* Presence chips */}
          <div className="flex -space-x-1">
            {presence.map(u => (
              <div key={u.user_id} title={u.full_name}
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-slate-900 ring-2 ring-slate-900"
                style={{ backgroundColor: u.color }}>
                {u.full_name[0]?.toUpperCase()}
              </div>
            ))}
          </div>
          <span className={`text-xs ${saveStatus === 'saving' ? 'text-yellow-400' : 'text-slate-500'}`}>
            {saveStatus === 'saving' ? 'Saving…' : 'Saved'}
          </span>
        </div>
      </div>

      {/* Lock banner */}
      {isLockedByOther && (
        <div className="bg-amber-900/40 border-b border-amber-700 px-4 py-2 text-sm text-amber-300 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse inline-block" />
          <strong>{lockHolder.full_name}</strong> is editing this section
        </div>
      )}

      {/* Editor */}
      <textarea
        className={`flex-1 bg-slate-900 text-slate-100 resize-none p-4 text-sm leading-relaxed focus:outline-none
          font-mono border-0 ${isLockedByOther ? 'opacity-60 cursor-not-allowed' : ''}`}
        value={content}
        readOnly={isLockedByOther}
        placeholder="Start writing your response for this section…"
        onFocus={requestLock}
        onBlur={releaseLock}
        onChange={e => handleChange(e.target.value)}
      />

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
        <span>{content.length} chars · {content.split(/\s+/).filter(Boolean).length} words</span>
        {presence.length > 0 && (
          <span>{presence.length} user{presence.length !== 1 ? 's' : ''} in this section</span>
        )}
      </div>
    </div>
  )
}
