import { useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

type User = {
  id: number
  username: string
  display_name: string
  role: string
  department: string
  site: string
  is_active: boolean
  created_at: string
}

type UserForm = {
  username: string
  password: string
  display_name: string
  role: string
  department: string
  site: string
}

const ROLES = [
  { value: 'admin', label: '管理员' },
  { value: 'analyst', label: '分析员' },
  { value: 'uploader', label: '上传员' },
  { value: 'viewer', label: '只读' },
]

const ROLE_LABELS: Record<string, string> = {
  admin: '管理员', analyst: '分析员', uploader: '上传员', viewer: '只读',
}

function emptyForm(): UserForm {
  return { username: '', password: '', display_name: '', role: 'viewer', department: '', site: '' }
}

function authHeaders(json = false): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  const h: Record<string, string> = {}
  if (token) h['Authorization'] = `Bearer ${token}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [form, setForm] = useState<UserForm>(emptyForm())
  const [editId, setEditId] = useState<number | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [isCreate, setIsCreate] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => { loadUsers() }, [])

  async function loadUsers() {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/users`, { headers: authHeaders() })
      if (!res.ok) throw new Error(await res.text())
      setUsers(await res.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载用户失败')
    } finally {
      setLoading(false)
    }
  }

  function openCreate() {
    setForm(emptyForm())
    setEditId(null)
    setIsCreate(true)
    setModalOpen(true)
    setError('')
  }

  function openEdit(user: User) {
    setForm({ username: user.username, password: '', display_name: user.display_name, role: user.role, department: user.department, site: user.site })
    setEditId(user.id)
    setIsCreate(false)
    setModalOpen(true)
    setError('')
  }

  function closeModal() {
    setModalOpen(false)
    setError('')
  }

  async function handleSave() {
    setError('')
    try {
      if (isCreate) {
        if (!form.username.trim() || !form.password) { setError('用户名和密码不能为空'); return }
        const res = await fetch(`${API_BASE_URL}/users`, {
          method: 'POST', headers: authHeaders(true), body: JSON.stringify(form),
        })
        if (!res.ok) throw new Error((await res.json()).detail)
      } else {
        const body: Record<string, string | boolean> = {
          display_name: form.display_name, role: form.role,
          department: form.department, site: form.site,
        }
        if (form.password) body.password = form.password
        const res = await fetch(`${API_BASE_URL}/users/${editId}`, {
          method: 'PUT', headers: authHeaders(true), body: JSON.stringify(body),
        })
        if (!res.ok) throw new Error((await res.json()).detail)
      }
      setMessage(isCreate ? '用户已创建' : '已更新')
      setModalOpen(false)
      await loadUsers()
      setTimeout(() => setMessage(''), 3000)
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  async function handleDelete(id: number, name: string) {
    if (!confirm(`确认删除用户「${name}」？此操作不可撤销。`)) return
    try {
      const res = await fetch(`${API_BASE_URL}/users/${id}`, { method: 'DELETE', headers: authHeaders() })
      if (!res.ok) throw new Error((await res.json()).detail)
      await loadUsers()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    }
  }

  async function toggleActive(user: User) {
    try {
      const res = await fetch(`${API_BASE_URL}/users/${user.id}`, {
        method: 'PUT', headers: authHeaders(true),
        body: JSON.stringify({ is_active: !user.is_active }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      await loadUsers()
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败')
    }
  }

  return (
    <section className="portal-page">
      <div className="page-title-section">
        <p className="page-eyebrow">系统管理</p>
        <h1>用户管理</h1>
        <p className="page-desc">管理系统用户账号、角色与部门权限。</p>
      </div>

      <div className="page-action-bar">
        <button className="btn-primary" type="button" onClick={openCreate}>＋ 新建用户</button>
      </div>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-message">{message}</div>}

      <div className="data-card">
        {loading ? (
          <div className="empty-state">加载中...</div>
        ) : users.length === 0 ? (
          <div className="empty-state">暂无用户</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>显示名称</th>
                <th>角色</th>
                <th>部门</th>
                <th>园区/工厂</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id} className={user.is_active ? '' : 'row-disabled'}>
                  <td><strong>{user.username}</strong></td>
                  <td>{user.display_name}</td>
                  <td><span className="role-badge" data-role={user.role}>{ROLE_LABELS[user.role] ?? user.role}</span></td>
                  <td>{user.department || <span className="text-muted">—</span>}</td>
                  <td>{user.site || <span className="text-muted">—</span>}</td>
                  <td>
                    <span className={`status-dot ${user.is_active ? 'status-active' : 'status-inactive'}`}>
                      {user.is_active ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button type="button" className="btn-row" onClick={() => openEdit(user)}>编辑</button>
                      <button type="button" className="btn-row" onClick={() => toggleActive(user)}>
                        {user.is_active ? '禁用' : '启用'}
                      </button>
                      <button type="button" className="btn-row btn-danger" onClick={() => handleDelete(user.id, user.display_name)}>删除</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Modal ── */}
      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{isCreate ? '新建用户' : '编辑用户'}</h3>
              <button type="button" className="modal-close" onClick={closeModal}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-grid">
                <label className="field">
                  <span>用户名</span>
                  <input value={form.username} disabled={!isCreate}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
                </label>
                <label className="field">
                  <span>显示名称</span>
                  <input value={form.display_name}
                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} />
                </label>
                <label className="field">
                  <span>密码{!isCreate ? '（留空不修改）' : ''}</span>
                  <input type="password" value={form.password} autoComplete="new-password"
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
                </label>
                <label className="field">
                  <span>角色</span>
                  <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                    {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>部门</span>
                  <input value={form.department}
                    onChange={e => setForm(f => ({ ...f, department: e.target.value }))} />
                </label>
                <label className="field">
                  <span>园区/工厂</span>
                  <input value={form.site}
                    onChange={e => setForm(f => ({ ...f, site: e.target.value }))} />
                </label>
              </div>
              {error && <div className="form-error" style={{ marginTop: 8 }}>{error}</div>}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn-ghost" onClick={closeModal}>取消</button>
              <button type="button" className="btn-primary" onClick={handleSave}>
                {isCreate ? '创建' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default UsersPage
