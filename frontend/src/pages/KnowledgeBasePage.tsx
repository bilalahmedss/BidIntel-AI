import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Trash2, Upload } from 'lucide-react'
import { deleteLookupDoc, getLookupDocs, uploadLookupDoc } from '../api/lookup'
import NoticePanel from '../components/governance/NoticePanel'
import { CONFIDENTIALITY_NOTICE } from '../governance'

export default function KnowledgeBasePage() {
  const qc = useQueryClient()
  const { data: docs = [] } = useQuery({ queryKey: ['lookup', 'docs'], queryFn: getLookupDocs })

  const deleteMut = useMutation({
    mutationFn: (filename: string) => deleteLookupDoc(filename),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lookup', 'docs'] }),
  })

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    try {
      for (const f of files) await uploadLookupDoc(f)
      qc.invalidateQueries({ queryKey: ['lookup', 'docs'] })
    } catch {
      alert('Upload failed.')
    } finally {
      e.target.value = ''
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Company Knowledge Base</h1>
      <p className="text-slate-400 text-sm mb-6">
        Upload your company's documents once - past proposals, certifications, CVs, financial statements, and capability statements.
        They are automatically searched during every bid analysis and Ask/Lookup experience.
      </p>

      <div className="mb-6">
        <NoticePanel variant="confidential" title="Confidentiality Warning" compact>
          {CONFIDENTIALITY_NOTICE}
        </NoticePanel>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 mb-6">
        <h2 className="font-semibold text-sm mb-4 flex items-center gap-2">
          <Upload size={14} /> Add Documents
        </h2>
        <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-700 hover:border-indigo-500 hover:bg-indigo-900/10 rounded-xl p-8 cursor-pointer transition-colors">
          <Upload size={28} className="text-slate-500 mb-3" />
          <span className="text-sm text-slate-300 font-medium">Click to upload PDF or TXT files</span>
          <span className="text-xs text-slate-500 mt-1">Company profiles · Certifications · CVs · Past proposals</span>
          <input type="file" multiple accept=".pdf,.txt" onChange={handleUpload} className="hidden" />
        </label>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <FileText size={14} /> Documents ({docs.length})
          </h2>
          {docs.length > 0 && <span className="text-xs text-amber-400">Confidential by default</span>}
        </div>
        {docs.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <FileText size={32} className="text-slate-700 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No documents yet.</p>
            <p className="text-slate-600 text-xs mt-1">Upload your company docs above to get started.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {docs.map((d: any) => (
              <div key={d.id} className="flex items-center justify-between px-5 py-3 hover:bg-slate-800/50 transition-colors">
                <div className="flex items-center gap-3">
                  <FileText size={14} className="text-slate-500 shrink-0" />
                  <div>
                    <div className="text-sm text-slate-200 font-medium">{d.filename}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {(d.size_bytes / 1024).toFixed(1)} KB · uploaded {d.uploaded_at?.slice(0, 10)}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => {
                    if (confirm(`Remove "${d.filename}" from the knowledge base?`)) deleteMut.mutate(d.filename)
                  }}
                  className="text-slate-600 hover:text-red-400 transition-colors p-1.5 rounded"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
