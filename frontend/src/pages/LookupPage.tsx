import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getLookupDocs, deleteLookupDoc, uploadLookupDoc, searchLookup } from '../api/lookup'
import ReactMarkdown from 'react-markdown'
import { Search, Upload, Trash2, FileText } from 'lucide-react'
import NoticePanel from '../components/governance/NoticePanel'
import { CONFIDENTIALITY_NOTICE, HUMAN_REVIEW_NOTICE } from '../governance'

export default function LookupPage() {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<any>(null)
  const [searching, setSearch] = useState(false)
  const [uploading, setUploading] = useState(false)

  const { data: docs = [] } = useQuery({ queryKey: ['lookup', 'docs'], queryFn: getLookupDocs })

  const deleteMut = useMutation({
    mutationFn: (filename: string) => deleteLookupDoc(filename),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lookup', 'docs'] }),
  })

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setSearch(true)
    setResult(null)
    try {
      setResult(await searchLookup(query.trim()))
    } catch {
      alert('Search failed.')
    } finally {
      setSearch(false)
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    try {
      for (const f of files) await uploadLookupDoc(f)
      qc.invalidateQueries({ queryKey: ['lookup', 'docs'] })
    } catch {
      alert('Upload failed.')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">LookUp - Company Knowledge Base</h1>

      <div className="space-y-3 mb-6">
        <NoticePanel variant="confidential" title="Confidentiality Warning" compact>
          {CONFIDENTIALITY_NOTICE}
        </NoticePanel>
        <NoticePanel variant="review" title="Human Review Required" compact>
          {HUMAN_REVIEW_NOTICE}
        </NoticePanel>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3 mb-6">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search certifications, past projects, capabilities..."
            className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 pl-10 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          type="submit"
          disabled={searching || !query.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-6 py-3 rounded-xl text-sm font-medium transition-colors"
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
      </form>

      {result && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
          <h2 className="font-semibold text-sm text-slate-400 mb-3">Results for "{result.query}"</h2>
          <div className="mb-4">
            <NoticePanel variant="review" title="Review This Summary" compact>
              Verify any capability, certification, or compliance claim against the original uploaded document excerpts before reuse.
            </NoticePanel>
          </div>
          <div className="prose prose-invert prose-sm max-w-none text-slate-100">
            <ReactMarkdown>{result.summary}</ReactMarkdown>
          </div>
          {result.chunks?.length > 0 && (
            <details className="mt-4">
              <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-300">
                View {result.chunks.length} source excerpt{result.chunks.length !== 1 ? 's' : ''}
              </summary>
              <div className="mt-3 space-y-3">
                {result.chunks.map((c: string, i: number) => (
                  <div key={i} className="bg-slate-800 rounded p-3 text-xs text-slate-400 font-mono whitespace-pre-wrap">
                    {c.slice(0, 500)}
                    {c.length > 500 ? '...' : ''}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h2 className="font-semibold text-sm mb-4 flex items-center gap-2">
              <Upload size={14} /> Upload Documents
            </h2>
            <label
              className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors ${
                uploading ? 'border-indigo-600 bg-indigo-900/20' : 'border-slate-700 hover:border-indigo-600 hover:bg-indigo-900/10'
              }`}
            >
              <Upload size={24} className="text-slate-500 mb-2" />
              <span className="text-xs text-slate-400 text-center">{uploading ? 'Uploading and indexing...' : 'Click to upload PDF or TXT'}</span>
              <span className="text-xs text-slate-600 mt-1">Company profiles, certifications, CVs, financials</span>
              <input type="file" multiple accept=".pdf,.txt" onChange={handleUpload} className="hidden" disabled={uploading} />
            </label>
          </div>
        </div>

        <div className="col-span-2">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-800">
              <h2 className="font-semibold text-sm flex items-center gap-2">
                <FileText size={14} /> Knowledge Base ({docs.length} docs)
              </h2>
            </div>
            {docs.length === 0 ? (
              <div className="px-5 py-8 text-slate-500 text-sm text-center">No documents uploaded yet.</div>
            ) : (
              <div className="divide-y divide-slate-800">
                {docs.map((d: any) => (
                  <div key={d.id} className="flex items-center justify-between px-5 py-3 hover:bg-slate-800/50 transition-colors">
                    <div>
                      <div className="text-sm text-slate-200 font-medium">{d.filename}</div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {(d.size_bytes / 1024).toFixed(1)} KB · {d.uploaded_at?.slice(0, 10)}
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        if (confirm('Remove this document?')) deleteMut.mutate(d.filename)
                      }}
                      className="text-slate-600 hover:text-red-400 transition-colors p-1.5"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
