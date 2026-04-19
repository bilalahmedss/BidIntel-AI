import api from './axios'

export const getLookupDocs = () => api.get('/lookup/docs').then(r => r.data)
export const deleteLookupDoc = (filename: string) => api.delete(`/lookup/doc/${encodeURIComponent(filename)}`)
export const searchLookup = (query: string, top_k = 5) =>
  api.post('/lookup/search', { query, top_k }).then(r => r.data)
export function uploadLookupDoc(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/lookup/upload', form).then(r => r.data)
}
