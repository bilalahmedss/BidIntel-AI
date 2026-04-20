import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, ShieldCheck, Trash2, UploadCloud } from 'lucide-react'
import { deleteLookupDoc, getLookupDocs, uploadLookupDoc } from '../api/lookup'
import NoticePanel from '../components/governance/NoticePanel'
import StatusBadge from '../components/ui/StatusBadge'
import { CONFIDENTIALITY_NOTICE } from '../governance'

export default function KnowledgeBasePage() {
  const queryClient = useQueryClient()
  const { data: documents = [] } = useQuery({ queryKey: ['lookup', 'docs'], queryFn: getLookupDocs })

  const deleteMutation = useMutation({
    mutationFn: (filename: string) => deleteLookupDoc(filename),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['lookup', 'docs'] }),
  })

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || [])
    if (!files.length) return

    try {
      for (const file of files) {
        await uploadLookupDoc(file)
      }
      queryClient.invalidateQueries({ queryKey: ['lookup', 'docs'] })
    } catch {
      alert('Upload failed.')
    } finally {
      event.target.value = ''
    }
  }

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Knowledge base</div>
          <h1 className="page-title">Centralize reusable company evidence for every bid.</h1>
          <p className="page-description">
            Upload certifications, capability statements, CVs, financials, and past proposals once so analysis and Q&A can ground on them automatically.
          </p>
        </div>
        <StatusBadge tone="info">
          <ShieldCheck size={13} />
          Confidential by default
        </StatusBadge>
      </section>

      <NoticePanel variant="confidential" title="Confidentiality notice" compact>
        {CONFIDENTIALITY_NOTICE}
      </NoticePanel>

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.2fr)]">
        <section className="surface p-6">
          <div className="eyebrow">Input pane</div>
          <h2 className="section-title mt-2 text-xl">Upload reference material</h2>
          <p className="section-subtitle">Accepted formats: PDF and TXT. Documents are indexed for analysis, Ask, and retrieval workflows.</p>

          <label className="upload-zone mt-6 cursor-pointer">
            <UploadCloud size={30} className="text-blue-600" />
            <div className="text-base font-bold text-slate-950">Click to add company documents</div>
            <div className="text-sm text-slate-500">Capability statements, past proposals, certifications, CVs, financial statements, and more.</div>
            <input type="file" multiple accept=".pdf,.txt" className="hidden" onChange={handleUpload} />
          </label>
        </section>

        <section className="surface p-6">
          <div className="page-header">
            <div>
              <div className="eyebrow">Insights pane</div>
              <h2 className="section-title mt-2 text-xl">Indexed documents</h2>
              <p className="section-subtitle">Every document below is available for grounded retrieval across the platform.</p>
            </div>
            <StatusBadge tone="neutral">{documents.length} document{documents.length === 1 ? '' : 's'}</StatusBadge>
          </div>

          {documents.length === 0 ? (
            <div className="surface-soft mt-6 p-10 text-center">
              <FileText size={32} className="mx-auto text-slate-400" />
              <div className="mt-4 text-lg font-bold text-slate-950">No knowledge documents uploaded yet</div>
              <p className="mt-2 text-sm text-slate-500">Upload reusable company evidence in the left pane to start grounding responses.</p>
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              {documents.map((document: any) => (
                <div key={document.id} className="surface-soft p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <div className="truncate text-base font-bold text-slate-950">{document.filename}</div>
                        <StatusBadge tone="neutral">Indexed</StatusBadge>
                      </div>
                      <div className="mt-2 text-sm text-slate-500">
                        {(document.size_bytes / 1024).toFixed(1)} KB · Uploaded {document.uploaded_at?.slice(0, 10)}
                      </div>
                    </div>
                    <button
                      className="ghost-button"
                      onClick={() => {
                        if (confirm(`Remove "${document.filename}" from the knowledge base?`)) {
                          deleteMutation.mutate(document.filename)
                        }
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
        </section>
      </div>
    </div>
  )
}
