import { useState } from 'react'
import { LockKeyhole, ShieldCheck } from 'lucide-react'
import api from '../api/axios'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/ui/StatusBadge'

export default function LoginPage() {
  const { login } = useAuth()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState('')

  async function handleLogin(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await api.post('/auth/login', { email, password })
      login(response.data.access_token, response.data.user)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api.post('/auth/register', { email, password, full_name: fullName })
      setSuccess('Account created successfully. Please sign in.')
      setTab('login')
      setPassword('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen p-5 md:p-8">
      <div className="mx-auto grid min-h-[calc(100vh-2.5rem)] max-w-6xl gap-6 lg:grid-cols-[minmax(0,1.15fr)_420px]">
        <section className="surface auth-shell auth-hero flex flex-col justify-between p-8 lg:p-12">
          <div>
            <div className="brand-mark">
              <span className="brand-mark-badge">BI</span>
              <div>
                <div className="text-xl text-white">BidIntel AI</div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-white/60">Bid decision intelligence platform</div>
              </div>
            </div>

            <div className="mt-12 max-w-2xl">
              <div className="eyebrow">Enterprise workspace</div>
              <h1 className="page-title text-white">Professional bid intelligence with guardrails built in.</h1>
              <p className="page-description text-white/75">
                Analyze RFPs, score response coverage, manage sections, and review safety controls from a clean enterprise interface built for proposal teams.
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {[
              ['Structured analysis', 'Parse RFPs, score requirements, and surface poison-pill risks.'],
              ['Grounded Q&A', 'Ask project-specific questions against your uploaded bid material.'],
              ['Responsible AI', 'PII redaction, audit logging, and human-review notices stay visible.'],
            ].map(([title, description]) => (
              <div key={title} className="auth-highlight-card p-5">
                <div className="text-sm font-bold text-white">{title}</div>
                <div className="mt-2 text-sm text-white/70">{description}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="surface surface-strong auth-panel flex flex-col justify-center p-8">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="eyebrow">Access</div>
              <h2 className="section-title mt-2 text-2xl text-slate-950">{tab === 'login' ? 'Sign in to your workspace' : 'Create your account'}</h2>
            </div>
            <StatusBadge tone="info">
              <ShieldCheck size={13} />
              Secure
            </StatusBadge>
          </div>

          <div className="segmented-control segmented-control-fill mt-6">
            {(['login', 'register'] as const).map((option) => (
              <button
                key={option}
                onClick={() => {
                  setTab(option)
                  setError('')
                  setSuccess('')
                }}
                className={`segmented-button segmented-button-fill ${tab === option ? 'segmented-button-active' : ''}`}
              >
                {option === 'login' ? 'Sign in' : 'Register'}
              </button>
            ))}
          </div>

          {error && <div className="surface-soft mt-5 p-4 text-sm text-red-600">{error}</div>}
          {success && <div className="surface-soft mt-5 p-4 text-sm text-emerald-700">{success}</div>}

          <form onSubmit={tab === 'login' ? handleLogin : handleRegister} className="mt-6 space-y-4">
            {tab === 'register' && (
              <div className="field-stack">
                <label className="field-label">Full name</label>
                <input value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Bid manager name" />
              </div>
            )}

            <div className="field-stack">
              <label className="field-label">Email</label>
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@company.com" required />
            </div>

            <div className="field-stack">
              <label className="field-label">Password</label>
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required />
            </div>

            <button type="submit" disabled={loading} className="primary-button w-full justify-center">
              <LockKeyhole size={15} />
              {loading ? 'Please wait...' : tab === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
