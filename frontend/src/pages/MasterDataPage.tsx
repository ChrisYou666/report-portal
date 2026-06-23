import { useEffect, useState } from 'react'

const API = (import.meta.env.VITE_API_BASE_URL ?? '/api')

function authH(json = false) {
  const t = localStorage.getItem('auth_token')
  const h: Record<string, string> = {}
  if (t) h['Authorization'] = `Bearer ${t}`
  if (json) h['Content-Type'] = 'application/json'
  return h
}

async function api<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { headers: authH() })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText)
  return r.json()
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: 'POST', headers: authH(true), body: JSON.stringify(body) })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText)
  return r.json()
}

async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: 'PUT', headers: authH(true), body: JSON.stringify(body) })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText)
  return r.json()
}

async function apiDelete(path: string) {
  const r = await fetch(`${API}${path}`, { method: 'DELETE', headers: authH() })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText)
  return r.json()
}

// ─── Types ───────────────────────────────────────────────────────────────────

type Site = { id: number; code: string; name: string; name_id: string; region: string; country: string; is_active: boolean; source: string; external_id: string; remark: string }
type Division = { id: number; site_code: string; code: string; name: string; name_id: string; is_active: boolean; source: string; external_id: string; remark: string }
type DataSource = { id: number; name: string; description: string; source_type: string; host: string; port: number; database_name: string; username: string; api_url: string; api_method: string; api_response_path: string; sync_query: string; target_entity: string; field_mapping: string; is_active: boolean; last_sync_at: string | null; last_sync_count: number; last_sync_status: string; last_sync_message: string }

type Tab = 'sites' | 'divisions' | 'sources'

// ─── Main page ───────────────────────────────────────────────────────────────

export default function MasterDataPage() {
  const [tab, setTab] = useState<Tab>('sites')

  return (
    <section className="portal-page">
      <div className="page-title-section">
        <p className="page-eyebrow">主数据管理</p>
        <h1>主数据维护</h1>
        <p className="page-desc">管理园区、小区等维度数据，以及外部数据源连接配置和同步。</p>
      </div>

      <div className="entry-tabs">
        {([['sites', '园区管理'], ['divisions', '小区/Afdeling'], ['sources', '外部数据源']] as const).map(([k, l]) => (
          <button key={k} type="button" className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>

      {tab === 'sites' && <SiteTab />}
      {tab === 'divisions' && <DivisionTab />}
      {tab === 'sources' && <SourceTab />}
    </section>
  )
}

// ─── Site tab ────────────────────────────────────────────────────────────────

function emptySite(): Omit<Site, 'id' | 'source'> {
  return { code: '', name: '', name_id: '', region: '', country: 'Indonesia', is_active: true, external_id: '', remark: '' }
}

function SiteTab() {
  const [rows, setRows] = useState<Site[]>([])
  const [modal, setModal] = useState<null | { mode: 'create' | 'edit'; data: Omit<Site, 'id' | 'source'>; id?: number }>(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => { load() }, [])

  async function load() { setRows(await api('/master/sites')) }

  async function save() {
    setErr('')
    try {
      if (modal!.mode === 'create') await apiPost('/master/sites', modal!.data)
      else await apiPut(`/master/sites/${modal!.id}`, modal!.data)
      setMsg('已保存'); setModal(null); load()
      setTimeout(() => setMsg(''), 3000)
    } catch (e) { setErr(e instanceof Error ? e.message : '操作失败') }
  }

  async function del(id: number, name: string) {
    if (!confirm(`确认删除园区「${name}」？`)) return
    try { await apiDelete(`/master/sites/${id}`); load() } catch (e) { setErr(e instanceof Error ? e.message : '删除失败') }
  }

  return (
    <>
      <div className="page-action-bar">
        <button className="btn-primary" type="button" onClick={() => setModal({ mode: 'create', data: emptySite() })}>＋ 新建园区</button>
      </div>
      {err && <div className="form-error">{err}</div>}
      {msg && <div className="form-message">{msg}</div>}
      <div className="data-card">
        <table className="data-table">
          <thead><tr><th>代码</th><th>名称</th><th>印尼语名</th><th>地区</th><th>国家</th><th>来源</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={8}><div className="empty-state">暂无园区数据</div></td></tr>}
            {rows.map(r => (
              <tr key={r.id} className={r.is_active ? '' : 'row-disabled'}>
                <td><strong style={{ fontFamily: 'monospace' }}>{r.code}</strong></td>
                <td>{r.name}</td><td>{r.name_id || <Muted />}</td><td>{r.region || <Muted />}</td><td>{r.country}</td>
                <td><SourceBadge s={r.source} /></td>
                <td><span className={`status-dot ${r.is_active ? 'status-active' : 'status-inactive'}`}>{r.is_active ? '启用' : '禁用'}</span></td>
                <td><div className="row-actions">
                  <button className="btn-row" onClick={() => setModal({ mode: 'edit', id: r.id, data: { code: r.code, name: r.name, name_id: r.name_id, region: r.region, country: r.country, is_active: r.is_active, external_id: r.external_id, remark: r.remark } })}>编辑</button>
                  <button className="btn-row btn-danger" onClick={() => del(r.id, r.name)}>删除</button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <Modal title={modal.mode === 'create' ? '新建园区' : '编辑园区'} onClose={() => setModal(null)} onSave={save} err={err}>
          <div className="form-grid">
            <Field label="代码 *"><input value={modal.data.code} disabled={modal.mode === 'edit'} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, code: e.target.value } }))} /></Field>
            <Field label="中文名称 *"><input value={modal.data.name} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, name: e.target.value } }))} /></Field>
            <Field label="印尼语名称"><input value={modal.data.name_id} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, name_id: e.target.value } }))} /></Field>
            <Field label="地区/省份"><input value={modal.data.region} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, region: e.target.value } }))} /></Field>
            <Field label="国家"><input value={modal.data.country} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, country: e.target.value } }))} /></Field>
            <Field label="外部系统ID"><input value={modal.data.external_id} placeholder="SAP 等外部系统的对应 ID" onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, external_id: e.target.value } }))} /></Field>
            <Field label="备注" full><input value={modal.data.remark} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, remark: e.target.value } }))} /></Field>
            <Field label="状态"><label style={{ display: 'flex', alignItems: 'center', gap: 8 }}><input type="checkbox" checked={modal.data.is_active} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, is_active: e.target.checked } }))} /> 启用</label></Field>
          </div>
        </Modal>
      )}
    </>
  )
}

