import { useEffect, useMemo, useState } from 'react'
import { getIndexCalc, getSapHarvestMonitor, getSubMetricDetail, getIndices } from '../services/api'
import type { IndexCalcSeries, IndexDef, HarvestMonitorResult, SubMetricTimeSeries } from '../services/api'

// 字段 → 可读标签映射
const PROD_FIELD_LABELS: Record<string, string> = {
  production_ag: '最新扣重后 (kg)',
  production_bg: '最新扣重前 (kg)',
}

// ── 常量 ──────────────────────────────────────────────────────
const INDICES = [
  { id: 'agri',      name: '农业',      color: '#3b82f6' },
  { id: 'futures',   name: '期货',      color: '#22c55e' },
  { id: 'industry',  name: '工业',      color: '#f59e0b' },
  { id: 'livestock', name: '牧业',      color: '#ec4899' },
  { id: 'commerce',  name: '商业',      color: '#a78bfa' },
  { id: 'logistics', name: '物流',      color: '#14b8a6' },
  { id: 'dist',      name: '分配',      color: '#fb923c' },
  { id: 'russell',   name: '罗素骨干',  color: '#06b6d4' },
  { id: 'chicago',   name: '芝加哥人力', color: '#a3e635' },
  { id: 'env',       name: '环境生态',  color: '#f43f5e' },
  { id: 'asset',     name: '资产扩张',  color: '#fbbf24' },
  { id: 'estate',    name: '单数园子',  color: '#c084fc' },
  { id: 'dividend',  name: '分红',      color: '#34d399' },
] as const

type IndexId = (typeof INDICES)[number]['id']

function prevMonths(n: number) {
  const d = new Date(); d.setDate(1)
  const result: { year: number; month: number }[] = []
  for (let i = 0; i < n; i++) {
    result.push({ year: d.getFullYear(), month: d.getMonth() + 1 })
    d.setMonth(d.getMonth() - 1)
  }
  return result.reverse()
}

function fmtPeriod(y: number, m: number) {
  return `${y}/${String(m).padStart(2, '0')}`
}

// ── 表头样式 ─────────────────────────────────────────────────
const TH: React.CSSProperties = {
  padding: '8px 12px', color: '#6b7280', fontSize: 11, fontWeight: 700,
  textTransform: 'uppercase', letterSpacing: '0.04em',
  borderBottom: '1px solid rgba(255,255,255,0.08)', whiteSpace: 'nowrap',
}
const THR: React.CSSProperties = { ...TH, textAlign: 'right' }

// ── 状态徽章 ─────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    ok:      { label: '正常', color: '#4ade80', bg: 'rgba(74,222,128,0.12)' },
    lagging: { label: '滞后', color: '#fbbf24', bg: 'rgba(251,191,36,0.12)' },
    stale:   { label: '过期', color: '#f87171', bg: 'rgba(248,113,113,0.12)' },
    no_data: { label: '无数据', color: '#6b7280', bg: 'rgba(107,114,128,0.1)' },
  }
  const s = map[status] ?? map.no_data
  return (
    <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, color: s.color, background: s.bg }}>
      {s.label}
    </span>
  )
}

// ── 数据完整度单元格 ──────────────────────────────────────────
function CellDot({ value }: { value: number | null | undefined }) {
  if (value == null)
    return <span title="无数据" style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#374151' }} />
  return (
    <span title={String(value.toFixed(2))} style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }} />
  )
}

