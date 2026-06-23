import { useState } from 'react'
import IndexMgmtPage from './pages/IndexMgmtPage'
import IndicatorDashboard from './pages/IndicatorDashboard'
import IndicatorDetailPage from './pages/IndicatorDetailPage'
import DataMonitorPage from './pages/DataMonitorPage'
import { login, getAuthUser, clearAuth } from './services/auth'
import type { AuthUser } from './services/auth'

type IndPage = 'dashboard' | 'detail' | 'monitor' | 'config'

function initialPageFromUrl(): IndPage {
  const value = new URLSearchParams(window.location.search).get('page')
  return value === 'detail' || value === 'monitor' || value === 'config' ? value : 'dashboard'
}

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员', analyst: '分析员', uploader: '上传员', viewer: '只读',
}

// ── Login ──────────────────────────────────────────────────────
function IndicatorLogin({ onLogin }: { onLogin: (u: AuthUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError('')
    try { onLogin(await login(username, password)) }
    catch (e: any) { setError(e.message) } finally { setLoading(false) }
  }

  return (
    <div className="ind-login-wrap">
      <form className="ind-login-card" onSubmit={handleSubmit}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ width: 52, height: 52, background: 'linear-gradient(135deg,#3b82f6,#1d4ed8)', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, margin: '0 auto 14px' }}>📊</div>
          <div style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 18, marginBottom: 4 }}>经营指数平台</div>
          <div style={{ color: '#4b5563', fontSize: 13 }}>请使用数据中台账户登录</div>
        </div>

        {error && (
          <div style={{ color: '#f87171', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 7, padding: '9px 13px', marginBottom: 16, fontSize: 13 }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: 12 }}>
          <input placeholder="用户名" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" />
        </div>
        <div style={{ marginBottom: 22 }}>
          <input type="password" placeholder="密码" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
        </div>
        <button type="submit" className="ind-login-btn" disabled={loading || !username || !password}>
          {loading ? '登录中…' : '登 录'}
        </button>
      </form>
    </div>
  )
}

// ── App ────────────────────────────────────────────────────────
export default function IndicatorApp() {
  const [user, setUser] = useState<AuthUser | null>(() => getAuthUser())
  const [page, setPage] = useState<IndPage>(() => initialPageFromUrl())

  if (!user) {
    return <IndicatorLogin onLogin={(u) => { setUser(u); setPage(initialPageFromUrl()) }} />
  }

  // 管理员和分析员可以编辑配置；所有人都能查看配置
  const canEdit   = ['admin', 'analyst'].includes(user.role)

  const now = new Date()
  const dateStr = now.toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
  })

  const NAV: { key: IndPage; label: string }[] = [
    { key: 'dashboard', label: '指数看板' },
    { key: 'detail',    label: '指标详情' },
    { key: 'monitor',   label: '数据监控' },
    { key: 'config',    label: '配置管理' },
  ]

  return (
    <div className="ind-root">
      {/* ── Header ── */}
      <header className="ind-header">
        {/* Logo */}
        <div className="ind-logo">
          <div className="ind-logo-icon">📊</div>
          <div className="ind-logo-text">
            <strong>经营指数平台</strong>
            <small>Index Platform</small>
          </div>
        </div>

        {/* Nav */}
        <nav className="ind-nav">
          {NAV.map(t => (
            <button
              key={t.key}
              type="button"
              className={`ind-nav-tab${page === t.key ? ' active' : ''}`}
              onClick={() => setPage(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {/* Right */}
        <div className="ind-header-right">
          <span className="ind-date">{dateStr}</span>
          <div className="ind-user">
            <div className="ind-avatar">{user.display_name.charAt(0).toUpperCase()}</div>
            <span className="ind-username">{user.display_name}</span>
            <span style={{ color: '#4b5563', fontSize: 12 }}>{ROLE_LABELS[user.role] ?? user.role}</span>
          </div>
          <button
            type="button"
            className="ind-logout"
            onClick={() => { clearAuth(); setUser(null) }}
          >
            退出
          </button>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="ind-main">
        {page === 'dashboard' && <IndicatorDashboard />}
        {page === 'detail'    && <IndicatorDetailPage />}
        {page === 'monitor'   && <DataMonitorPage />}
        {page === 'config' && (
          <IndexMgmtPage user={user} dark canEdit={canEdit} />
        )}
      </main>
    </div>
  )
}
