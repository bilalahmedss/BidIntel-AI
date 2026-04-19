import api from './axios'

export const getSafetySummary = () => api.get('/safety/summary').then(r => r.data)
export const getSafetyEvents = (limit = 25) => api.get(`/safety/events?limit=${limit}`).then(r => r.data)
