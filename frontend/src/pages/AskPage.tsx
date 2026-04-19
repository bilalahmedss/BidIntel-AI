import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getProjects } from '../api/projects'
import { getChatHistory, streamAsk, clearHistory } from '../api/ask'
import ReactMarkdown from 'react-markdown'
import { Send, Trash2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

interface Message { id?: number; role: 'user' | 'assistant'; content: string; streaming?: boolean }

export default function AskPage() {
  const { user } = useAuth()
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: getProjects })
  const [pid, setPid]         = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!pid) { setMessages([]); return }
    getChatHistory(pid).then(setMessages)
  }, [pid])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  function send() {
    if (!input.trim() || loading || !pid) return
    const q = input.trim(); setInput('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)
    const idx = -1
    let buf = ''
    setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])
    streamAsk(pid, q, chunk => {
      buf += chunk
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last.streaming) msgs[msgs.length - 1] = { ...last, content: buf }
        return msgs
      })
    }, () => {
      setLoading(false)
      setMessages(prev => {
        const msgs = [...prev]
        const last = msgs[msgs.length - 1]
        if (last.streaming) msgs[msgs.length - 1] = { ...last, streaming: false }
        return msgs
      })
    })
  }

  async function handleClear() {
    if (!pid || !confirm('Clear chat history?')) return
    await clearHistory(pid)
    setMessages([])
  }

  return (
    <div className="flex flex-col h-[calc(100vh-96px)] max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Ask</h1>
        <div className="flex items-center gap-3">
          <select value={pid ?? ''} onChange={e => setPid(e.target.value ? Number(e.target.value) : null)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none">
            <option value="">No project context</option>
            {projects.map((p: any) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
          {pid && messages.length > 0 && (
            <button onClick={handleClear} className="text-slate-500 hover:text-red-400 transition-colors"><Trash2 size={15} /></button>
          )}
        </div>
      </div>

      {!pid && (
        <div className="mb-3 bg-amber-900/30 border border-amber-700 rounded-lg px-4 py-2 text-xs text-amber-300">
          Select a project to include RFP and response context in answers.
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
        {messages.length === 0 && (
          <div className="text-center text-slate-500 text-sm mt-16">
            <p className="text-lg mb-2">👋 Ask anything</p>
            <p>Ask about tender requirements, your bid response, certifications, past projects…</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">AI</div>
            )}
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed
              ${m.role === 'user' ? 'bg-indigo-600 text-white rounded-br-sm' : 'bg-slate-800 text-slate-100 rounded-bl-sm'}`}>
              {m.role === 'assistant'
                ? <ReactMarkdown className="prose prose-invert prose-sm max-w-none">{m.content || (m.streaming ? '▌' : '')}</ReactMarkdown>
                : m.content}
            </div>
            {m.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-slate-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                {user?.full_name?.[0]?.toUpperCase() || '?'}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="bg-slate-900 border border-slate-700 rounded-xl flex items-end gap-2 p-3">
        <textarea value={input} onChange={e => setInput(e.target.value)} disabled={!pid}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={pid ? 'Ask about your RFP, bid response, or company capabilities…' : 'Select a project first'}
          rows={1} className="flex-1 bg-transparent text-sm text-slate-100 resize-none focus:outline-none placeholder-slate-500 max-h-32" />
        <button onClick={send} disabled={loading || !input.trim() || !pid}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white p-2 rounded-lg transition-colors shrink-0">
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}