// ─── Division tab ─────────────────────────────────────────────────────────────

function emptyDiv(sites: Site[]): Omit<Division, 'id' | 'source'> {
  return { site_code: sites[0]?.code ?? '', code: '', name: '', name_id: '', is_active: true, external_id: '', remark: '' }
}

function DivisionTab() {
  const [sites, setSites] = useState<Site[]>([])
  const [rows, setRows] = useState<Division[]>([])
  const [modal, setModal] = useState<null | { mode: 'create' | 'edit'; data: Omit<Division, 'id' | 'source'>; id?: number }>(null)
  const [filterSite, setFilterSite] = useState('')
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => { api<Site[]>('/master/sites').then(s => { setSites(s); load() }) }, [])

  async function load(sc = filterSite) { setRows(await api(`/master/divisions${sc ? `?site_code=${sc}` : ''}`)) }

  async function save() {
    setErr('')
    try {
      if (modal!.mode === 'create') await apiPost('/master/divisions', modal!.data)
      else await apiPut(`/master/divisions/${modal!.id}`, modal!.data)
      setMsg('已保存'); setModal(null); load()
      setTimeout(() => setMsg(''), 3000)
    } catch (e) { setErr(e instanceof Error ? e.message : '操作失败') }
  }

  async function del(id: number, name: string) {
    if (!confirm(`确认删除小区「${name}」？`)) return
    try { await apiDelete(`/master/divisions/${id}`); load() } catch (e) { setErr(e instanceof Error ? e.message : '删除失败') }
  }

  return (
    <>
      <div className="page-action-bar">
        <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: '#64748b', whiteSpace: 'nowrap' }}>筛选园区</span>
          <select value={filterSite} style={{ height: 34, padding: '0 8px', border: '1px solid #e2e8f0', borderRadius: 6 }}
            onChange={e => { setFilterSite(e.target.value); load(e.target.value) }}>
            <option value="">全部</option>
            {sites.map(s => <option key={s.code} value={s.code}>{s.name}（{s.code}）</option>)}
          </select>
        </label>
        <button className="btn-primary" type="button" onClick={() => setModal({ mode: 'create', data: emptyDiv(sites) })}>＋ 新建小区</button>
      </div>
      {err && <div className="form-error">{err}</div>}
      {msg && <div className="form-message">{msg}</div>}
      <div className="data-card">
        <table className="data-table">
          <thead><tr><th>所属园区</th><th>小区代码</th><th>名称</th><th>印尼语名</th><th>来源</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7}><div className="empty-state">暂无小区数据</div></td></tr>}
            {rows.map(r => (
              <tr key={r.id} className={r.is_active ? '' : 'row-disabled'}>
                <td><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.site_code}</span></td>
                <td><strong style={{ fontFamily: 'monospace' }}>{r.code}</strong></td>
                <td>{r.name}</td><td>{r.name_id || <Muted />}</td>
                <td><SourceBadge s={r.source} /></td>
                <td><span className={`status-dot ${r.is_active ? 'status-active' : 'status-inactive'}`}>{r.is_active ? '启用' : '禁用'}</span></td>
                <td><div className="row-actions">
                  <button className="btn-row" onClick={() => setModal({ mode: 'edit', id: r.id, data: { site_code: r.site_code, code: r.code, name: r.name, name_id: r.name_id, is_active: r.is_active, external_id: r.external_id, remark: r.remark } })}>编辑</button>
                  <button className="btn-row btn-danger" onClick={() => del(r.id, r.name)}>删除</button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <Modal title={modal.mode === 'create' ? '新建小区' : '编辑小区'} onClose={() => setModal(null)} onSave={save} err={err}>
          <div className="form-grid">
            <Field label="所属园区 *">
              <select value={modal.data.site_code} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, site_code: e.target.value } }))}>
                {sites.map(s => <option key={s.code} value={s.code}>{s.name}（{s.code}）</option>)}
              </select>
            </Field>
            <Field label="小区代码 *"><input value={modal.data.code} disabled={modal.mode === 'edit'} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, code: e.target.value } }))} /></Field>
            <Field label="中文名称 *"><input value={modal.data.name} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, name: e.target.value } }))} /></Field>
            <Field label="印尼语名称"><input value={modal.data.name_id} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, name_id: e.target.value } }))} /></Field>
            <Field label="外部系统ID"><input value={modal.data.external_id} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, external_id: e.target.value } }))} /></Field>
            <Field label="备注" full><input value={modal.data.remark} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, remark: e.target.value } }))} /></Field>
            <Field label="状态"><label style={{ display: 'flex', alignItems: 'center', gap: 8 }}><input type="checkbox" checked={modal.data.is_active} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, is_active: e.target.checked } }))} /> 启用</label></Field>
          </div>
        </Modal>
      )}
    </>
  )
}

