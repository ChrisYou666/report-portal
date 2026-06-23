import { useState } from 'react'
import BatchPage from './pages/BatchPage'
import DashboardPage from './pages/DashboardPage'
import EntryPage from './pages/EntryPage'
import LoginPage from './pages/LoginPage'
import MasterDataPage from './pages/MasterDataPage'
import QueryPage from './pages/QueryPage'
import ReportPage from './pages/ReportPage'
import UploadPage from './pages/UploadPage'
import UsersPage from './pages/UsersPage'
import { clearAuth, getAuthUser } from './services/auth'
import type { AuthUser } from './services/auth'
import { useI18n } from './i18n'
import './App.css'

type PageKey = 'dashboard' | 'upload' | 'entry' | 'batches' | 'reports' | 'query' | 'users' | 'master'

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员', analyst: '分析员', uploader: '上传员', viewer: '只读',
}

type NavItem = { key: PageKey; label: string; icon: string; roles?: string[] }
type NavGroup = { label: string; items: NavItem[]; roles?: string[] }

const NAV_GROUPS: NavGroup[] = [
  {
    label: '数据采集',
    items: [
      { key: 'upload', label: '文件上传', icon: '↑' },
      { key: 'entry', label: '在线填报', icon: '✎' },
    ],
  },
  {
    label: '数据处理',
    items: [
      { key: 'batches', label: '批次流程', icon: '⊞' },
    ],
  },
  {
    label: '数据分析',
    items: [
      { key: 'query', label: '指标分析', icon: '⊙' },
      { key: 'reports', label: '日报管理', icon: '▦' },
    ],
  },
  {
    label: '系统管理',
    roles: ['admin'],
    items: [
      { key: 'users', label: '用户管理', icon: '⊕', roles: ['admin'] },
      { key: 'master', label: '主数据管理', icon: '◫', roles: ['admin'] },
    ],
  },
]

function App() {
  const { language, setLanguage, t } = useI18n()
  const [user, setUser] = useState<AuthUser | null>(() => getAuthUser())
  const [activePage, setActivePage] = useState<PageKey>('dashboard')

  if (!user) {
    return <LoginPage onLogin={(u) => { setUser(u); setActivePage('dashboard') }} />
  }

  function canSee(roles?: string[]) {
    return !roles || roles.includes(user!.role)
  }

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        {/* Brand */}
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">⬡</span>
          <div>
            <strong>{t.nav.brand}</strong>
            <small>{t.nav.subtitle}</small>
          </div>
        </div>

        {/* Nav */}
        <nav className="sidebar-nav">
          {/* 工作台 — standalone */}
          <button
            className={`sidebar-nav-item${activePage === 'dashboard' ? ' active' : ''}`}
            type="button"
            onClick={() => setActivePage('dashboard')}
          >
            <span className="sidebar-nav-icon">◈</span>
            工作台
          </button>

          {/* Groups */}
          {NAV_GROUPS.map(group => {
            if (!canSee(group.roles)) return null
            const visibleItems = group.items.filter(it => canSee(it.roles))
            if (visibleItems.length === 0) return null
            return (
              <div key={group.label} className="sidebar-nav-group">
                <span className="sidebar-nav-group-label">{group.label}</span>
                {visibleItems.map(item => (
                  <button
                    key={item.key}
                    className={`sidebar-nav-item sidebar-nav-child${activePage === item.key ? ' active' : ''}`}
                    type="button"
                    onClick={() => setActivePage(item.key)}
                  >
                    <span className="sidebar-nav-icon">{item.icon}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-avatar">{user.display_name.charAt(0).toUpperCase()}</div>
            <div className="sidebar-user-info">
              <span>{user.display_name}</span>
              <small className="role-badge" data-role={user.role}>{ROLE_LABELS[user.role] ?? user.role}</small>
            </div>
          </div>
          <div className="sidebar-actions">
            <div className="language-switch">
              <button className={language === 'zh' ? 'active' : ''} type="button" onClick={() => setLanguage('zh')}>中</button>
              <button className={language === 'id' ? 'active' : ''} type="button" onClick={() => setLanguage('id')}>ID</button>
            </div>
            <button type="button" className="sidebar-logout" onClick={() => { clearAuth(); setUser(null) }}>退出</button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-content">
        <div hidden={activePage !== 'dashboard'}>
          <DashboardPage onOpenPage={(p) => setActivePage(p as PageKey)} />
        </div>
        <div hidden={activePage !== 'upload'}><UploadPage /></div>
        <div hidden={activePage !== 'entry'}><EntryPage /></div>
        <div hidden={activePage !== 'batches'}><BatchPage /></div>
        <div hidden={activePage !== 'reports'}><ReportPage /></div>
        <div hidden={activePage !== 'query'}><QueryPage /></div>
        {user.role === 'admin' && (
          <div hidden={activePage !== 'users'}><UsersPage /></div>
        )}
        {user.role === 'admin' && (
          <div hidden={activePage !== 'master'}><MasterDataPage /></div>
        )}
      </main>
    </div>
  )
}

export default App
