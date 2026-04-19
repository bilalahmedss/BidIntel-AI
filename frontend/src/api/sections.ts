import api from './axios'

export const getSections      = (pid: number) => api.get(`/projects/${pid}/sections`).then(r => r.data)
export const createSection    = (pid: number, title: string) => api.post(`/projects/${pid}/sections`, { title }).then(r => r.data)
export const updateSection    = (sid: number, data: object) => api.patch(`/sections/${sid}`, data).then(r => r.data)
export const deleteSection    = (sid: number) => api.delete(`/sections/${sid}`)
export const generateSections = (pid: number) => api.post(`/projects/${pid}/sections/generate`).then(r => r.data)
export const reorderSections  = (pid: number, order: { section_id: number; order_index: number }[]) =>
  api.patch(`/projects/${pid}/sections/reorder`, order).then(r => r.data)