// ─── Data source tab ──────────────────────────────────────────────────────────

const SOURCE_TYPES = [
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'sqlserver', label: 'SQL Server' },
  { value: 'rest_api', label: 'REST API' },
]

const TARGET_ENTITIES = [
  { value: 'dim_site', label: '园区（dim_site）' },
  { value: 'dim_division', label: '小区（dim_division）' },
]

const MAPPING_EXAMPLES: Record<string, string> = {
  dim_site: JSON.stringify({ estate_code: 'code', estate_name: 'name', region: 'region' }, null, 2),
  dim_division: JSON.stringify({ div_code: 'code', div_name: 'name', estate_code: 'site_code' }, null, 2),
}

const QUERY_EXAMPLES: Record<string, string> = {
  postgresql: 'SELECT estate_code, estate_name, region\nFROM estates\nWHERE is_active = true\nORDER BY estate_code',
  sqlserver: 'SELECT WERKS AS estate_code, NAME1 AS estate_name\nFROM MARA\nWHERE MANDT = \'100\'',
  rest_api: '',
}

function emptySource(): Omit<DataSource, 'id' | 'last_sync_at' | 'last_sync_count' | 'last_sync_status' | 'last_sync_message'> & { password: string; api_headers: string } {
  return { name: '', description: '', source_type: 'postgresql', host: '', port: 5432, database_name: '', username: '', password: '', api_url: '', api_method: 'GET', api_response_path: '', api_headers: '{}', sync_query: '', target_entity: 'dim_site', field_mapping: MAPPING_EXAMPLES.dim_site, is_active: true }
}

