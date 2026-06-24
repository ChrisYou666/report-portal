import { createContext, useContext, useEffect, useRef, useState } from 'react'
import {
  getIndices, createIndex, updateIndex, deleteIndex,
  addSubMetric, updateSubMetric, deleteSubMetric,
  getCompositeFormula, updateCompositeFormula,
  getCurrentSapHarvestPipeline, getSapHarvestDailyPreview, getSapHarvestMonitor, getSapHarvestPipelineStatus, syncSapHarvestPipeline,
  previewSubMetricSync, syncSubMetric,
  getDbTables, getDbColumns,
  getScheduledSyncs, createScheduledSync, updateScheduledSync, deleteScheduledSync, triggerScheduledSync,
  getTeamsConfig, updateTeamsConfig, testTeamsWebhook,
  getTeamsBotConversations, getTeamsBotStatus, getIndexNotifications, updateIndexNotification, testIndexNotification,
  previewInitDb, runInitDb,
} from '../services/api'
import type { HarvestDailyPreviewItem, HarvestMonitorResult, HarvestPipelineSyncResult, IndexDef, IndexDefIn, SubMetricIn, CompositeFormula, SmSyncItem, ScheduledSyncIn, ScheduledSyncOut, TeamsConfig, TeamsBotConversation, TeamsBotStatus, IndexNotificationConfig, IndexNotificationInput, InitDbPreview, InitDbResult } from '../services/api'
import type { AuthUser } from '../services/auth'

type Tab = 'definitions' | 'index_calc' | 'composite' | 'data_sync' | 'scheduled' | 'notify' | 'system'

// ── Theme context ─────────────────────────────────────────────
const DarkCtx    = createContext(false)
const useDark    = () => useContext(DarkCtx)
const CanEditCtx = createContext(false)
const useCanEdit = () => useContext(CanEditCtx)

// Theme helpers
function c(d: boolean, dark: string, light: string) { return d ? dark : light }

const T = {
  textPrimary:   (d: boolean) => c(d, '#e2e8f0', '#0f172a'),
  textSecondary: (d: boolean) => c(d, '#8892a4', '#64748b'),
  textMuted:     (d: boolean) => c(d, '#6b7280', '#94a3b8'),
  cardBg:        (d: boolean) => c(d, '#1a1d2a', '#fff'),
  tabBg:         (d: boolean) => c(d, '#0f1117', '#fff'),
  tabBorder:     (d: boolean) => c(d, 'rgba(255,255,255,0.08)', '#e2e8f0'),
  tabActiveBg:   (d: boolean) => c(d, '#1d4ed8', '#0f766e'),
  rowBorder:     (d: boolean) => c(d, 'rgba(255,255,255,0.06)', '#f1f5f9'),
  sectionBorder: (d: boolean) => c(d, 'rgba(255,255,255,0.08)', '#e2e8f0'),
  codeBg:        (d: boolean) => c(d, 'rgba(125,211,252,0.1)', '#f0fdf4'),
  codeColor:     (d: boolean) => c(d, '#7dd3fc', '#0f766e'),
  inputBg:       (d: boolean) => c(d, '#0f1117', '#fff'),
  inputBorder:   (d: boolean) => c(d, 'rgba(255,255,255,0.12)', '#cbd5e1'),
  inputColor:    (d: boolean) => c(d, '#e2e8f0', '#0f172a'),
  infoBg:        (d: boolean) => c(d, 'rgba(59,130,246,0.08)', 'transparent'),
  infoColor:     (d: boolean) => c(d, '#93c5fd', '#475569'),
  successBg:     (d: boolean) => c(d, 'rgba(34,197,94,0.1)', '#f0fdf4'),
  successBorder: (d: boolean) => c(d, 'rgba(34,197,94,0.2)', '#bbf7d0'),
  successTitle:  (d: boolean) => c(d, '#4ade80', '#166534'),
  successText:   (d: boolean) => c(d, '#86efac', '#15803d'),
}

// ── Shared helpers ────────────────────────────────────────────
const EMPTY_DEF: IndexDefIn = { code: '', name: '', formula: '', description: '', sort_order: 0, is_active: true, granularity: 'monthly' }

function field(label: string, input: React.ReactNode, dark: boolean) {
  return (
    <div className="field">
      <span style={{ color: T.textSecondary(dark) }}>{label}</span>
      {input}
    </div>
  )
}

function inputStyle(dark: boolean, extra?: React.CSSProperties): React.CSSProperties {
  return {
    height: 36,
    background: T.inputBg(dark),
    border: `1px solid ${T.inputBorder(dark)}`,
    borderRadius: 6,
    color: T.inputColor(dark),
    ...extra,
  }
}

function selectStyle(dark: boolean): React.CSSProperties {
  return {
    height: 36,
    background: T.inputBg(dark),
    border: `1px solid ${T.inputBorder(dark)}`,
    borderRadius: 6,
    padding: '0 8px',
    fontSize: 14,
    color: T.inputColor(dark),
  }
}

// ── Sub-metric inline row ─────────────────────────────────────
const SOURCE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  manual:  { label: '手动录入',   color: '#94a3b8', bg: 'rgba(148,163,184,0.1)' },
  db_sync: { label: '从数据库提取', color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
  fixed:   { label: '固定值',     color: '#22c55e', bg: 'rgba(34,197,94,0.1)'   },
}

