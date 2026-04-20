import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Search, Trash2, UploadCloud } from 'lucide-react'
import { deleteLookupDoc, getLookupDocs, searchLookup, uploadLookupDoc } from '../api/lookup'
import NoticePanel from '../components/governance/NoticePanel'
import RichMarkdown from '../components/ui/RichMarkdown'
import StatusBadge from '../components/ui/StatusBadge'
import { CONFIDENTIALITY_NOTICE, HUMAN_REVIEW_NOTICE } from '../governance'

export default function LookupPage() {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<any>(null)
  const [searching, setSearching] = useState(false)
  const [uploading, setUploading] = useState(false)

  const { data: documents = [] } = useQuery({ queryKey: ['lookup', 'docs'], queryFn: getLookupDocs })

  const deleteMutation = useMutation({
    mutationFn: (filename: string) => deleteLookupDoc(filename),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['lookup', 'docs'] }),
  })

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    setSearching(true)
    setResult(null)

    try {
      setResult(await searchLookup(query.trim()))
    } catch {
      alert('Search failed.')
    } finally {
      setSearching(false)
    }
  }

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || [])
    if (!files.length) return

    setUploading(true)
    try {
      for (const file of files) {
        await uploadLookupDoc(file)
      }
      queryClient.invalidateQueries({ queryKey: ['lookup', 'docs'] })
    } catch {
      alert('Upload failed.')
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Lookup</div>
          <h1 className="page-title">Search reusable company knowledge with structured results.</h1>
          <p className="page-description">
            Query uploaded reference material and review the summary plus supporting source excerpts in a readable, card-based layout.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <NoticePanel variant="confidential" title="Confidentiality notice" compact>
          {CONFIDENTIALITY_NOTICE}
        </NoticePanel>
        <NoticePanel variant="review" title="Human review required" compact>
          {HUMAN_REVIEW_NOTICE}
        </NoticePanel>
      </section>

      <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="surface p-6">
          <div className="eyebrow">Input pane</div>
          <h2 className="section-title mt-2 text-xl">Search and upload</h2>
          <p className="section-subtitle">Search indexed documents and expand the knowledge base from the same control pane.</p>

          <form onSubmit={handleSearch} className="mt-6 space-y-4">
            <div className="field-stack">
              <label className="field-label">Search query</label>
              <div className="relative">
                <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search certifications, delivery experience, or capabilities..." className="pl-11" />
              </div>
            </div>
            <button className="primary-button w-full justify-center" type="submit" disabled={searching || !query.trim()}>
              <Search size={15} />
              {searching ? 'Searching...' : 'Search knowledge base'}
            </button>
          </form>

          <label className="upload-zone mt-6 cursor-pointer">
            <UploadCloud size={28} className="text-blue-600" />
            <div className="text-base font-bold text-slate-950">{uploading ? 'Uploading and indexing...' : 'Upload PDF or TXT documents'}</div>
            <div className="text-sm text-slate-500">Company profiles, certifications, CVs, financials, and past proposals.</div>
            <input type="file" multiple accept=".pdf,.txt" className="hidden" onChange={handleUpload} disabled={uploading} />
          </label>
        </section>

        <section className="space-y-6 min-w-0">
          {result && (
            <div className="surface p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="eyebrow">Insights pane</div>
                  <h2 className="section-title mt-2 text-xl">Search summary</h2>
                </div>
                <StatusBadge tone="info">{result.query}</StatusBadge>
              </div>

              <div className="mt-5">
                <RichMarkdown content={result.summary || ''} />
              </div>

              {result.chunks?.length > 0 && (
                <div className="mt-6 space-y-3">
                  <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Source excerpts</div>
                  {result.chunks.map((chunk: string, index: number) => (
                    <div key={index} className="surface-soft p-4">
                      <RichMarkdown content={chunk.slice(0, 500) + (chunk.length > 500 ? '...' : '')} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="surface p-6">
            <div className="page-header">
              <div>
                <div className="eyebrow">Indexed files</div>
                <h2 className="section-title mt-2 text-xl">Knowledge base library</h2>
              </div>
              <StatusBadge tone="neutral">{documents.length} docs</StatusBadge>
            </div>

            {documents.length === 0 ? (
              <div className="surface-soft mt-6 p-8 text-center">
                <FileText size={30} className="mx-auto text-slate-400" />
                <div className="mt-4 text-lg font-bold text-slate-950">No documents uploaded yet</div>
                <p className="mt-2 text-sm text-slate-500">Use the left pane to upload material for search and analysis.</p>
              </div>
            ) : (
              <div className="mt-6 space-y-4">
                {documents.map((document: any) => (
                  <div key={document.id} className="surface-soft p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="text-base font-bold text-slate-950">{document.filename}</div>
                        <div className="mt-2 text-sm text-slate-500">
                          {(document.size_bytes / 1024).toFixed(1)} KB · Uploaded {document.uploaded_at?.slice(0, 10)}
                        </div>
                      </div>
                      <button
                        className="ghost-button"
                        onClick={() => {
                          if (confirm('Remove this document?')) deleteMutation.mutate(document.filename)
                        }}
                      >
                        <Trash2 size={14} />
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
