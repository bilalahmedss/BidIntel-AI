import { useState } from 'react'
import api from '../api/axios'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const [tab, setTab]         = useState<'login' | 'register'>('login')
  const [email, setEmail]     = useState('')
  const [password, setPass]   = useState('')
  const [fullName, setName]   = useState('')
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState('')

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      const r = await api.post('/auth/login', { email, password })
      login(r.data.access_token, r.data.user)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally { setLoading(false) }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault(); setError(''); setLoading(true)
    try {
      await api.post('/auth/register', { email, password, full_name: fullName })
      setSuccess('Account created — please log in.')
      setTab('login'); setPass('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-indigo-400">BidIntel AI</h1>
          <p className="text-slate-400 text-sm mt-1">Bid decision intelligence platform</p>
        </div>
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-6">
          <div className="flex mb-6 bg-slate-800 rounded-lg p-1 gap-1">
            {(['login', 'register'] as const).map(t => (
              <button key={t} onClick={() => { setTab(t); setError(''); setSuccess('') }}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors capitalize
                  ${tab === t ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}>
                {t}
              </button>
            ))}
          </div>
          {error   && <div className="mb-4 text-sm text-red-400 bg-red-900/30 border border-red-800 rounded p-3">{error}</div>}
          {success && <div className="mb-4 text-sm text-green-400 bg-green-900/30 border border-green-800 rounded p-3">{success}</div>}
          <form onSubmit={tab === 'login' ? handleLogin : handleRegister} className="space-y-4">
            {tab === 'register' && (
              <input className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                placeholder="Full Name" value={fullName} onChange={e => setName(e.target.value)} />
            )}
            <input type="email" className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
            <input type="password" className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
              placeholder="Password" value={password} onChange={e => setPass(e.target.value)} required />
            <button type="submit" disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors">
              {loading ? 'Please wait…' : tab === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