// ── 主页面 ────────────────────────────────────────────────────
export default function DataMonitorPage() {
  const [selectedId, setSelectedId] = useState<IndexId>('agri')

  // API 数据
  const [apiSeries, setApiSeries]     = useState<IndexCalcSeries[]>([])
  const [indexDefs, setIndexDefs]     = useState<IndexDef[]>([])
  const [monitor, setMonitor]         = useState<HarvestMonitorResult | null>(null)
  const [monitorLoading, setMLoading] = useState(false)
  const [monitorError, setMError]     = useState('')
  const [subMetrics, setSubMetrics]   = useState<SubMetricTimeSeries[]>([])
  const [subLoading, setSubLoading]   = useState(false)
  const [calcLoading, setCalcLoading] = useState(false)

  const periods = useMemo(() => prevMonths(12), [])

  // 拉指数计算（获取指标 id + 粒度） + 指标定义（获取子指标 db_field）
  useEffect(() => {
    setCalcLoading(true)
    Promise.all([getIndexCalc(12), getIndices()])
      .then(([calc, defs]) => { setApiSeries(calc.indices); setIndexDefs(defs) })
      .finally(() => setCalcLoading(false))
  }, [])

  const apiIdx  = apiSeries.find(s => s.code === selectedId)
  const isDaily = apiIdx?.granularity === 'daily'

  // 从指标定义中找到 DWD 连接子指标的 db_field（用于 monitor 查询）
  const { dwdField, hasDwdSubMetric } = useMemo(() => {
    const def = indexDefs.find(d => d.code === selectedId)
    const dwdSm = def?.sub_metrics.find(
      sm => sm.source_type === 'db_sync' && sm.db_table === 'dwd.sap_harvest_actual_block_daily'
    )
    return { dwdField: dwdSm?.db_field ?? 'production_ag', hasDwdSubMetric: !!dwdSm }
  }, [indexDefs, selectedId])

  // 有 DWD 产量子指标的指标才展示园区明细
  const isAgri = hasDwdSubMetric && !!apiIdx

  const prodFieldLabel = PROD_FIELD_LABELS[dwdField] ?? `最新${dwdField} (kg)`

  // 有 DWD 子指标时拉 harvest monitor
  useEffect(() => {
    if (!isAgri) { setMonitor(null); return }
    setMLoading(true); setMError('')
    getSapHarvestMonitor(false, dwdField)
      .then(setMonitor)
      .catch(e => setMError(e.message))
      .finally(() => setMLoading(false))
  }, [isAgri, dwdField])

  // 所有有真实数据的指标：拉分项时序
  useEffect(() => {
    if (!apiIdx) { setSubMetrics([]); return }
    const last = periods[periods.length - 1]
    setSubLoading(true)
    getSubMetricDetail(apiIdx.id, last.year, last.month, 12)
      .then(d => setSubMetrics(d.sub_metrics))
      .catch(() => setSubMetrics([]))
      .finally(() => setSubLoading(false))
  }, [apiIdx?.id, periods])

  // 刷新 harvest monitor
  function refreshMonitor() {
    if (!isAgri) return
    setMLoading(true); setMError('')
    getSapHarvestMonitor(true, dwdField)
      .then(setMonitor)
      .catch(e => setMError(e.message))
      .finally(() => setMLoading(false))
  }

  const idxInfo    = INDICES.find(i => i.id === selectedId)!
  const hasApiData = !!apiIdx && apiIdx.data.some(d => d.value != null)

  // 数据完整度：每个月的指数值（用于完整度格子）
  // 完整度百分比
  const completePct = useMemo(() => {
    if (!apiIdx) return null
    const vals = apiIdx.data.filter(d => d.value != null)
    return Math.round((vals.length / apiIdx.data.length) * 100)
  }, [apiIdx])

  return (
    <div style={{ display: 'grid', gap: 20, width: '100%', minWidth: 0 }}>

      {/* ── Header ── */}
      <div>
        <div style={{ color: '#60a5fa', fontSize: 12, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>
          数据监控
        </div>
        <h2 style={{ margin: '0 0 4px', color: '#f1f5f9', fontWeight: 700, fontSize: 22 }}>
          {idxInfo.name}指标数据状态
        </h2>
      </div>

      {/* ── 指标选择器 ── */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {INDICES.map(idx => {
          const on      = idx.id === selectedId
          const apiInfo = apiSeries.find(s => s.code === idx.id)
          const hasReal = !!apiInfo && apiInfo.data.some(d => d.value != null)
          const isD     = apiInfo?.granularity === 'daily'
          return (
            <button key={idx.id} type="button" onClick={() => setSelectedId(idx.id)} style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 12px', borderRadius: 20, border: '1px solid', fontSize: 12, cursor: 'pointer',
              background:  on ? idx.color + '20' : 'rgba(255,255,255,0.04)',
              borderColor: on ? idx.color + '80' : 'rgba(255,255,255,0.1)',
              color:       on ? '#f1f5f9' : '#6b7280',
              fontWeight:  on ? 600 : 400, transition: 'all 0.15s',
            }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: on ? idx.color : '#374151', flexShrink: 0 }} />
              {idx.name}
              {hasReal && <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#22c55e', flexShrink: 0 }} title="真实数据" />}
              {isD      && <span style={{ fontSize: 10, color: '#60a5fa', fontWeight: 700 }}>日</span>}
            </button>
          )
        })}
      </div>

      {calcLoading && <div style={{ color: '#4b5563', fontSize: 13 }}>加载中…</div>}

      {/* ── 数据概览卡片 ── */}
      {!calcLoading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          {[
            {
              label: '数据来源',
              value: hasApiData ? '真实数据' : '模拟数据',
              color: hasApiData ? '#4ade80' : '#6b7280',
            },
            {
              label: '粒度',
              value: isDaily ? '按日' : '按月',
              color: isDaily ? '#60a5fa' : '#94a3b8',
            },
            {
              label: '近12月完整度',
              value: hasApiData ? `${completePct}%` : '—',
              color: completePct != null && completePct >= 80 ? '#4ade80' : completePct != null && completePct >= 50 ? '#fbbf24' : '#f87171',
            },
            ...(monitor ? [
              { label: 'DWD 最新日期', value: monitor.summary.max_date ?? '—', color: '#f1f5f9' },
              { label: '数据过期天数', value: monitor.summary.days_lag != null ? (monitor.summary.days_lag <= 0 ? '未过期' : `${monitor.summary.days_lag} 天`) : '—', color: monitor.summary.days_lag != null && monitor.summary.days_lag <= 0 ? '#4ade80' : '#f87171' },
              { label: 'DWD 总行数', value: monitor.summary.total_rows.toLocaleString('zh-CN'), color: '#f1f5f9' },
              { label: '园区数量', value: String(monitor.summary.estate_count), color: '#f1f5f9' },
            ] : []),
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background: '#1a1d2a', borderRadius: 10, padding: '14px 16px', border: '1px solid rgba(255,255,255,0.07)' }}>
              <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 6 }}>{label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── 分项数据完整度（近12月格子图） ── */}
      {/* 只展示有月度数据的分项（固定值分项全为 null，排除）*/}
      {!calcLoading && hasApiData && subMetrics.filter(sm => sm.data.some(d => d.value !== null)).length > 0 && (
        <div className="ind-chart-panel" style={{ padding: '16px 20px' }}>
          <div style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>分项数据完整度（近12月）</div>
          <div style={{ color: '#4b5563', fontSize: 11, marginBottom: 12 }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#22c55e', marginRight: 4 }} />有数据
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#374151', marginLeft: 12, marginRight: 4 }} />无数据
          </div>
          {subLoading ? (
            <div style={{ color: '#4b5563' }}>加载中…</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    <th style={{ ...TH, textAlign: 'left', position: 'sticky', left: 0, background: '#1a1d2a', zIndex: 1, minWidth: 120 }}>分项</th>
                    <th style={TH}>单位</th>
                    {periods.map(p => (
                      <th key={`${p.year}-${p.month}`} style={{ ...TH, textAlign: 'center', minWidth: 52 }}>
                        {fmtPeriod(p.year, p.month)}
                      </th>
                    ))}
                    <th style={THR}>有数据月数</th>
                  </tr>
                </thead>
                <tbody>
                  {subMetrics.filter(sm => sm.data.some(d => d.value !== null)).map(sm => {
                    const filled = sm.data.filter(d => d.value != null).length
                    return (
                      <tr key={sm.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '9px 12px', color: '#e2e8f0', fontWeight: 500, position: 'sticky', left: 0, background: '#1a1d2a', whiteSpace: 'nowrap' }}>
                          {sm.name || sm.code}
                          <span style={{ marginLeft: 6, color: '#4b5563', fontFamily: 'monospace' }}>({sm.code})</span>
                        </td>
                        <td style={{ padding: '9px 12px', color: '#6b7280', whiteSpace: 'nowrap' }}>{sm.unit || '—'}</td>
                        {sm.data.map((d, i) => (
                          <td key={i} style={{ padding: '9px 12px', textAlign: 'center' }}>
                            <CellDot value={d.value} />
                          </td>
                        ))}
                        <td style={{ padding: '9px 12px', textAlign: 'right', color: filled === 12 ? '#4ade80' : filled > 0 ? '#fbbf24' : '#f87171', fontWeight: 600 }}>
                          {filled} / 12
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!calcLoading && !hasApiData && (
        <div className="ind-chart-panel" style={{ padding: '16px 20px' }}>
          <div style={{ color: '#4b5563', textAlign: 'center', padding: '24px 0' }}>
            「{idxInfo.name}」暂未接入真实数据，无法展示监控信息。<br />
            <span style={{ fontSize: 11, marginTop: 4, display: 'block' }}>请在「配置管理」中为该指标配置分项数据来源并完成同步。</span>
          </div>
        </div>
      )}

      {/* ── 农业专属：DWD 园区明细 ── */}
      {isAgri && (
        <div className="ind-chart-panel" style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
            <span style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600 }}>DWD 园区数据明细</span>
            {monitorLoading && <span style={{ fontSize: 12, color: '#4b5563' }}>刷新中…</span>}
            {monitorError  && <span style={{ fontSize: 12, color: '#f87171' }}>{monitorError}</span>}
            <button type="button" className="ind-range-btn"
              style={{ marginLeft: 'auto', height: 28, padding: '0 14px', fontSize: 12 }}
              onClick={refreshMonitor} disabled={monitorLoading}>
              刷新
            </button>
          </div>

          {monitorLoading && !monitor ? (
            <div style={{ color: '#4b5563', textAlign: 'center', padding: '24px 0' }}>加载中…</div>
          ) : monitor ? (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    <th style={TH}>公司</th>
                    <th style={TH}>园区</th>
                    <th style={THR}>最新日期</th>
                    <th style={THR}>过期天数</th>
                    <th style={THR}>近7日天数</th>
                    <th style={THR}>{prodFieldLabel}</th>
                    <th style={THR}>总行数</th>
                    <th style={{ ...THR, textAlign: 'center' }}>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {monitor.estates.map(row => (
                    <tr key={row.estate_code} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '8px 12px', color: '#60a5fa', fontFamily: 'monospace' }}>{row.company_code || '—'}</td>
                      <td style={{ padding: '8px 12px', color: '#e2e8f0', whiteSpace: 'nowrap' }}>
                        <code style={{ color: '#7dd3fc', marginRight: 6 }}>{row.estate_code}</code>
                        {row.estate_name}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#94a3b8', fontFamily: 'monospace' }}>{row.latest_date ?? '—'}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: row.days_lag == null ? '#4b5563' : row.days_lag <= 0 ? '#4ade80' : '#f87171' }}>
                        {row.days_lag == null ? '—' : row.days_lag <= 0 ? '未过期' : `${row.days_lag} 天`}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#94a3b8' }}>{row.days_with_data_7d}/7</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#4ade80', fontWeight: 600 }}>
                        {row.latest_production_ag.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280' }}>
                        {row.row_count.toLocaleString('zh-CN')}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                        <StatusBadge status={row.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ color: '#4b5563', textAlign: 'center', padding: '20px 0' }}>暂无监控数据</div>
          )}
        </div>
      )}
    </div>
  )
}
