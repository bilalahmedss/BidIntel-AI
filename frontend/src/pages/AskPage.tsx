import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MessageSquareText, Send, Trash2 } from 'lucide-react'
import { clearHistory, getChatHistory, streamAsk } from '../api/ask'
import { getProjects } from '../api/projects'
import { getSafetySummary } from '../api/safety'
import { useAuth } from '../context/AuthContext'
import AssurancePanel from '../components/governance/AssurancePanel'
import NoticePanel from '../components/governance/NoticePanel'
import RichMarkdown from '../components/ui/RichMarkdown'
import StatusBadge from '../components/ui/StatusBadge'
import { CONFIDENTIALITY_NOTICE, HUMAN_REVIEW_NOTICE } from '../governance'

interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
}

export default function AskPage() {
  const { user } = useAuth()
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const { data: safetySummary } = useQuery({ queryKey: ['safety', 'summary'], queryFn: getSafetySummary })

  const [projectId, setProjectId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!projectId) {
      setMessages([])
      return
    }
    getChatHistory(projectId).then(setMessages)
  }, [projectId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function sendMessage() {
    if (!input.trim() || loading || !projectId) return

    const question = input.trim()
    setInput('')
    setMessages((current) => [...current, { role: 'user', content: question }, { role: 'assistant', content: '', streaming: true }])
    setLoading(true)

    let buffer = ''
    streamAsk(
      projectId,
      question,
      (chunk) => {
        buffer += chunk
        setMessages((current) => {
          const next = [...current]
          const last = next[next.length - 1]
          if (last?.streaming) next[next.length - 1] = { ...last, content: buffer }
          return next
        })
      },
      () => {
        setLoading(false)
        setMessages((current) => {
          const next = [...current]
          const last = next[next.length - 1]
          if (last?.streaming) next[next.length - 1] = { ...last, streaming: false }
          return next
        })
      },
      (replacement) => {
        buffer = replacement
        setMessages((current) => {
          const next = [...current]
          const last = next[next.length - 1]
          if (last?.streaming) next[next.length - 1] = { ...last, content: buffer }
          return next
        })
      },
    )
  }

  async function handleClear() {
    if (!projectId || !confirm('Clear chat history?')) return
    await clearHistory(projectId)
    setMessages([])
  }

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Guided Q&A</div>
          <h1 className="page-title">Ask grounded questions against your project context.</h1>
          <p className="page-description">
            Responses are grounded on the project RFP, uploaded bid response, knowledge base documents, and the latest analysis output.
          </p>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-6 xl:sticky xl:top-[108px] xl:h-[calc(100vh-144px)] xl:overflow-y-auto">
          <section className="surface p-6">
            <div className="eyebrow">Input pane</div>
            <h2 className="section-title mt-2 text-xl">Conversation setup</h2>
            <p className="section-subtitle">Choose the project context first so the assistant can ground answers on the correct bid material.</p>

            <div className="mt-6 space-y-4">
              <div className="field-stack">
                <label className="field-label">Project context</label>
                <select value={projectId ?? ''} onChange={(event) => setProjectId(event.target.value ? Number(event.target.value) : null)}>
                  <option value="">Select a project</option>
                  {projects.map((project: any) => (
                    <option key={project.id} value={project.id}>
                      {project.title}
                    </option>
                  ))}
                </select>
                <div className="field-help">The assistant uses the selected project's RFP, response, sections, and prior analysis context.</div>
              </div>

              {projectId && messages.length > 0 && (
                <button className="secondary-button w-full justify-center" onClick={handleClear}>
                  <Trash2 size={15} />
                  Clear conversation history
                </button>
              )}
            </div>
          </section>

          <section className="space-y-3">
            <NoticePanel variant="confidential" title="Confidentiality notice" compact>
              {CONFIDENTIALITY_NOTICE} Avoid entering unnecessary personal or business-sensitive detail in free-form prompts.
            </NoticePanel>
            <NoticePanel variant="review" title="Human review required" compact>
              {HUMAN_REVIEW_NOTICE}
            </NoticePanel>
          </section>

          <AssurancePanel summary={safetySummary} mode="ask" />
        </aside>

        <section className="surface p-6 conversation-shell min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-5">
            <div>
              <div className="eyebrow">Insights pane</div>
              <h2 className="section-title mt-2 text-xl">Conversation stream</h2>
              <p className="section-subtitle">Markdown answers are rendered into readable cards rather than raw text dumps.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone={projectId ? 'info' : 'warn'}>{projectId ? 'Project context active' : 'Select project context'}</StatusBadge>
              <StatusBadge tone="neutral">{messages.length} message{messages.length === 1 ? '' : 's'}</StatusBadge>
            </div>
          </div>

          <div className="conversation-stream mt-6 space-y-4">
            {messages.length === 0 ? (
              <div className="surface-soft p-10 text-center">
                <div className="inline-flex rounded-full bg-slate-100 p-4 text-slate-700">
                  <MessageSquareText size={28} />
                </div>
                <h3 className="mt-5 text-2xl font-extrabold tracking-tight text-slate-950">Ask anything about the bid.</h3>
                <p className="mt-3 text-sm text-slate-500">
                  Try questions about submission requirements, certifications, capability gaps, past performance, or the current response draft.
                </p>
              </div>
            ) : (
              messages.map((message, index) => (
                <div key={message.id ?? index} className={message.role === 'assistant' ? 'assistant-card' : 'user-card'}>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-sm font-bold text-slate-950">{message.role === 'assistant' ? 'BidIntel AI' : user?.full_name || 'You'}</div>
                    <StatusBadge tone={message.role === 'assistant' ? 'info' : 'neutral'}>
                      {message.role === 'assistant' ? 'Assistant' : 'User'}
                    </StatusBadge>
                  </div>
                  {message.role === 'assistant' ? (
                    <RichMarkdown content={message.content || (message.streaming ? '...' : '')} />
                  ) : (
                    <div className="whitespace-pre-wrap text-sm text-slate-700">{message.content}</div>
                  )}
                </div>
              ))
            )}
            <div ref={bottomRef} />
          </div>

          <div className="mt-6 border-t border-slate-100 pt-5">
            {!projectId && (
              <div className="surface-soft mb-4 p-4 text-sm text-amber-700">
                Select a project first to include its RFP, response, and analysis context in the conversation.
              </div>
            )}

            <div className="surface-soft p-4">
              <label className="field-label">Question</label>
              <textarea
                value={input}
                disabled={!projectId}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder={projectId ? 'Ask about requirements, gaps, risks, certifications, or proposal language...' : 'Select a project first'}
                className="mt-3 min-h-[130px]"
              />
              <div className="mt-4 flex items-center justify-between gap-3">
                <div className="text-xs text-slate-500">Press Enter to send, Shift+Enter for a new line.</div>
                <button className="primary-button" disabled={loading || !input.trim() || !projectId} onClick={sendMessage}>
                  <Send size={15} />
                  {loading ? 'Streaming answer...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
