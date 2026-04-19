import { NavLink } from 'react-router-dom'
import { LayoutDashboard, FolderKanban, ScanText, MessageSquare, BookOpen, LogOut } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

const links = [
  { to: '/',              label: 'Dashboard',       Icon: LayoutDashboard },
  { to: '/projects',      label: 'Projects',        Icon: FolderKanban },
  { to: '/analysis',      label: 'Analysis',        Icon: ScanText },
  { to: '/ask',           label: 'Ask',             Icon: MessageSquare },
  { to: '/knowledge-base',label: 'Knowledge Base',  Icon: BookOpen },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  return (
    <aside className="w-56 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-slate-800">
        <span className="text-indigo-400 font-bold text-lg tracking-tight">BidIntel AI</span>
      </div>
      <nav className="flex-1 py-4 space-y-1 px-2">
        {links.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
              ${isActive ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'}`
            }>
            <Icon size={16} />{label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-4 border-t border-slate-800">
        <div className="text-xs text-slate-400 truncate mb-2">{user?.full_name || user?.email}</div>
        <button onClick={logout}
          className="flex items-center gap-2 text-xs text-slate-500 hover:text-red-400 transition-colors">
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  )
}
