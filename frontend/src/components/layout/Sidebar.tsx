import { NavLink } from 'react-router-dom'
import { LayoutDashboard, FolderKanban, ScanText, MessageSquare, BookOpen, LogOut, ShieldCheck } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

const links = [
  { to: '/',              label: 'Dashboard',       Icon: LayoutDashboard },
  { to: '/projects',      label: 'Projects',        Icon: FolderKanban },
  { to: '/analysis',      label: 'Analysis',        Icon: ScanText },
  { to: '/ask',           label: 'Ask',             Icon: MessageSquare },
  { to: '/knowledge-base',label: 'Knowledge Base',  Icon: BookOpen },
  { to: '/safety',        label: 'Safety',          Icon: ShieldCheck },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  return (
    <aside className="app-sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <span className="brand-mark-badge">BI</span>
          <div>
            <div className="text-lg">BidIntel AI</div>
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Enterprise workspace</div>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="eyebrow px-3 pb-2">Navigation</div>
        {links.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Signed in</div>
        <div className="mt-2 text-sm font-bold text-slate-900">{user?.full_name || 'Bid team member'}</div>
        <div className="mt-1 text-sm text-slate-500 break-all">{user?.email}</div>
        <button onClick={() => { void logout() }} className="ghost-button mt-4 w-full justify-center">
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