function SourceTab() {
  const [rows, setRows] = useState<DataSource[]>([])
  const [modal, setModal] = useState<null | { mode: 'create' | 'edit'; data: ReturnType<typeof emptySource>; id?: number }>(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const [working, setWorking] = useState<Record<number, string>>({})

  useEffect(() => { load() }, [])

  async function load() { setRows(await api('/master/data-sources')) }

  async function save() {
    setErr('')
    try {
      if (modal!.mode === 'create') await apiPost('/master/data-sources', modal!.data)
      else await apiPut(`/master/data-sources/${modal!.id}`, modal!.data)
      setMsg('已保存'); setModal(null); load()
      setTimeout(() => setMsg(''), 3000)
    } catch (e) { setErr(e instanceof Error ? e.message : '操作失败') }
  }

  async function doTest(id: number) {
    setWorking(w => ({ ...w, [id]: 'testing' }))
    try {
      const r = await apiPost<{ success: boolean; message: string }>(`/master/data-sources/${id}/test`, {})
      setMsg(r.success ? `✓ ${r.message}` : `✗ ${r.message}`)
      setTimeout(() => setMsg(''), 5000)
    } catch (e) { setMsg(e instanceof Error ? e.message : '测试失败') }
    finally { setWorking(w => ({ ...w, [id]: '' })) }
  }

  async function doSync(id: number) {
    setWorking(w => ({ ...w, [id]: 'syncing' }))
    try {
      const r = await apiPost<{ success: boolean; count: number; message: string }>(`/master/data-sources/${id}/sync`, {})
      setMsg(r.success ? `✓ ${r.message}` : `✗ ${r.message}`)
      load()
      setTimeout(() => setMsg(''), 5000)
    } catch (e) { setMsg(e instanceof Error ? e.message : '同步失败') }
    finally { setWorking(w => ({ ...w, [id]: '' })) }
  }

  async function del(id: number, name: string) {
    if (!confirm(`确认删除数据源「${name}」？`)) return
    try { await apiDelete(`/master/data-sources/${id}`); load() } catch (e) { setErr(e instanceof Error ? e.message : '删除失败') }
  }

  const d = modal?.data

  return (
    <>
      <div className="page-action-bar">
        <button className="btn-primary" type="button" onClick={() => { setErr(''); setModal({ mode: 'create', data: emptySource() }) }}>＋ 新建数据源</button>
      </div>
      {err && <div className="form-error">{err}</div>}
      {msg && <div className={`${msg.startsWith('✓') ? 'form-message' : 'form-error'}`}>{msg}</div>}
      <div className="data-card">
        <table className="data-table">
          <thead><tr><th>名称</th><th>类型</th><th>目标实体</th><th>状态</th><th>上次同步</th><th>同步结果</th><th>操作</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7}><div className="empty-state">暂无数据源配置</div></td></tr>}
            {rows.map(r => (
              <tr key={r.id}>
                <td><strong>{r.name}</strong>{r.description && <small style={{ display: 'block', color: '#94a3b8' }}>{r.description}</small>}</td>
                <td><span className="role-badge" data-role="analyst">{SOURCE_TYPES.find(t => t.value === r.source_type)?.label ?? r.source_type}</span></td>
                <td><code style={{ fontSize: 11 }}>{r.target_entity}</code></td>
                <td><span className={`status-dot ${r.is_active ? 'status-active' : 'status-inactive'}`}>{r.is_active ? '启用' : '禁用'}</span></td>
                <td style={{ fontSize: 12, color: '#64748b' }}>{r.last_sync_at ? new Date(r.last_sync_at).toLocaleString('zh-CN') : '—'}</td>
                <td>
                  {r.last_sync_status === 'ok' && <span style={{ color: '#16a34a', fontSize: 12 }}>✓ {r.last_sync_count} 条</span>}
                  {r.last_sync_status === 'error' && <span style={{ color: '#dc2626', fontSize: 12 }} title={r.last_sync_message}>✗ 失败</span>}
                </td>
                <td><div className="row-actions" style={{ flexWrap: 'wrap' }}>
                  <button className="btn-row" onClick={() => { setErr(''); setModal({ mode: 'edit', id: r.id, data: { name: r.name, description: r.description, source_type: r.source_type, host: r.host, port: r.port, database_name: r.database_name, username: r.username, password: '', api_url: r.api_url, api_method: r.api_method, api_response_path: r.api_response_path, api_headers: '{}', sync_query: r.sync_query, target_entity: r.target_entity, field_mapping: r.field_mapping, is_active: r.is_active } }) }}>编辑</button>
                  <button className="btn-row" disabled={!!working[r.id]} onClick={() => doTest(r.id)}>{working[r.id] === 'testing' ? '测试中...' : '测试'}</button>
                  <button className="btn-row" disabled={!!working[r.id] || !r.is_active} onClick={() => doSync(r.id)}>{working[r.id] === 'syncing' ? '同步中...' : '立即同步'}</button>
                  <button className="btn-row btn-danger" onClick={() => del(r.id, r.name)}>删除</button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && d && (
        <Modal title={modal.mode === 'create' ? '新建数据源' : '编辑数据源'} onClose={() => setModal(null)} onSave={save} err={err} wide>
          <div className="form-grid">
            <Field label="名称 *" full><input value={d.name} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, name: e.target.value } }))} /></Field>
            <Field label="说明"><input value={d.description} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, description: e.target.value } }))} /></Field>
            <Field label="类型 *">
              <select value={d.source_type} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, source_type: e.target.value, sync_query: QUERY_EXAMPLES[e.target.value] ?? '' } }))}>
                {SOURCE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </Field>
            <Field label="目标实体 *">
              <select value={d.target_entity} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, target_entity: e.target.value, field_mapping: MAPPING_EXAMPLES[e.target.value] ?? '{}' } }))}>
                {TARGET_ENTITIES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </Field>

            {/* DB fields */}
            {(d.source_type === 'postgresql' || d.source_type === 'sqlserver') && (<>
              <Field label="主机/IP"><input value={d.host} placeholder="192.168.1.100" onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, host: e.target.value } }))} /></Field>
              <Field label="端口"><input type="number" value={d.port} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, port: +e.target.value } }))} /></Field>
              <Field label="数据库名"><input value={d.database_name} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, database_name: e.target.value } }))} /></Field>
              <Field label="用户名"><input value={d.username} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, username: e.target.value } }))} /></Field>
              <Field label={`密码${modal.mode === 'edit' ? '（留空不修改）' : ''}`}>
                <input type="password" value={d.password} autoComplete="new-password" onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, password: e.target.value } }))} />
              </Field>
              <Field label="同步查询 SQL" full>
                <textarea rows={4} value={d.sync_query} style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, padding: 8, border: '1px solid #e2e8f0', borderRadius: 6 }}
                  onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, sync_query: e.target.value } }))} />
              </Field>
            </>)}

            {/* REST API fields */}
            {d.source_type === 'rest_api' && (<>
              <Field label="URL *" full><input value={d.api_url} placeholder="https://api.example.com/estates" onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, api_url: e.target.value } }))} /></Field>
              <Field label="方法">
                <select value={d.api_method} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, api_method: e.target.value } }))}>
                  <option>GET</option><option>POST</option>
                </select>
              </Field>
              <Field label="响应数据路径" >
                <input value={d.api_response_path} placeholder="如: data.items（可留空）" onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, api_response_path: e.target.value } }))} />
              </Field>
              <Field label="请求头 JSON" full>
                <textarea rows={3} value={d.api_headers} placeholder={'{\n  "Authorization": "Bearer ...",\n  "X-Api-Key": "..."\n}'} style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, padding: 8, border: '1px solid #e2e8f0', borderRadius: 6 }}
                  onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, api_headers: e.target.value } }))} />
              </Field>
            </>)}

            {/* Field mapping */}
            <Field label="字段映射 JSON" full>
              <textarea rows={5} value={d.field_mapping} style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, padding: 8, border: '1px solid #e2e8f0', borderRadius: 6 }}
                onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, field_mapping: e.target.value } }))} />
              <small style={{ color: '#94a3b8', fontSize: 11 }}>格式：{"{"}"源字段名": "目标字段名"{"}"}</small>
            </Field>

            <Field label="状态"><label style={{ display: 'flex', alignItems: 'center', gap: 8 }}><input type="checkbox" checked={d.is_active} onChange={e => setModal(m => m && ({ ...m, data: { ...m.data, is_active: e.target.checked } }))} /> 启用</label></Field>
          </div>
        </Modal>
      )}
    </>
  )
}

// ─── Shared components ────────────────────────────────────────────────────────

function Modal({ title, onClose, onSave, err, children, wide }: { title: string; onClose: () => void; onSave: () => void; err?: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" style={wide ? { maxWidth: 680 } : {}} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {children}
          {err && <div className="form-error" style={{ marginTop: 8 }}>{err}</div>}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn-primary" onClick={onSave}>保存</button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <label className="field" style={full ? { gridColumn: '1 / -1' } : {}}>
      <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>{label}</span>
      {children}
    </label>
  )
}

function Muted() { return <span className="text-muted">—</span> }

function SourceBadge({ s }: { s: string }) {
  return <span className="role-badge" data-role={s === 'manual' ? 'viewer' : 'uploader'}>{s === 'manual' ? '手动' : '同步'}</span>
}
