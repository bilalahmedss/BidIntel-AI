import api from './axios'

export const getProjects = () => api.get('/projects').then(r => r.data)
export const getProject  = (id: number) => api.get(`/projects/${id}`).then(r => r.data)
export const deleteProject = (id: number) => api.delete(`/projects/${id}`)
export const updateProject = (id: number, form: FormData) => api.patch(`/projects/${id}`, form).then(r => r.data)
export const addMember = (pid: number, email: string, role: string) =>
  api.post(`/projects/${pid}/members`, { email, role }).then(r => r.data)
export const removeMember = (pid: number, uid: number) => api.delete(`/projects/${pid}/members/${uid}`)

export function createProject(form: FormData) {
  return api.post('/projects', form).then(r => r.data)
}