function SubMetricRow({
  sm, onSave, onDelete,
}: {
  sm: {
    id?: number; code: string; name: string; unit: string
    source_type: 'manual' | 'db_sync' | 'fixed'; fixed_value: number | null
    db_table: string | null; db_field: string | null
    db_aggregation: string; db_date_col: string; db_extra_where: string | null
    fiscal_start_month: number | null
    sort_order: number
  }
  onSave: (v: SubMetricIn) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const dark    = useDark()
  const canEdit = useCanEdit()
  const [editing, setEditing] = useState(!sm.id)
  const [form, setForm] = useState<SubMetricIn>({
    code: sm.code, name: sm.name, unit: sm.unit,
    source_type: sm.source_type ?? 'manual',
    fixed_value: sm.fixed_value,
    db_table: sm.db_table, db_field: sm.db_field,
    db_aggregation: sm.db_aggregation || 'SUM',
    db_date_col: sm.db_date_col || 'report_date',
    db_extra_where: sm.db_extra_where,
    fiscal_start_month: sm.fiscal_start_month,
    sort_order: sm.sort_order,
  })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [tables, setTables] = useState<string[]>([])
  const [columns, setColumns] = useState<{ name: string; type: string }[]>([])
  const smRef = useRef(sm)
  smRef.current = sm
  const formRef = useRef(form)
  formRef.current = form   // 始终指向最新 form，避免闭包捕获旧值

  // 进入编辑且是 db_sync 时，懒加载表列表
  useEffect(() => {
    if (editing && form.source_type === 'db_sync' && tables.length === 0) {
      getDbTables().then(setTables).catch(() => {})
    }
  }, [editing, form.source_type])  // eslint-disable-line react-hooks/exhaustive-deps

  // 表名变化时加载字段列表
  useEffect(() => {
    if (!form.db_table) { setColumns([]); return }
    getDbColumns(form.db_table).then(setColumns).catch(() => setColumns([]))
  }, [form.db_table])

  // 每次进入编辑状态时从最新的 sm prop 重新初始化 form
  useEffect(() => {
    if (editing) {
      const s = smRef.current
      setForm({
        code: s.code, name: s.name, unit: s.unit,
        source_type: s.source_type ?? 'manual',
        fixed_value: s.fixed_value,
        db_table: s.db_table, db_field: s.db_field,
        db_aggregation: s.db_aggregation || 'SUM',
        db_date_col: s.db_date_col || 'report_date',
        db_extra_where: s.db_extra_where,
        fiscal_start_month: s.fiscal_start_month,
        sort_order: s.sort_order,
      })
      setSaveError('')
    }
  }, [editing])

  async function save() {
    const f = formRef.current
    if (!f.code) return
    setSaving(true); setSaveError('')
    try { await onSave(f); setEditing(false) }
    catch (e: any) { setSaveError(e.message ?? '保存失败') }
    finally { setSaving(false) }
  }

  const srcInfo = SOURCE_LABELS[sm.source_type ?? 'manual'] ?? SOURCE_LABELS.manual

  if (!editing) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 60px 130px 52px 52px', gap: 10, alignItems: 'center', padding: '7px 0', borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
        <code style={{ fontWeight: 700, color: T.codeColor(dark), background: T.codeBg(dark), borderRadius: 4, padding: '1px 6px', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sm.code}</code>
        <span style={{ color: T.textPrimary(dark), fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sm.name || '—'}</span>
        <span style={{ color: T.textMuted(dark), fontSize: 12 }}>{sm.unit || '—'}</span>
        <span style={{ fontSize: 12, color: srcInfo.color, background: srcInfo.bg, borderRadius: 4, padding: '2px 8px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {srcInfo.label}{sm.source_type === 'fixed' && sm.fixed_value != null && `：${sm.fixed_value.toLocaleString('zh-CN')}`}
        </span>
        {canEdit && <button type="button" className="btn-row" onClick={() => setEditing(true)}>编辑</button>}
        {canEdit && <button type="button" className="btn-row btn-danger" onClick={onDelete}>删除</button>}
      </div>
    )
  }

  const formSrcInfo = SOURCE_LABELS[form.source_type] ?? SOURCE_LABELS.manual

  return (
    <div style={{ display: 'grid', gap: 8, padding: '10px 0', borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
      {/* Row 1: 变量名 / 显示名 / 单位 */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input className="entry-cell-input" style={inputStyle(dark, { width: 100, flexShrink: 0, fontFamily: 'monospace' })} placeholder="变量名*" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} />
        <input className="entry-cell-input" style={inputStyle(dark, { flex: 1, minWidth: 0, maxWidth: 380 })} placeholder="显示名" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
        <input className="entry-cell-input" style={inputStyle(dark, { width: 70, flexShrink: 0 })} placeholder="单位" value={form.unit} onChange={e => setForm(f => ({ ...f, unit: e.target.value }))} />
      </div>
      {/* Row 2: 数据来源 / 固定值（条件显示） / 排序 / 操作 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>数据来源</span>
        <select
          style={{ ...selectStyle(dark), minWidth: 130, borderColor: formSrcInfo.color + '60' }}
          value={form.source_type}
          onChange={e => setForm(f => ({
            ...f,
            source_type: e.target.value as SubMetricIn['source_type'],
            fixed_value: e.target.value !== 'fixed' ? null : f.fixed_value,
          }))}
        >
          <option value="manual">手动录入</option>
          <option value="db_sync">从数据库提取</option>
          <option value="fixed">固定值</option>
        </select>

        {form.source_type === 'fixed' && (
          <>
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>固定值</span>
            <input className="entry-cell-input" type="number" style={inputStyle(dark, { width: 150 })}
              placeholder="如 1122005" value={form.fixed_value ?? ''}
              onChange={e => setForm(f => ({ ...f, fixed_value: e.target.value === '' ? null : +e.target.value }))} />
          </>
        )}

        <span style={{ fontSize: 12, color: T.textMuted(dark), whiteSpace: 'nowrap', marginLeft: 4 }}>排序</span>
        <input className="entry-cell-input" type="number" style={inputStyle(dark, { width: 60 })} value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: +e.target.value }))} />
        <button type="button" className="btn-primary" style={{ padding: '4px 12px', height: 30, fontSize: 12 }} onClick={save} disabled={saving || !form.code}>
          {saving ? '保存中…' : '保存'}
        </button>
        {sm.id && <button type="button" className="btn-ghost" style={{ padding: '4px 10px', height: 30, fontSize: 12 }} onClick={() => setEditing(false)}>取消</button>}
      </div>
      {/* Row 3: DB config (when db_sync) */}
      {form.source_type === 'db_sync' && (
        <div style={{ display: 'grid', gap: 8, padding: '8px 12px', background: dark ? 'rgba(96,165,250,0.06)' : '#f0f9ff', borderRadius: 6, border: `1px solid ${dark ? 'rgba(96,165,250,0.2)' : '#bae6fd'}` }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: dark ? '#60a5fa' : '#0369a1', textTransform: 'uppercase', letterSpacing: '0.05em' }}>数据库配置</div>
          {/* datalist IDs per row to avoid conflicts */}
          <datalist id={`tables-${sm.id ?? 'new'}`}>
            {tables.map(t => <option key={t} value={t} />)}
          </datalist>
          <datalist id={`cols-${sm.id ?? 'new'}`}>
            {columns.map(c => <option key={c.name} value={c.name} label={c.type} />)}
          </datalist>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>表名</span>
            <input
              className="entry-cell-input"
              list={`tables-${sm.id ?? 'new'}`}
              style={inputStyle(dark, { width: 260, fontFamily: 'monospace' })}
              placeholder="输入或选择 schema.table"
              value={form.db_table ?? ''}
              onFocus={() => { if (tables.length === 0) getDbTables().then(setTables).catch(() => {}) }}
              onChange={e => setForm(f => ({ ...f, db_table: e.target.value || null, db_field: null }))}
            />
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>字段</span>
            <input
              className="entry-cell-input"
              list={`cols-${sm.id ?? 'new'}`}
              style={inputStyle(dark, { width: 160, fontFamily: 'monospace' })}
              placeholder={columns.length ? `${columns.length} 个字段可选` : '如 production_ag'}
              value={form.db_field ?? ''}
              onChange={e => setForm(f => ({ ...f, db_field: e.target.value || null }))}
            />
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>聚合</span>
            <select style={{ ...selectStyle(dark), width: 90 }} value={form.db_aggregation}
              onChange={e => setForm(f => ({ ...f, db_aggregation: e.target.value }))}>
              {['SUM', 'AVG', 'MAX', 'MIN', 'COUNT'].map(a => <option key={a}>{a}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>日期列</span>
            <input className="entry-cell-input" style={inputStyle(dark, { width: 150, fontFamily: 'monospace' })}
              placeholder="report_date" value={form.db_date_col || ''}
              onChange={e => setForm(f => ({ ...f, db_date_col: e.target.value || 'report_date' }))} />
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>附加条件（可选）</span>
            <input className="entry-cell-input" style={inputStyle(dark, { flex: 1, minWidth: 180, fontFamily: 'monospace' })}
              placeholder="如 site = 'WPP'" value={form.db_extra_where ?? ''}
              onChange={e => setForm(f => ({ ...f, db_extra_where: e.target.value || null }))} />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>聚合模式</span>
            <select
              style={{ ...selectStyle(dark), minWidth: 140 }}
              value={form.fiscal_start_month != null ? 'fiscal_year' : 'monthly'}
              onChange={e => setForm(f => ({
                ...f,
                fiscal_start_month: e.target.value === 'fiscal_year' ? 9 : null,
              }))}
            >
              <option value="monthly">月度聚合（当月）</option>
              <option value="fiscal_year">财年累计（从财年起始月）</option>
            </select>
            {form.fiscal_start_month != null && (
              <>
                <span style={{ fontSize: 12, color: T.textSecondary(dark), whiteSpace: 'nowrap' }}>财年起始月</span>
                <input
                  className="entry-cell-input"
                  type="number"
                  min={1} max={12}
                  style={inputStyle(dark, { width: 60 })}
                  value={form.fiscal_start_month}
                  onChange={e => setForm(f => ({ ...f, fiscal_start_month: Math.min(12, Math.max(1, +e.target.value)) }))}
                />
                <span style={{ fontSize: 11, color: T.textMuted(dark) }}>
                  （当月在该月之前则从上一年开始）
                </span>
              </>
            )}
          </div>
        </div>
      )}

      {saveError && (
        <div style={{ fontSize: 12, color: '#f87171', marginTop: 4 }}>{saveError}</div>
      )}
    </div>
  )
}

// ── Index definition card ─────────────────────────────────────
function IndexDefCard({ idx, onUpdated, onDeleted }: {
  idx: IndexDef; onUpdated: (u: IndexDef) => void; onDeleted: (id: number) => void
}) {
  const dark    = useDark()
  const canEdit = useCanEdit()
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState<IndexDefIn>({ code: idx.code, name: idx.name, formula: idx.formula, description: idx.description, sort_order: idx.sort_order, is_active: idx.is_active, granularity: idx.granularity ?? 'monthly' })
  const [saving, setSaving] = useState(false)
  const [addingSm, setAddingSm] = useState(false)
  const [subs, setSubs] = useState(idx.sub_metrics)
  const [error, setError] = useState('')

  async function saveIdx() {
    setSaving(true); setError('')
    try { const u = await updateIndex(idx.id, form); onUpdated(u); setEditing(false) }
    catch (e: any) { setError(e.message) } finally { setSaving(false) }
  }

  async function handleDelete() {
    if (!confirm(`确认删除指标「${idx.name}」及其所有分项？`)) return
    try { await deleteIndex(idx.id); onDeleted(idx.id) }
    catch (e: any) { setError(e.message) }
  }

  async function saveSm(smId: number | undefined, data: SubMetricIn) {
    if (smId) {
      const u = await updateSubMetric(smId, data)
      setSubs(s => {
        const next = s.map(x => x.id === smId ? { ...x, ...u } : x)
        onUpdated({ ...idx, sub_metrics: next })
        return next
      })
    } else {
      const c = await addSubMetric(idx.id, data)
      setSubs(s => {
        const next = [...s, c]
        onUpdated({ ...idx, sub_metrics: next })
        return next
      }); setAddingSm(false)
    }
  }

  async function deleteSm(smId: number) {
    if (!confirm('确认删除该分项？')) return
    await deleteSubMetric(smId)
    setSubs(s => {
      const next = s.filter(x => x.id !== smId)
      onUpdated({ ...idx, sub_metrics: next })
      return next
    })
  }

  return (
    <div className="data-card" style={{ padding: '13px 18px', marginBottom: 10, background: T.cardBg(dark) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button type="button" style={{ background: 'none', border: 'none', cursor: 'pointer', color: T.textMuted(dark), fontSize: 12 }} onClick={() => setExpanded(e => !e)}>
          {expanded ? '▼' : '▶'}
        </button>
        <span style={{ fontWeight: 700, color: T.textPrimary(dark), flex: 1 }}>{idx.name}</span>
        <code style={{ color: T.codeColor(dark), fontSize: 12, background: T.codeBg(dark), borderRadius: 4, padding: '2px 7px' }}>{idx.code}</code>
        <span style={{ color: T.textMuted(dark), fontSize: 12 }}>{subs.length} 个分项</span>
        {!idx.is_active && <span className="status-badge">停用</span>}
        {canEdit && <button type="button" className="btn-row" onClick={() => { setEditing(e => !e); setExpanded(true) }}>编辑</button>}
        {canEdit && <button type="button" className="btn-row btn-danger" onClick={handleDelete}>删除</button>}
      </div>

      {error && <div className="form-error" style={{ marginTop: 8 }}>{error}</div>}

      {editing && (
        <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
          <div className="form-grid">
            {field('指标代码', <input className="entry-cell-input" style={inputStyle(dark, { fontFamily: 'monospace' })} value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} />, dark)}
            {field('指标名称', <input className="entry-cell-input" style={inputStyle(dark)} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />, dark)}
            {field('排序', <input type="number" className="entry-cell-input" style={inputStyle(dark)} value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: +e.target.value }))} />, dark)}
            {field('状态', (
              <select style={selectStyle(dark)} value={form.is_active ? 'active' : 'inactive'} onChange={e => setForm(f => ({ ...f, is_active: e.target.value === 'active' }))}>
                <option value="active">启用</option>
                <option value="inactive">停用</option>
              </select>
            ), dark)}
            {field('计算粒度', (
              <select style={selectStyle(dark)} value={form.granularity} onChange={e => setForm(f => ({ ...f, granularity: e.target.value as 'monthly' | 'daily' }))}>
                <option value="monthly">按月（月度汇总）</option>
                <option value="daily">按日（每日更新）</option>
              </select>
            ), dark)}
          </div>
          {field('说明', <input className="entry-cell-input" style={inputStyle(dark)} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />, dark)}
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="btn-primary" onClick={saveIdx} disabled={saving || !form.code || !form.name}>保存</button>
            <button type="button" className="btn-ghost" onClick={() => setEditing(false)}>取消</button>
          </div>
        </div>
      )}

      {expanded && !editing && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr 60px 130px 52px 52px', gap: 10, padding: '0 0 6px', borderBottom: `1px solid ${T.sectionBorder(dark)}` }}>
            {['变量名', '显示名', '单位', '数据来源', '', ''].map((h, i) => (
              <span key={i} style={{ fontSize: 11, fontWeight: 700, color: T.textMuted(dark), textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</span>
            ))}
          </div>
          {subs.map(sm => (
            <SubMetricRow key={sm.id} sm={sm} onSave={d => saveSm(sm.id, d)} onDelete={() => deleteSm(sm.id)} />
          ))}
          {addingSm && (
            <SubMetricRow sm={{ code: '', name: '', unit: '', source_type: 'manual', fixed_value: null, db_table: null, db_field: null, db_aggregation: 'SUM', db_date_col: 'report_date', db_extra_where: null, fiscal_start_month: null, sort_order: subs.length }} onSave={d => saveSm(undefined, d)} onDelete={async () => setAddingSm(false)} />
          )}
          {canEdit && (
            <button type="button" className="btn-ghost" style={{ marginTop: 8, height: 30, fontSize: 12, padding: '0 12px' }} onClick={() => setAddingSm(true)}>
              + 添加分项
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tab 1: 指标定义 ───────────────────────────────────────────
function DefinitionsTab({ indices, setIndices }: { indices: IndexDef[]; setIndices: React.Dispatch<React.SetStateAction<IndexDef[]>> }) {
  const dark    = useDark()
  const canEdit = useCanEdit()
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<IndexDefIn>(EMPTY_DEF)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleCreate() {
    setSaving(true); setError('')
    try {
      const created = await createIndex(form)
      setIndices(l => [...l, { ...created, sub_metrics: [] }])
      setForm(EMPTY_DEF); setAdding(false)
    } catch (e: any) { setError(e.message) } finally { setSaving(false) }
  }

  return (
    <div>
      {canEdit && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <button type="button" className="btn-primary" onClick={() => setAdding(a => !a)}>+ 新增指标</button>
        </div>
      )}
      {canEdit && adding && (
        <div className="data-card" style={{ padding: '16px 18px', marginBottom: 12, background: T.cardBg(dark) }}>
          <div style={{ fontWeight: 700, marginBottom: 10, color: T.textPrimary(dark) }}>新增指标</div>
          {error && <div className="form-error" style={{ marginBottom: 8 }}>{error}</div>}
          <div className="form-grid" style={{ marginBottom: 10 }}>
            {field('指标代码（公式中使用）', <input className="entry-cell-input" style={inputStyle(dark, { fontFamily: 'monospace' })} placeholder="如 agri, futures" value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))} />, dark)}
            {field('指标名称', <input className="entry-cell-input" style={inputStyle(dark)} placeholder="如 农业、期货" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />, dark)}
            {field('排序', <input type="number" className="entry-cell-input" style={inputStyle(dark)} value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: +e.target.value }))} />, dark)}
            {field('计算粒度', (
              <select style={selectStyle(dark)} value={form.granularity} onChange={e => setForm(f => ({ ...f, granularity: e.target.value as 'monthly' | 'daily' }))}>
                <option value="monthly">按月</option>
                <option value="daily">按日</option>
              </select>
            ), dark)}
          </div>
          {field('说明（可选）', <input className="entry-cell-input" style={inputStyle(dark)} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />, dark)}
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button type="button" className="btn-primary" onClick={handleCreate} disabled={saving || !form.code || !form.name}>创建</button>
            <button type="button" className="btn-ghost" onClick={() => { setAdding(false); setForm(EMPTY_DEF); setError('') }}>取消</button>
          </div>
        </div>
      )}
      {indices.length === 0 && !adding && <div className="empty-state">暂无指标，点击「新增指标」开始配置</div>}
      {indices.map(idx => (
        <IndexDefCard key={idx.id} idx={idx}
          onUpdated={u => setIndices(l => l.map(i => i.id === u.id ? { ...u, sub_metrics: i.sub_metrics } : i))}
          onDeleted={id => setIndices(l => l.filter(i => i.id !== id))}
        />
      ))}
    </div>
  )
}

// ── Tab 2: 指数计算 ───────────────────────────────────────────
function IndexCalcTab({ indices, setIndices }: { indices: IndexDef[]; setIndices: React.Dispatch<React.SetStateAction<IndexDef[]>> }) {
  const dark    = useDark()
  const canEdit = useCanEdit()
  const [formulas, setFormulas] = useState<Record<number, string>>(() =>
    Object.fromEntries(indices.map(i => [i.id, i.formula]))
  )
  const [saving, setSaving] = useState<Record<number, boolean>>({})
  const [errors, setErrors] = useState<Record<number, string>>({})
  const [success, setSuccess] = useState<Record<number, boolean>>({})

  useEffect(() => {
    setFormulas(Object.fromEntries(indices.map(i => [i.id, i.formula])))
  }, [indices])

  async function saveFormula(idx: IndexDef) {
    setSaving(s => ({ ...s, [idx.id]: true }))
    setErrors(e => ({ ...e, [idx.id]: '' }))
    setSuccess(s => ({ ...s, [idx.id]: false }))
    try {
      const body: IndexDefIn = { code: idx.code, name: idx.name, formula: formulas[idx.id] ?? '', description: idx.description, sort_order: idx.sort_order, is_active: idx.is_active, granularity: idx.granularity }
      const updated = await updateIndex(idx.id, body)
      setIndices(l => l.map(i => i.id === updated.id ? { ...updated, sub_metrics: i.sub_metrics } : i))
      setSuccess(s => ({ ...s, [idx.id]: true }))
    } catch (e: any) {
      setErrors(er => ({ ...er, [idx.id]: e.message }))
    } finally {
      setSaving(s => ({ ...s, [idx.id]: false }))
    }
  }

  if (indices.length === 0) return <div className="empty-state">请先在「指标定义」中添加指标和分项</div>

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ fontSize: 13, color: T.infoColor(dark), background: T.infoBg(dark), borderRadius: 7, padding: '10px 14px' }}>
        公式中使用各指标的分项变量名（如 A、B、C）进行计算，结果即为该指标的当月指数值。
      </div>
      {indices.map(idx => (
        <div key={idx.id} className="data-card" style={{ padding: '16px 20px', background: T.cardBg(dark) }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
            <span style={{ fontWeight: 700, color: T.textPrimary(dark), fontSize: 15 }}>{idx.name}</span>
            <code style={{ color: T.codeColor(dark), fontSize: 12, background: T.codeBg(dark), borderRadius: 4, padding: '1px 6px' }}>{idx.code}</code>
            {idx.sub_metrics.length > 0 && (
              <span style={{ fontSize: 12, color: T.textSecondary(dark) }}>
                可用变量：{idx.sub_metrics.map(sm => (
                  <code key={sm.id} style={{ background: T.codeBg(dark), color: T.codeColor(dark), borderRadius: 4, padding: '1px 5px', marginRight: 4 }}>{sm.code}</code>
                ))}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <input
              className="entry-cell-input"
              style={{ flex: 1, height: 38, ...inputStyle(dark, { fontFamily: 'monospace', fontSize: 13 }) }}
              placeholder="例：A/80000*0.6 + B/0.5*0.2 + C/150000*0.2"
              value={formulas[idx.id] ?? ''}
              onChange={e => canEdit && setFormulas(f => ({ ...f, [idx.id]: e.target.value }))}
              readOnly={!canEdit}
            />
            {canEdit && (
              <button type="button" className="btn-primary" style={{ flexShrink: 0 }} onClick={() => saveFormula(idx)} disabled={saving[idx.id]}>
                保存
              </button>
            )}
          </div>
          {errors[idx.id] && <div className="form-error" style={{ marginTop: 8 }}>{errors[idx.id]}</div>}
          {success[idx.id] && <div className="form-message" style={{ marginTop: 8 }}>保存成功</div>}
          {idx.sub_metrics.length === 0 && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#f59e0b' }}>⚠ 该指标尚无分项，请先在「指标定义」中添加分项</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Tab 3: 综合指数计算 ───────────────────────────────────────
function CompositeTab({ indices }: { indices: IndexDef[] }) {
  const dark    = useDark()
  const canEdit = useCanEdit()
  const [cfg, setCfg] = useState<CompositeFormula>({ label: '综合指数', formula: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    getCompositeFormula().then(setCfg).finally(() => setLoading(false))
  }, [])

  async function save() {
    setSaving(true); setError(''); setSuccess(false)
    try { await updateCompositeFormula(cfg); setSuccess(true) }
    catch (e: any) { setError(e.message) } finally { setSaving(false) }
  }

  return (
    <div style={{ maxWidth: 680 }}>
      {loading && <div className="empty-state">加载中…</div>}
      {!loading && (
        <div style={{ display: 'grid', gap: 16 }}>
          <div className="data-card" style={{ padding: '20px 24px', display: 'grid', gap: 14, background: T.cardBg(dark) }}>
            {field('综合指数名称', (
              <input className="entry-cell-input" style={inputStyle(dark)} value={cfg.label} onChange={e => canEdit && setCfg(c => ({ ...c, label: e.target.value }))} readOnly={!canEdit} />
            ), dark)}
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.textSecondary(dark), marginBottom: 4 }}>综合计算公式</div>
              <div style={{ fontSize: 12, color: T.textMuted(dark), marginBottom: 8 }}>
                可用变量（各指标代码）：
                {indices.map(i => (
                  <code key={i.id} style={{ background: T.codeBg(dark), color: T.codeColor(dark), borderRadius: 4, padding: '1px 5px', marginRight: 4 }}>{i.code}</code>
                ))}
              </div>
              <textarea
                style={{ width: '100%', height: 88, ...inputStyle(dark, { padding: '8px 12px', fontSize: 13, resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.6, height: 88 }) }}
                value={cfg.formula}
                onChange={e => canEdit && setCfg(c => ({ ...c, formula: e.target.value }))}
                readOnly={!canEdit}
                placeholder="例：agri*100 + futures/10 + industry*100"
              />
            </div>
            {error && <div className="form-error">{error}</div>}
            {success && <div className="form-message">保存成功</div>}
            {canEdit && <div><button type="button" className="btn-primary" onClick={save} disabled={saving || !cfg.label}>保存</button></div>}
          </div>
          {indices.length > 0 && (
            <div className="data-card" style={{ padding: '14px 20px', background: T.cardBg(dark) }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.textMuted(dark), textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>各指标计算公式参考</div>
              {indices.map(idx => (
                <div key={idx.id} style={{ display: 'flex', alignItems: 'baseline', gap: 10, padding: '6px 0', borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
                  <code style={{ color: T.codeColor(dark), minWidth: 80, fontSize: 12 }}>{idx.code}</code>
                  <span style={{ color: T.textPrimary(dark), fontSize: 13 }}>{idx.name}</span>
                  <span style={{ color: T.textMuted(dark), fontSize: 12, fontFamily: 'monospace', flex: 1 }}>{idx.formula || '（未配置公式）'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Single sub-metric sync card ───────────────────────────────
function SmSyncCard({ sm, indexName, months }: {
  sm: { id: number; code: string; name: string; db_table: string | null; db_field: string | null; db_aggregation: string; db_date_col: string; db_extra_where: string | null }
  indexName: string
  months: number
}) {
  const dark    = useDark()
  const canEdit = useCanEdit()
  const [preview, setPreview] = useState<SmSyncItem[] | null>(null)
  const [dailyPreview, setDailyPreview] = useState<HarvestDailyPreviewItem[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [pipelineStatus, setPipelineStatus] = useState<HarvestPipelineSyncResult | null>(null)
  const [showPipelineDetails, setShowPipelineDetails] = useState(false)
  const [monitor, setMonitor] = useState<HarvestMonitorResult | null>(null)
  const [monitorLoading, setMonitorLoading] = useState(false)
  const [monitorError, setMonitorError] = useState('')
  const [showMonitorDetails, setShowMonitorDetails] = useState(false)
  // 只判断表名，字段名可以是 production_ag / production_bg 等任意列
  const isHarvestProduction = sm.db_table === 'dwd.sap_harvest_actual_block_daily'

  useEffect(() => {
    if (!isHarvestProduction) return
    let alive = true
    loadMonitor()
    getCurrentSapHarvestPipeline()
      .then(current => {
        if (!alive || !current || current.status !== 'running') return
        setPipelineStatus(current)
        setSyncing(true)
        return followPipeline(current)
      })
      .catch(() => undefined)
      .finally(() => { setSyncing(false) })
    return () => { alive = false }
  }, [isHarvestProduction])

  async function loadMonitor(refresh = false) {
    if (!isHarvestProduction) return
    setMonitorLoading(true); setMonitorError('')
    try {
      const next = await getSapHarvestMonitor(refresh, sm.db_field ?? undefined)
      setMonitor(next)
    } catch (e: any) {
      setMonitorError(e.message ?? '加载农业产量监控失败')
    } finally {
      setMonitorLoading(false)
    }
  }

  async function followPipeline(started: HarvestPipelineSyncResult) {
    let current = started
    while (current.status === 'running') {
      await new Promise(resolve => setTimeout(resolve, 1500))
      current = await getSapHarvestPipelineStatus(current.job_id)
      setPipelineStatus(current)
    }
    return current
  }

  async function handlePreview() {
    // 已有预览时再次点击 → 关闭
    if (preview || dailyPreview) {
      setPreview(null); setDailyPreview(null); return
    }
    setLoading(true); setErr(''); setMsg('')
    try {
      if (isHarvestProduction) {
        setDailyPreview(await getSapHarvestDailyPreview(7))
      } else {
        setPreview(await previewSubMetricSync(sm.id, months))
      }
    }
    catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  // 仅从 DWD 更新指标（跳过 SQL Server → ODS → DWD 阶段）
  async function handleSyncIndexOnly() {
    setSyncing(true); setErr(''); setMsg('')
    try {
      const r = await syncSubMetric(sm.id, months)
      // 说明：DWD 是日度数据，此处按月聚合财年累计后写入指标（每月一个快照值）
      setMsg(`从 DWD 日度数据聚合完成，写入 ${r.synced} 个月度指标值`)
      setPreview(null)
    } catch (e: any) { setErr(e.message) } finally { setSyncing(false) }
  }

  // 全量同步（SQL Server → ODS → DWD → 指标）
  async function handleSync() {
    setSyncing(true); setErr(''); setMsg(''); setPipelineStatus(null)
    try {
      if (isHarvestProduction) {
        const started = await syncSapHarvestPipeline(months)
        setPipelineStatus(started)
        const current = await followPipeline(started)
        if (current.status === 'failed') throw new Error(current.error || current.message || '产量源数据同步失败')
      }
      if (isHarvestProduction) setMsg('正在写入指标月度数据…')
      const r = await syncSubMetric(sm.id, months)
      setMsg(isHarvestProduction ? `全量同步完成，指标月度数据写入 ${r.synced} 条` : `写入 ${r.synced} 条`)
      setPreview(null)
      if (isHarvestProduction) {
        setDailyPreview(await getSapHarvestDailyPreview(7))
        await loadMonitor()
      }
    } catch (e: any) { setErr(e.message) } finally { setSyncing(false) }
  }

  const odsTotalRows = pipelineStatus
    ? Object.values(pipelineStatus.ods_rows).reduce((sum, value) => sum + value, 0)
    : 0

  return (
    <div className="data-card" style={{ padding: '14px 18px', background: T.cardBg(dark) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ color: T.textMuted(dark), fontSize: 12 }}>{indexName}</span>
        <span style={{ color: T.textPrimary(dark), fontWeight: 600 }}>{sm.name || sm.code}</span>
        <code style={{ color: T.codeColor(dark), background: T.codeBg(dark), borderRadius: 4, padding: '1px 6px', fontSize: 12 }}>{sm.code}</code>
        <div style={{ flex: 1 }} />
        <button type="button" className="btn-ghost" style={{ height: 28, padding: '0 12px', fontSize: 12 }} onClick={handlePreview} disabled={loading}>
          {loading ? '查询…' : (preview || dailyPreview) ? '收起预览' : '预览'}
        </button>
        {/* DWD → 指标（跳过数据源同步，直接从现有 DWD 计算写入指标） */}
        {canEdit && isHarvestProduction && (
          <button type="button" className="btn-ghost" style={{ height: 28, padding: '0 12px', fontSize: 12 }} onClick={handleSyncIndexOnly} disabled={syncing}
            title="仅从现有 DWD 数据更新指标，不重新拉取 SQL Server 数据">
            {syncing ? '更新中…' : 'DWD→指标'}
          </button>
        )}
        {canEdit && (
          <button type="button" className="btn-primary" style={{ height: 28, padding: '0 12px', fontSize: 12 }} onClick={handleSync} disabled={syncing}>
            {syncing ? '同步中…' : isHarvestProduction ? '全量同步' : '同步'}
          </button>
        )}
      </div>
      <div style={{ fontSize: 12, color: T.textMuted(dark), fontFamily: 'monospace' }}>
        {sm.db_aggregation}({sm.db_field}) FROM {sm.db_table}
        {` WHERE ${sm.db_date_col} BETWEEN :start AND :end`}
        {sm.db_extra_where ? ` AND (${sm.db_extra_where})` : ''}
      </div>
      {err && <div style={{ fontSize: 12, color: '#f87171', marginTop: 6 }}>{err}</div>}
      {msg && <div style={{ fontSize: 12, color: '#4ade80', marginTop: 6 }}>✓ {msg}</div>}
      {isHarvestProduction && (
        <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12, color: T.textSecondary(dark) }}>
            <span style={{ fontWeight: 700, color: T.textPrimary(dark) }}>数据监控</span>
            {monitor ? (
              <>
                <span>最新 {monitor.summary.max_date ?? '—'}</span>
                <span>应有 {monitor.summary.expected_date}</span>
                <span>过期 {monitor.summary.days_lag == null ? '—' : monitor.summary.days_lag <= 0 ? '未过期' : `${monitor.summary.days_lag} 天`}</span>
                <span>DWD {monitor.summary.total_rows.toLocaleString('zh-CN')} 行</span>
                <span>园区 {monitor.summary.estate_count.toLocaleString('zh-CN')}</span>
              </>
            ) : (
              <span>{monitorLoading ? '加载中…' : '暂无监控数据'}</span>
            )}
            {monitorError && <span style={{ color: '#f87171' }}>{monitorError}</span>}
            <button type="button" className="btn-row" style={{ height: 24, padding: '0 8px', fontSize: 11 }} onClick={() => loadMonitor(true)} disabled={monitorLoading}>
              {monitorLoading ? '刷新中…' : '刷新'}
            </button>
            {monitor && (
              <button type="button" className="btn-row" style={{ height: 24, padding: '0 8px', fontSize: 11 }} onClick={() => setShowMonitorDetails(v => !v)}>
                {showMonitorDetails ? '收起监控' : '展开监控'}
              </button>
            )}
          </div>
          {showMonitorDetails && monitor && (
            <div style={{ overflowX: 'auto', padding: '6px 8px', background: dark ? '#0f1117' : '#f8fafc', border: `1px solid ${T.sectionBorder(dark)}`, borderRadius: 6 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr>
                    {['公司', '园区', '最新日期', '过期', '近7天', sm.db_field === 'production_bg' ? '最新扣重前' : '最新扣重后', '行数', '状态'].map(h => (
                      <th key={h} style={{ padding: '4px 8px', textAlign: h === '公司' || h === '园区' ? 'left' : 'right', color: T.textSecondary(dark), borderBottom: `1px solid ${T.sectionBorder(dark)}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {monitor.estates.map(row => {
                    const color = row.status === 'ok' ? '#4ade80' : row.status === 'lagging' ? '#fbbf24' : '#f87171'
                    const label = row.status === 'ok' ? '正常' : row.status === 'lagging' ? '滞后' : row.status === 'stale' ? '过期' : '无数据'
                    return (
                      <tr key={row.estate_code}>
                        <td style={{ padding: '4px 8px', color: T.textPrimary(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
                          {row.company_code ? <code style={{ color: T.codeColor(dark) }}>{row.company_code}</code> : '—'}
                        </td>
                        <td style={{ padding: '4px 8px', color: T.textPrimary(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
                          <code style={{ color: T.codeColor(dark) }}>{row.estate_code}</code> {row.estate_name}
                        </td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: T.textPrimary(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{row.latest_date ?? '—'}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: T.textSecondary(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{row.days_lag == null ? '—' : row.days_lag <= 0 ? '未过期' : `${row.days_lag} 天`}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: T.textSecondary(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{row.days_with_data_7d}/7</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: '#4ade80', fontWeight: 600, borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{row.latest_production_ag.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color: T.textSecondary(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{row.row_count.toLocaleString('zh-CN')}</td>
                        <td style={{ padding: '4px 8px', textAlign: 'right', color, fontWeight: 700, borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{label}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {pipelineStatus && (
        <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12, color: T.textSecondary(dark) }}>
            {[
              ['SQL Server → ODS', pipelineStatus.current_step === 'sqlserver_to_ods' ? '同步中' : odsTotalRows > 0 ? '完成' : '等待'],
              ['ODS → DWD', pipelineStatus.current_step === 'ods_to_dwd' ? '同步中' : pipelineStatus.dwd_rows > 0 ? '完成' : '等待'],
              ['DWD → 指标', msg.startsWith('正在写入') ? '同步中' : msg.includes('指标月度数据写入') ? '完成' : '等待'],
            ].map(([label, state]) => (
              <span key={label} style={{
                padding: '3px 8px', borderRadius: 5,
                background: state === '同步中' ? 'rgba(96,165,250,0.15)' : state === '完成' ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.05)',
                color: state === '同步中' ? '#60a5fa' : state === '完成' ? '#4ade80' : T.textMuted(dark),
              }}>{label}：{state}</span>
            ))}
            <span>ODS {odsTotalRows.toLocaleString('zh-CN')} 行</span>
            <span>DWD {pipelineStatus.dwd_rows ? pipelineStatus.dwd_rows.toLocaleString('zh-CN') : '—'} 行</span>
            <button type="button" className="btn-row" style={{ height: 24, padding: '0 8px', fontSize: 11 }} onClick={() => setShowPipelineDetails(v => !v)}>
              {showPipelineDetails ? '收起明细' : '展开明细'}
            </button>
          </div>
          {pipelineStatus.current_step === 'sqlserver_to_ods' && pipelineStatus.current_table && (
            <div style={{ fontSize: 12, color: T.textMuted(dark) }}>
              当前表：<code style={{ color: T.codeColor(dark) }}>{pipelineStatus.current_table}</code>
              ，已写入 {pipelineStatus.current_rows.toLocaleString('zh-CN')} 行
            </div>
          )}
          {pipelineStatus.current_step === 'ods_to_dwd' && (
            <div style={{ fontSize: 12, color: '#60a5fa' }}>正在刷新 DWD 产量表，完成后会显示 DWD 行数。</div>
          )}
          {showPipelineDetails && pipelineStatus.source_tables.length > 0 && (
            <div style={{ display: 'grid', gap: 6, padding: '8px 10px', background: dark ? '#0f1117' : '#f8fafc', border: `1px solid ${T.sectionBorder(dark)}`, borderRadius: 6 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted(dark) }}>ODS 表同步明细</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 1fr) 90px 80px', gap: 8, fontSize: 11, color: T.textSecondary(dark) }}>
                <span>源表</span>
                <span style={{ textAlign: 'right' }}>行数</span>
                <span style={{ textAlign: 'right' }}>状态</span>
                {pipelineStatus.source_tables.map(table => {
                  const rowCount = pipelineStatus.ods_rows[table]
                  const isCurrent = pipelineStatus.current_table === table
                  const done = rowCount != null
                  return (
                    <span key={table} style={{ display: 'contents' }}>
                      <code style={{ color: isCurrent ? '#60a5fa' : T.codeColor(dark), overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{table}</code>
                      <span style={{ textAlign: 'right', color: done || isCurrent ? '#e2e8f0' : T.textMuted(dark) }}>
                        {done ? rowCount.toLocaleString('zh-CN') : isCurrent ? pipelineStatus.current_rows.toLocaleString('zh-CN') : '—'}
                      </span>
                      <span style={{ textAlign: 'right', color: done ? '#4ade80' : isCurrent ? '#60a5fa' : T.textMuted(dark) }}>
                        {done ? '完成' : isCurrent ? '同步中' : '等待'}
                      </span>
                    </span>
                  )
                })}
              </div>
              {pipelineStatus.logs.length > 0 && (
                <pre style={{ maxHeight: 92, overflow: 'auto', margin: 0, padding: '6px 8px', background: dark ? '#11131b' : '#fff', border: `1px solid ${T.sectionBorder(dark)}`, borderRadius: 6, color: T.textMuted(dark), fontSize: 11, lineHeight: 1.45 }}>
                  {pipelineStatus.logs.slice(-18).join('\n')}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
      {dailyPreview && (
        <div style={{ marginTop: 10, overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: 12, width: '100%' }}>
            <thead>
              <tr>
                {['日期', '扣重前', '扣重后', '单位', 'DWD行数'].map(h => (
                  <th key={h} style={{ padding: '4px 10px', background: dark ? 'rgba(255,255,255,0.05)' : '#f8fafc', borderBottom: `1px solid ${T.sectionBorder(dark)}`, textAlign: h === '日期' ? 'left' : 'right', color: T.textSecondary(dark) }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dailyPreview.map(r => (
                <tr key={r.date}>
                  <td style={{ padding: '3px 10px', color: T.textPrimary(dark), fontFamily: 'monospace', borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{r.date}</td>
                  <td style={{ padding: '3px 10px', textAlign: 'right', color: '#60a5fa', fontWeight: 600, borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{r.production_bg.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}</td>
                  <td style={{ padding: '3px 10px', textAlign: 'right', color: '#4ade80', fontWeight: 600, borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{r.production_ag.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}</td>
                  <td style={{ padding: '3px 10px', textAlign: 'right', color: T.textMuted(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{r.unit}</td>
                  <td style={{ padding: '3px 10px', textAlign: 'right', color: T.textMuted(dark), borderBottom: `1px solid ${T.rowBorder(dark)}` }}>{r.row_count.toLocaleString('zh-CN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {preview && (
        <div style={{ marginTop: 10, overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: 12, width: '100%' }}>
            <thead>
              <tr>
                {['年月', '值'].map(h => (
                  <th key={h} style={{ padding: '4px 10px', background: dark ? 'rgba(255,255,255,0.05)' : '#f8fafc', borderBottom: `1px solid ${T.sectionBorder(dark)}`, textAlign: 'left', color: T.textSecondary(dark) }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.map(r => (
                <tr key={`${r.year}-${r.month}`}>
                  <td style={{ padding: '3px 10px', color: T.textPrimary(dark), fontFamily: 'monospace', borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
                    {r.year}/{String(r.month).padStart(2, '0')}
                  </td>
                  <td style={{ padding: '3px 10px', textAlign: 'right', color: r.value == null ? T.textMuted(dark) : '#60a5fa', fontWeight: 600, borderBottom: `1px solid ${T.rowBorder(dark)}` }}>
                    {r.value == null ? '—' : r.value.toLocaleString('zh-CN', { maximumFractionDigits: 4 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab 4: 数据同步 ───────────────────────────────────────────
function DataSyncTab({ indices }: { indices: IndexDef[] }) {
  const dark = useDark()
  const [months, setMonths] = useState(12)

  // All sub-metrics with source_type = db_sync AND db_table configured
  const dbSyncSms = indices.flatMap(idx =>
    idx.sub_metrics
      .filter(sm => sm.source_type === 'db_sync')
      .map(sm => ({ ...sm, indexName: idx.name }))
  )
  const configuredSms = dbSyncSms.filter(sm => sm.db_table && sm.db_field)
  const unconfiguredSms = dbSyncSms.filter(sm => !sm.db_table || !sm.db_field)

  return (
    <div style={{ maxWidth: 900 }}>
      {/* Header controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ fontSize: 14, color: T.textSecondary(dark) }}>
          共 {dbSyncSms.length} 个数据库来源分项，{configuredSms.length} 个已配置
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: T.textMuted(dark) }}>同步月数</span>
          <input type="number" min={1} max={36} style={{ width: 70, ...inputStyle(dark) }}
            value={months} onChange={e => setMonths(Math.min(36, Math.max(1, +e.target.value)))} />
        </div>
      </div>

      {dbSyncSms.length === 0 && (
        <div className="empty-state">暂无「从数据库提取」分项，请在「指标定义」中将分项数据来源设为「从数据库提取」并配置表名和字段</div>
      )}

      {/* Unconfigured warning */}
      {unconfiguredSms.length > 0 && (
        <div style={{ padding: '10px 14px', marginBottom: 12, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 7, fontSize: 13, color: '#fbbf24' }}>
          ⚠ {unconfiguredSms.length} 个分项尚未配置表名/字段：
          {unconfiguredSms.map(s => <code key={s.id} style={{ marginLeft: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 3, padding: '0 4px' }}>{s.code}</code>)}
          。请在「指标定义」中编辑分项并填写数据库配置。
        </div>
      )}

      {/* Configured sync cards */}
      <div style={{ display: 'grid', gap: 12 }}>
        {configuredSms.map(sm => (
          <SmSyncCard key={sm.id} sm={sm} indexName={sm.indexName} months={months} />
        ))}
      </div>
    </div>
  )
}

// ── Tab 5: 定时同步 ───────────────────────────────────────────

const SYNC_TYPE_LABELS: Record<string, string> = {
  sub_metric:      '分项DB同步',
  sap_harvest:     'SAP产量管道',
  agri_production: '农业累计产量',
}

const STATUS_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  success: { color: '#4ade80', bg: 'rgba(74,222,128,0.12)', label: '成功' },
  failed:  { color: '#f87171', bg: 'rgba(248,113,113,0.12)', label: '失败' },
  running: { color: '#60a5fa', bg: 'rgba(96,165,250,0.12)',  label: '运行中' },
  skipped: { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', label: '跳过' },
}

const EMPTY_SCHED: ScheduledSyncIn = {
  name: '', sync_type: 'sub_metric', sub_metric_id: null,
  months: 12, cron_minute: '0', cron_hour: '2',
  cron_day: '*', cron_month: '*', cron_dow: '*', enabled: true,
}

function cronLabel(j: ScheduledSyncOut) {
  const dow = j.cron_dow === '*' ? '每天' : `周${j.cron_dow}`
  return `${dow} ${j.cron_hour}:${j.cron_minute.padStart(2,'0')}`
}

function ScheduledTab({ indices }: { indices: IndexDef[] }) {
  const dark    = useDark()
  const canEdit = useCanEdit()

  const [jobs, setJobs]       = useState<ScheduledSyncOut[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding]   = useState(false)
  const [editId, setEditId]   = useState<number | null>(null)
  const [form, setForm]       = useState<ScheduledSyncIn>(EMPTY_SCHED)
  const [saving, setSaving]   = useState(false)
  const [running, setRunning] = useState<number | null>(null)
  const [err, setErr]         = useState('')

  useEffect(() => {
    setLoading(true)
    getScheduledSyncs().then(setJobs).finally(() => setLoading(false))
  }, [])

  // 所有分项 flat list（供 sub_metric 选择）
  const allSms = indices.flatMap(idx =>
    idx.sub_metrics.map(sm => ({ ...sm, indexName: idx.name, indexCode: idx.code }))
  )

  function openAdd() {
    setForm(EMPTY_SCHED); setEditId(null); setAdding(true); setErr('')
  }
  function openEdit(j: ScheduledSyncOut) {
    const { id, last_run_at, last_status, last_message, created_by, created_at, updated_at, ...rest } = j
    setForm(rest); setEditId(id); setAdding(true); setErr('')
  }

  async function handleSave() {
    if (!form.name) return
    setSaving(true); setErr('')
    try {
      if (editId != null) {
        const updated = await updateScheduledSync(editId, form)
        setJobs(l => l.map(j => j.id === editId ? updated : j))
      } else {
        const created = await createScheduledSync(form)
        setJobs(l => [...l, created])
      }
      setAdding(false)
    } catch (e: any) { setErr(e.message) } finally { setSaving(false) }
  }

  async function handleDelete(id: number) {
    if (!confirm('确认删除该定时任务？')) return
    await deleteScheduledSync(id)
    setJobs(l => l.filter(j => j.id !== id))
  }

  async function handleRun(id: number) {
    setRunning(id)
    try {
      const updated = await triggerScheduledSync(id)
      setJobs(l => l.map(j => j.id === id ? updated : j))
    } catch (e: any) { setErr(e.message) } finally { setRunning(null) }
  }

  const inputSt = inputStyle(dark)
  const selSt   = selectStyle(dark)

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ fontSize: 13, color: T.infoColor(dark), background: T.infoBg(dark), borderRadius: 7, padding: '8px 14px' }}>
          定时任务按 Cron 表达式运行，服务器时区为马来西亚时间（UTC+8）。重启服务后自动从数据库恢复。
        </div>
        {canEdit && (
          <button type="button" className="btn-primary" style={{ marginLeft: 12, flexShrink: 0 }} onClick={openAdd}>
            + 新增定时任务
          </button>
        )}
      </div>

      {/* 新增/编辑表单 */}
      {canEdit && adding && (
        <div className="data-card" style={{ padding: '16px 20px', marginBottom: 14, background: T.cardBg(dark) }}>
          <div style={{ fontWeight: 700, color: T.textPrimary(dark), marginBottom: 12 }}>
            {editId != null ? '编辑定时任务' : '新增定时任务'}
          </div>
          {err && <div className="form-error" style={{ marginBottom: 8 }}>{err}</div>}
          <div className="form-grid" style={{ marginBottom: 10 }}>
            {field('任务名称', (
              <input className="entry-cell-input" style={inputSt} value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如：农业产量每日同步" />
            ), dark)}
            {field('同步类型', (
              <select style={selSt} value={form.sync_type}
                onChange={e => setForm(f => ({ ...f, sync_type: e.target.value as ScheduledSyncIn['sync_type'], sub_metric_id: null }))}>
                <option value="sub_metric">分项DB同步</option>
                <option value="sap_harvest">SAP产量管道（全量）</option>
                <option value="agri_production">农业累计产量</option>
              </select>
            ), dark)}
            {(form.sync_type === 'sub_metric' || form.sync_type === 'agri_production') && field('目标分项', (
              <select style={selSt} value={form.sub_metric_id ?? ''}
                onChange={e => setForm(f => ({ ...f, sub_metric_id: e.target.value ? +e.target.value : null }))}>
                <option value="">-- 请选择 --</option>
                {allSms.map(sm => (
                  <option key={sm.id} value={sm.id}>{sm.indexName} / {sm.name}（{sm.code}）</option>
                ))}
              </select>
            ), dark)}
            {field('同步月数', (
              <input type="number" className="entry-cell-input" style={inputSt} min={1} max={36}
                value={form.months} onChange={e => setForm(f => ({ ...f, months: +e.target.value }))} />
            ), dark)}
          </div>

          {/* Cron 配置 */}
          <div style={{ fontSize: 12, fontWeight: 700, color: T.textSecondary(dark), marginBottom: 8 }}>执行计划（Cron）</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 10, marginBottom: 10 }}>
            {([
              ['分钟', 'cron_minute', '0-59 或 *'],
              ['小时', 'cron_hour',   '0-23 或 *'],
              ['日期', 'cron_day',    '1-31 或 *'],
              ['月份', 'cron_month',  '1-12 或 *'],
              ['星期', 'cron_dow',    '0-6 或 mon-sun'],
            ] as [string, keyof ScheduledSyncIn, string][]).map(([label, key, ph]) => (
              <div key={key}>
                <div style={{ fontSize: 11, color: T.textMuted(dark), marginBottom: 4 }}>{label}</div>
                <input className="entry-cell-input" style={{ ...inputSt, width: '100%' }}
                  placeholder={ph} value={String(form[key] ?? '')}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: T.textMuted(dark), marginBottom: 12 }}>
            示例：每天凌晨2点 → 分0 时2 日* 月* 周*；每周一凌晨3点 → 分0 时3 日* 月* 周mon
          </div>

          {field('启用', (
            <select style={selSt} value={form.enabled ? 'yes' : 'no'}
              onChange={e => setForm(f => ({ ...f, enabled: e.target.value === 'yes' }))}>
              <option value="yes">启用</option>
              <option value="no">停用</option>
            </select>
          ), dark)}

          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button type="button" className="btn-primary" onClick={handleSave} disabled={saving || !form.name}>
              {saving ? '保存中…' : '保存'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => setAdding(false)}>取消</button>
          </div>
        </div>
      )}

      {loading && <div style={{ color: T.textMuted(dark) }}>加载中…</div>}

      {!loading && jobs.length === 0 && (
        <div className="empty-state">
          {canEdit
            ? '暂无定时任务，点击右上角「+ 新增定时任务」开始配置'
            : '暂无定时任务，需要管理员或分析员权限才能配置'
          }
        </div>
      )}

      {/* 任务列表 */}
      {!loading && jobs.length > 0 && (
        <div style={{ display: 'grid', gap: 10 }}>
          {jobs.map(j => {
            const statusInfo = j.last_status ? STATUS_STYLE[j.last_status] : null
            return (
              <div key={j.id} className="data-card" style={{ padding: '14px 18px', background: T.cardBg(dark) }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  {/* 启用指示灯 */}
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: j.enabled ? '#4ade80' : '#374151', flexShrink: 0 }} />
                  <span style={{ fontWeight: 700, color: T.textPrimary(dark) }}>{j.name}</span>
                  <span style={{ fontSize: 12, color: T.textMuted(dark), background: 'rgba(255,255,255,0.06)', borderRadius: 4, padding: '1px 8px' }}>
                    {SYNC_TYPE_LABELS[j.sync_type] ?? j.sync_type}
                  </span>
                  <span style={{ fontSize: 12, color: T.textSecondary(dark) }}>
                    🕐 {cronLabel(j)} · {j.months}月
                  </span>
                  {statusInfo && (
                    <span style={{ fontSize: 11, fontWeight: 700, color: statusInfo.color, background: statusInfo.bg, borderRadius: 4, padding: '1px 8px' }}>
                      {statusInfo.label}
                    </span>
                  )}
                  <div style={{ flex: 1 }} />
                  {canEdit && (
                    <>
                      <button type="button" className="btn-ghost" style={{ height: 28, padding: '0 12px', fontSize: 12 }}
                        onClick={() => handleRun(j.id)} disabled={running === j.id}>
                        {running === j.id ? '执行中…' : '立即执行'}
                      </button>
                      <button type="button" className="btn-row" onClick={() => openEdit(j)}>编辑</button>
                      <button type="button" className="btn-row btn-danger" onClick={() => handleDelete(j.id)}>删除</button>
                    </>
                  )}
                </div>
                {j.last_run_at && (
                  <div style={{ marginTop: 8, fontSize: 12, color: T.textMuted(dark) }}>
                    上次运行：{new Date(j.last_run_at).toLocaleString('zh-CN')}
                    {j.last_message && <span style={{ marginLeft: 8, color: statusInfo?.color ?? T.textMuted(dark) }}>{j.last_message}</span>}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}


// ── Tab 6: 通知配置 ───────────────────────────────────────────

function NotifyTab() {
  const dark    = useDark()
  const canEdit = useCanEdit()

  const [cfg, setCfg]                 = useState<TeamsConfig>({ webhook_url: '', notify_on: 'failure' })
  const [botStatus, setBotStatus]     = useState<TeamsBotStatus | null>(null)
  const [targets, setTargets]         = useState<TeamsBotConversation[]>([])
  const [indexCfgs, setIndexCfgs]     = useState<IndexNotificationConfig[]>([])
  const [loading, setLoading]         = useState(true)
  const [saving, setSaving]           = useState(false)
  const [testing, setTesting]         = useState(false)
  const [rowSaving, setRowSaving]     = useState<string | null>(null)
  const [rowTesting, setRowTesting]   = useState<string | null>(null)
  const [msg, setMsg]                 = useState('')
  const [err, setErr]                 = useState('')

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true); setErr('')
    try {
      const [teams, status, convs, notifies] = await Promise.all([
        getTeamsConfig(),
        getTeamsBotStatus(),
        getTeamsBotConversations(),
        getIndexNotifications(),
      ])
      setCfg(teams)
      setBotStatus(status)
      setTargets(convs)
      setIndexCfgs(notifies)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true); setMsg(''); setErr('')
    try { await updateTeamsConfig(cfg); setMsg('保存成功') }
    catch (e: any) { setErr(e.message) } finally { setSaving(false) }
  }

  async function handleTest() {
    setTesting(true); setMsg(''); setErr('')
    try { await testTeamsWebhook(); setMsg('测试消息已发送，请查看 Teams 频道') }
    catch (e: any) { setErr(e.message) } finally { setTesting(false) }
  }

  function patchIndexCfg(code: string, patch: Partial<IndexNotificationConfig>) {
    setIndexCfgs(rows => rows.map(row => row.index_code === code ? { ...row, ...patch } : row))
  }

  async function handleSaveIndex(row: IndexNotificationConfig) {
    const body: IndexNotificationInput = {
      teams_conversation_id: row.teams_conversation_id,
      cron_minute: row.cron_minute,
      cron_hour: row.cron_hour,
      cron_day: '*',
      cron_month: '*',
      cron_dow: '*',
      enabled: row.enabled,
    }
    setRowSaving(row.index_code); setMsg(''); setErr('')
    try {
      const updated = await updateIndexNotification(row.index_code, body)
      patchIndexCfg(row.index_code, updated)
      setMsg(`${row.index_name} 通知配置已保存`)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setRowSaving(null)
    }
  }

  async function handleTestIndex(row: IndexNotificationConfig) {
    setRowTesting(row.index_code); setMsg(''); setErr('')
    try {
      const updated = await testIndexNotification(row.index_code)
      patchIndexCfg(row.index_code, updated)
      if (updated.last_status === 'success') setMsg(`${row.index_name} 测试通知已发送`)
      else setErr(updated.last_message || `${row.index_name} 测试通知发送失败`)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setRowTesting(null)
    }
  }

  const inputSt = inputStyle(dark)
  const selSt   = selectStyle(dark)
  const thSt: React.CSSProperties = { padding: '8px 10px', color: T.textMuted(dark), fontSize: 12, textAlign: 'left', borderBottom: `1px solid ${T.rowBorder(dark)}` }
  const tdSt: React.CSSProperties = { padding: '8px 10px', borderBottom: `1px solid ${T.rowBorder(dark)}`, verticalAlign: 'middle' }

  return (
    <div style={{ maxWidth: 1120 }}>
      {loading && <div style={{ color: T.textMuted(dark) }}>加载中…</div>}
      {!loading && (
        <div style={{ display: 'grid', gap: 16 }}>
          <div className="data-card" style={{ padding: '20px 24px', background: T.cardBg(dark), maxWidth: 680 }}>
            <div style={{ fontWeight: 700, color: T.textPrimary(dark), fontSize: 15, marginBottom: 4 }}>
              Microsoft Teams Workflow 推送
            </div>
            <div style={{ fontSize: 12, color: T.textMuted(dark), marginBottom: 16 }}>
              保留当前可用的 Workflow Webhook。Bot 通知配置在下方，不会覆盖这个地址。
            </div>

            <div style={{ display: 'grid', gap: 12 }}>
              {field('Webhook URL', (
                <input
                  className="entry-cell-input"
                  style={{ ...inputSt, fontFamily: 'monospace', fontSize: 12 }}
                  value={cfg.webhook_url}
                  onChange={e => canEdit && setCfg(c => ({ ...c, webhook_url: e.target.value }))}
                  readOnly={!canEdit}
                  placeholder="https://xxxxx.webhook.office.com/webhookb2/..."
                />
              ), dark)}

              {field('推送时机', (
                <select style={selSt} value={cfg.notify_on}
                  onChange={e => canEdit && setCfg(c => ({ ...c, notify_on: e.target.value }))}
                  disabled={!canEdit}>
                  <option value="">不推送</option>
                  <option value="success">仅成功时</option>
                  <option value="failure">仅失败时</option>
                  <option value="success,failure">成功和失败都推送</option>
                </select>
              ), dark)}
            </div>

            {err && <div className="form-error" style={{ marginTop: 10 }}>{err}</div>}
            {msg && <div className="form-message" style={{ marginTop: 10 }}>{msg}</div>}

            {canEdit && (
              <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
                  {saving ? '保存中…' : '保存'}
                </button>
                <button type="button" className="btn-ghost" onClick={handleTest}
                  disabled={testing || !cfg.webhook_url}>
                  {testing ? '发送中…' : '发送测试消息'}
                </button>
              </div>
            )}
          </div>

          <div className="data-card" style={{ padding: '16px 20px', background: T.cardBg(dark) }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
              <div>
                <div style={{ fontWeight: 700, color: T.textPrimary(dark), fontSize: 15 }}>Teams Bot 状态</div>
                <div style={{ fontSize: 12, color: T.textMuted(dark), marginTop: 4 }}>
                  Bot 装到频道或个人聊天后，系统会在这里显示可选目标。
                </div>
              </div>
              <button type="button" className="btn-ghost" onClick={loadAll}>刷新目标</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10, marginBottom: 14 }}>
              <div style={{ fontSize: 12, color: T.textSecondary(dark) }}>App ID：{botStatus?.app_id_configured ? '已配置' : '未配置'}</div>
              <div style={{ fontSize: 12, color: T.textSecondary(dark) }}>Secret：{botStatus?.app_password_configured ? '已配置' : '未配置'}</div>
              <div style={{ fontSize: 12, color: T.textSecondary(dark) }}>入站校验：{botStatus?.validate_incoming ? '开启' : '关闭'}</div>
            </div>
            <div style={{ fontSize: 12, color: T.textMuted(dark), marginBottom: 14 }}>
              Messaging endpoint：<code style={{ color: T.codeColor(dark) }}>{botStatus?.messaging_endpoint}</code>
            </div>

            {targets.length === 0 ? (
              <div className="empty-state">暂无 Bot 目标。把 Bot 安装到 Teams 频道或个人聊天后，发送任意消息给 Bot，再点刷新。</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={thSt}>目标</th>
                      <th style={thSt}>类型</th>
                      <th style={thSt}>最后捕获</th>
                    </tr>
                  </thead>
                  <tbody>
                    {targets.map(t => (
                      <tr key={t.id}>
                        <td style={tdSt}>
                          <div style={{ color: T.textPrimary(dark), fontWeight: 600 }}>{t.name || `目标 ${t.id}`}</div>
                          <div style={{ color: T.textMuted(dark), fontSize: 11 }}>{t.user_name || t.channel_id || t.team_id}</div>
                        </td>
                        <td style={{ ...tdSt, color: T.textSecondary(dark), fontSize: 12 }}>{t.conversation_type || 'unknown'}</td>
                        <td style={{ ...tdSt, color: T.textMuted(dark), fontSize: 12 }}>{new Date(t.last_seen_at).toLocaleString('zh-CN')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="data-card" style={{ padding: '16px 20px', background: T.cardBg(dark) }}>
            <div style={{ fontWeight: 700, color: T.textPrimary(dark), fontSize: 15, marginBottom: 4 }}>
              指标 Bot 定时通知
            </div>
            <div style={{ fontSize: 12, color: T.textMuted(dark), marginBottom: 14 }}>
              每个指标可选择不同 Teams 目标和发送时间。链接会自动带 index 参数，点击后优先显示对应指标。
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 980 }}>
                <thead>
                  <tr>
                    <th style={thSt}>指标</th>
                    <th style={thSt}>Teams 目标</th>
                    <th style={thSt}>时</th>
                    <th style={thSt}>分</th>
                    <th style={thSt}>频率</th>
                    <th style={thSt}>启用</th>
                    <th style={thSt}>状态</th>
                    <th style={thSt}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {indexCfgs.map(row => {
                    const statusInfo = row.last_status ? STATUS_STYLE[row.last_status] : null
                    return (
                      <tr key={row.index_code}>
                        <td style={tdSt}>
                          <div style={{ color: T.textPrimary(dark), fontWeight: 700 }}>{row.index_name}</div>
                          <div style={{ color: T.textMuted(dark), fontSize: 11 }}>{row.index_code}</div>
                        </td>
                        <td style={tdSt}>
                          <select style={{ ...selSt, minWidth: 220 }} value={row.teams_conversation_id ?? ''}
                            disabled={!canEdit}
                            onChange={e => patchIndexCfg(row.index_code, { teams_conversation_id: e.target.value ? Number(e.target.value) : null })}>
                            <option value="">-- 请选择 Bot 目标 --</option>
                            {targets.map(t => <option key={t.id} value={t.id}>{t.name || `目标 ${t.id}`}</option>)}
                          </select>
                        </td>
                        <td style={tdSt}>
                          <input className="entry-cell-input" style={{ ...inputSt, width: 58 }} value={row.cron_hour}
                            disabled={!canEdit} onChange={e => patchIndexCfg(row.index_code, { cron_hour: e.target.value })} />
                        </td>
                        <td style={tdSt}>
                          <input className="entry-cell-input" style={{ ...inputSt, width: 58 }} value={row.cron_minute}
                            disabled={!canEdit} onChange={e => patchIndexCfg(row.index_code, { cron_minute: e.target.value })} />
                        </td>
                        <td style={{ ...tdSt, color: T.textSecondary(dark), fontSize: 12 }}>
                          每天
                        </td>
                        <td style={tdSt}>
                          <select style={{ ...selSt, width: 82 }} value={row.enabled ? 'yes' : 'no'}
                            disabled={!canEdit} onChange={e => patchIndexCfg(row.index_code, { enabled: e.target.value === 'yes' })}>
                            <option value="yes">启用</option>
                            <option value="no">停用</option>
                          </select>
                        </td>
                        <td style={tdSt}>
                          {statusInfo ? (
                            <span style={{ fontSize: 11, fontWeight: 700, color: statusInfo.color, background: statusInfo.bg, borderRadius: 4, padding: '2px 8px' }}>
                              {statusInfo.label}
                            </span>
                          ) : <span style={{ color: T.textMuted(dark), fontSize: 12 }}>未发送</span>}
                          {row.last_message && <div style={{ color: T.textMuted(dark), fontSize: 11, marginTop: 4, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.last_message}</div>}
                        </td>
                        <td style={tdSt}>
                          {canEdit && (
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button type="button" className="btn-row" onClick={() => handleSaveIndex(row)} disabled={rowSaving === row.index_code}>
                                {rowSaving === row.index_code ? '保存中' : '保存'}
                              </button>
                              <button type="button" className="btn-row" onClick={() => handleTestIndex(row)} disabled={rowTesting === row.index_code || !row.teams_conversation_id}>
                                {rowTesting === row.index_code ? '发送中' : '测试'}
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ color: T.textMuted(dark), fontSize: 11, marginTop: 10 }}>
              时间使用服务器时区 UTC+8。指标通知固定每天发送，可分别设置每个指标的小时和分钟。
            </div>
          </div>
        </div>
      )}
      {err && <div className="form-error" style={{ marginTop: 10 }}>{err}</div>}
      {msg && <div className="form-message" style={{ marginTop: 10 }}>{msg}</div>}
    </div>
  )
}

// ── SystemTab ─────────────────────────────────────────────────
function SystemTab() {
  const dark = useDark()
  const [preview, setPreview]   = useState<InitDbPreview | null>(null)
  const [loading, setLoading]   = useState(false)
  const [running, setRunning]   = useState(false)
  const [result, setResult]     = useState<InitDbResult | null>(null)
  const [confirmed, setConfirmed] = useState(false)

  function loadPreview() {
    setLoading(true)
    setResult(null)
    setConfirmed(false)
    previewInitDb()
      .then(setPreview)
      .catch(e => alert('获取脚本信息失败：' + e.message))
      .finally(() => setLoading(false))
  }

  function handleRun() {
    if (!confirmed) return
    setRunning(true)
    setResult(null)
    runInitDb()
      .then(r => { setResult(r); setConfirmed(false) })
      .catch(e => alert('执行失败：' + e.message))
      .finally(() => setRunning(false))
  }

  const cardBg     = T.cardBg(dark)
  const textPri    = T.textPrimary(dark)
  const textSec    = T.textSecondary(dark)
  const border     = T.sectionBorder(dark)
  const inputBg    = T.inputBg(dark)
  const inputBdr   = T.inputBorder(dark)

  return (
    <div style={{ display: 'grid', gap: 20, maxWidth: 640 }}>
      <div style={{ background: cardBg, borderRadius: 10, padding: '20px 24px', border: `1px solid ${border}` }}>
        <h3 style={{ margin: '0 0 6px', color: textPri, fontSize: 15, fontWeight: 700 }}>数据库初始化</h3>
        <p style={{ margin: '0 0 16px', color: textSec, fontSize: 13 }}>
          从项目 <code style={{ background: T.codeBg(dark), color: T.codeColor(dark), padding: '1px 6px', borderRadius: 4 }}>init_postgresql.sql</code> 初始化数据库。
          所有建表语句使用 <code style={{ background: T.codeBg(dark), color: T.codeColor(dark), padding: '1px 6px', borderRadius: 4 }}>IF NOT EXISTS</code>，
          插入语句使用 <code style={{ background: T.codeBg(dark), color: T.codeColor(dark), padding: '1px 6px', borderRadius: 4 }}>ON CONFLICT DO NOTHING</code>，
          已有数据不会被覆盖，可安全重复执行。
        </p>

        {/* 第一步：预览 */}
        {!preview && (
          <button type="button" onClick={loadPreview} disabled={loading}
            style={{ padding: '8px 20px', borderRadius: 7, border: `1px solid ${inputBdr}`, background: inputBg, color: textPri, fontSize: 13, cursor: 'pointer' }}>
            {loading ? '读取中…' : '📋 查看脚本信息'}
          </button>
        )}

        {preview && (
          <div style={{ display: 'grid', gap: 14 }}>
            {/* 脚本信息 */}
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', padding: '12px 16px', background: T.infoBg(dark), borderRadius: 8, border: `1px solid ${inputBdr}` }}>
              <div>
                <div style={{ fontSize: 11, color: textSec, marginBottom: 2 }}>文件</div>
                <div style={{ fontSize: 13, color: T.codeColor(dark), fontWeight: 600 }}>{preview.file}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: textSec, marginBottom: 2 }}>大小</div>
                <div style={{ fontSize: 13, color: textPri, fontWeight: 600 }}>{preview.size_kb} KB</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: textSec, marginBottom: 2 }}>语句数</div>
                <div style={{ fontSize: 13, color: textPri, fontWeight: 600 }}>{preview.statement_count} 条</div>
              </div>
            </div>

            {/* 确认勾选 */}
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none' }}>
              <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}
                style={{ width: 15, height: 15, accentColor: '#3b82f6', cursor: 'pointer' }} />
              <span style={{ fontSize: 13, color: textSec }}>我已确认，现在执行初始化</span>
            </label>

            {/* 执行按钮 */}
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="button" onClick={handleRun} disabled={!confirmed || running}
                style={{
                  padding: '9px 24px', borderRadius: 7, border: 'none', fontSize: 13, fontWeight: 600, cursor: confirmed && !running ? 'pointer' : 'not-allowed',
                  background: confirmed && !running ? '#3b82f6' : (dark ? 'rgba(59,130,246,0.2)' : '#bfdbfe'),
                  color: confirmed && !running ? '#fff' : (dark ? '#4b5563' : '#93c5fd'),
                  transition: 'all 0.15s',
                }}>
                {running ? '⏳ 执行中…' : '▶ 执行初始化'}
              </button>
              <button type="button" onClick={loadPreview} disabled={running}
                style={{ padding: '9px 16px', borderRadius: 7, border: `1px solid ${inputBdr}`, background: 'transparent', color: textSec, fontSize: 13, cursor: 'pointer' }}>
                刷新
              </button>
            </div>

            {/* 执行结果 */}
            {result && (
              <div style={{
                padding: '14px 18px', borderRadius: 8,
                background: result.ok ? T.successBg(dark) : (dark ? 'rgba(239,68,68,0.1)' : '#fef2f2'),
                border: `1px solid ${result.ok ? T.successBorder(dark) : (dark ? 'rgba(239,68,68,0.3)' : '#fecaca')}`,
              }}>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6, color: result.ok ? T.successTitle(dark) : (dark ? '#f87171' : '#b91c1c') }}>
                  {result.ok ? '✅ 初始化完成' : '⚠️ 执行有误'}
                </div>
                <div style={{ fontSize: 13, color: result.ok ? T.successText(dark) : (dark ? '#fca5a5' : '#dc2626') }}>
                  {result.message}
                </div>
                {result.errors.length > 0 && (
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 12, color: dark ? '#f87171' : '#b91c1c' }}>
                    {result.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────
export default function IndexMgmtPage({ dark, canEdit = false }: { user: AuthUser; dark?: boolean; canEdit?: boolean }) {
  const isDark = !!dark
  const [tab, setTab] = useState<Tab>('definitions')
  const [indices, setIndices] = useState<IndexDef[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getIndices().then(setIndices).finally(() => setLoading(false))
  }, [])

  const tabs: { key: Tab; label: string }[] = [
    { key: 'definitions', label: '指标定义' },
    { key: 'index_calc',  label: '指数计算' },
    { key: 'composite',   label: '综合指数计算' },
    { key: 'data_sync',   label: '数据同步' },
    { key: 'scheduled',   label: '定时同步' },
    { key: 'notify',      label: '通知配置' },
    { key: 'system',      label: '系统' },
  ]

  return (
    <DarkCtx.Provider value={isDark}>
    <CanEditCtx.Provider value={canEdit}>
      <div style={{ maxWidth: 1100 }}>
        <div className="page-title-section" style={{ marginBottom: 16 }}>
          <p className="page-eyebrow" style={{ color: isDark ? '#60a5fa' : undefined }}>指标管理</p>
          <h1 style={{ margin: '6px 0 4px', fontSize: 22, fontWeight: 700, color: T.textPrimary(isDark) }}>指数指标配置</h1>
          <p className="page-desc" style={{ color: T.textSecondary(isDark) }}>定义指标体系、配置各级计算公式</p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 4, background: T.tabBg(isDark), border: `1px solid ${T.tabBorder(isDark)}`, borderRadius: 8, padding: 5, marginBottom: 16, width: 'fit-content' }}>
          {tabs.map(t => (
            <button key={t.key} type="button"
              style={{
                padding: '7px 20px', border: 'none', borderRadius: 6,
                background: tab === t.key ? T.tabActiveBg(isDark) : 'transparent',
                color: tab === t.key ? '#fff' : T.textSecondary(isDark),
                fontWeight: tab === t.key ? 600 : 500,
                fontSize: 13, cursor: 'pointer', transition: 'all 0.15s',
              }}
              onClick={() => setTab(t.key)}>{t.label}</button>
          ))}
        </div>

        {loading && <div className="empty-state">加载中…</div>}
        {!loading && tab === 'definitions' && <DefinitionsTab indices={indices} setIndices={setIndices} />}
        {!loading && tab === 'index_calc'  && <IndexCalcTab indices={indices} setIndices={setIndices} />}
        {!loading && tab === 'composite'   && <CompositeTab indices={indices} />}
        {!loading && tab === 'data_sync'   && <DataSyncTab indices={indices} />}
        {!loading && tab === 'scheduled'   && <ScheduledTab indices={indices} />}
        {!loading && tab === 'notify'      && <NotifyTab />}
        {tab === 'system'     && <SystemTab />}
      </div>
    </CanEditCtx.Provider>
    </DarkCtx.Provider>
  )
}
