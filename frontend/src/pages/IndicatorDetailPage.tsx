import { useEffect, useMemo, useState } from 'react'
import { getIndexCalc, getIndexDailyCalc, getSubMetricDetail } from '../services/api'
import type { IndexCalcSeries, DailyDataPoint, SubMetricTimeSeries } from '../services/api'

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

type IndexId    = (typeof INDICES)[number]['id']
type FYKey      = 'current' | 'previous'

function initialSelectedIndex(): IndexId {
  const value = new URLSearchParams(window.location.search).get('index')
  return INDICES.some(idx => idx.id === value) ? value as IndexId : 'agri'
}

// 与 IndicatorDashboard 完全一致：5月目标值，9月从 103 起线性增长
const MOCK_JUNE_TARGETS: Record<string, number> = {
  futures:   172,
  industry:  185,
  livestock: 173,
  commerce:  176,
  logistics: 171,
  dist:      174,
  russell:   178,
  chicago:   172,
  env:       175,
  asset:     183,
  estate:    180,
  dividend:  171,
}

// 财年月份顺序（9月 ~ 8月）
const FY_MONTHS = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]

// 与 Dashboard 完全相同的模拟函数，5月（fyPos=8）精确等于目标值
function mockFYValue(seed: number, fyPos: number, juneTarget: number): number {
  const BASE = 103
  const progress = Math.min(fyPos / 8, 1)
  const trend = BASE + (juneTarget - BASE) * progress
  if (fyPos >= 8) return Math.round(juneTarget * 10) / 10  // 5月及以后精确等于目标
  let rng = (seed + fyPos * 997) >>> 0
  const next = () => { rng = Math.imul(rng, 1664525) + 1013904223 >>> 0; return rng / 0xffffffff }
  const noise = (next() - 0.3) * 7
  return Math.round((trend + noise) * 10) / 10
}

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

function changePct(cur: number | null, prev: number | null): number | null {
  if (cur == null || prev == null || prev === 0) return null
  return ((cur - prev) / Math.abs(prev)) * 100
}

function fmtVal(v: number | null)  { return v == null ? '—' : v.toFixed(2) }
function fmtChg(v: number | null)  {
  if (v == null) return <span style={{ color: '#4b5563' }}>—</span>
  return <span style={{ color: v >= 0 ? '#4ade80' : '#f87171' }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}%</span>
}

// ── 样式常量 ──────────────────────────────────────────────────
const TH: React.CSSProperties = {
  padding: '8px 12px', color: '#6b7280', fontSize: 11, fontWeight: 700,
  textTransform: 'uppercase', letterSpacing: '0.04em',
  borderBottom: '1px solid rgba(255,255,255,0.08)', whiteSpace: 'nowrap',
}

// ── 主页面 ────────────────────────────────────────────────────
export default function IndicatorDetailPage() {
  const [selectedId, setSelectedId]   = useState<IndexId>(() => initialSelectedIndex())
  const [sortAsc, setSortAsc]         = useState(false)
  const [dimension, setDimension]     = useState<'monthly' | 'daily' | 'lastmonth'>('monthly')
  const [selectedFYs, setSelectedFYs] = useState<Set<FYKey>>(new Set<FYKey>(['current']))

  const [apiSeries, setApiSeries]   = useState<IndexCalcSeries[]>([])
  const [dailyData, setDailyData]   = useState<DailyDataPoint[]>([])
  const [subMetrics, setSubMetrics] = useState<SubMetricTimeSeries[]>([])
  const [loading, setLoading]       = useState(false)
  const [subLoading, setSubLoading] = useState(false)
  const [error, setError]           = useState('')

  // ── 财年逻辑 ──
  const currentFYStart = useMemo(() => {
    const now = new Date()
    const m = now.getMonth() + 1
    return m >= 9 ? now.getFullYear() : now.getFullYear() - 1
  }, [])

  function fyStartYear(fy: FYKey) {
    return fy === 'current' ? currentFYStart : currentFYStart - 1
  }
  function fyLabel(fy: FYKey) {
    const sy = fyStartYear(fy)
    return `${sy}/${String(sy + 1).slice(2)}年度`
  }

  function toggleFY(fy: FYKey) {
    setSelectedFYs(prev => {
      const next = new Set(prev)
      if (next.has(fy) && next.size > 1) next.delete(fy)
      else next.add(fy)
      return next
    })
  }

  // ── 数据拉取（始终 24 月，覆盖两个财年） ──
  useEffect(() => {
    setLoading(true); setError('')
    getIndexCalc(24)
      .then(r => setApiSeries(r.indices))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const apiIdx  = apiSeries.find(s => s.code === selectedId)
  const isMock  = !apiIdx || apiIdx.data.every(d => d.value == null)
  const isDaily = apiIdx?.granularity === 'daily'
  const idxInfo = INDICES.find(i => i.id === selectedId)!
  const idxPos  = INDICES.findIndex(i => i.id === selectedId)

  // 切换到非日度指标时，自动退出「本月/上月」模式
  useEffect(() => {
    if ((dimension === 'daily' || dimension === 'lastmonth') && apiSeries.length > 0 && !isDaily) {
      setDimension('monthly')
    }
  }, [selectedId, apiSeries.length])  // 只在切换指标或数据首次加载时检查

  // 日度数据
  useEffect(() => {
    if (!isDaily || (dimension !== 'daily' && dimension !== 'lastmonth') || !apiIdx) { setDailyData([]); return }
    let yr: number, mo: number
    if (dimension === 'daily') {
      const now = new Date(); yr = now.getFullYear(); mo = now.getMonth() + 1
    } else {
      const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1)
      yr = d.getFullYear(); mo = d.getMonth() + 1
    }
    getIndexDailyCalc(apiIdx.id, yr, mo)
      .then(setDailyData).catch(() => setDailyData([]))
  }, [isDaily, dimension, apiIdx])

  // 分项明细（月度维度 + 真实数据）
  useEffect(() => {
    if (isMock || dimension !== 'monthly' || !apiIdx) { setSubMetrics([]); return }
    const periods = prevMonths(24)
    const last    = periods[periods.length - 1]
    setSubLoading(true)
    getSubMetricDetail(apiIdx.id, last.year, last.month, 24)
      .then(d => setSubMetrics(d.sub_metrics))
      .catch(() => setSubMetrics([]))
      .finally(() => setSubLoading(false))
  }, [isMock, dimension, apiIdx])

  // ── 月度值查找表 ──
  const periods      = useMemo(() => prevMonths(24), [])
  const monthlyValues = useMemo((): (number | null)[] => {
    if (apiIdx && !isMock) return apiIdx.data.map(d => d.value)
    const juneTarget = MOCK_JUNE_TARGETS[selectedId] ?? 165
    const FY_START = 9
    const now = new Date()
    const curYM = `${now.getFullYear()}-${now.getMonth() + 1}`
    const iPos = idxPos  // 与 Dashboard INDICES.map((idx, i) => ...) 的 i 完全对齐
    return periods.map(({ year, month }) => {
      const key = `${year}-${month}`
      if (key === curYM) return null
      const fyPos  = ((month - FY_START + 12) % 12)
      const fyYear = month >= FY_START ? year : year - 1
      const seed   = (iPos + 1) * 7919 + fyYear * 31 + fyPos * 113
      return mockFYValue(seed, fyPos, juneTarget)
    })
  }, [selectedId, apiIdx, isMock, idxPos, periods])

  const valueByYM = useMemo(() => {
    const m: Record<string, number | null> = {}
    periods.forEach((p, i) => { m[`${p.year}-${p.month}`] = monthlyValues[i] ?? null })
    return m
  }, [periods, monthlyValues])

  function getValue(fy: FYKey, month: number): number | null {
    const sy   = fyStartYear(fy)
    const year = month >= 9 ? sy : sy + 1
    return valueByYM[`${year}-${month}`] ?? null
  }

  // ── 财年对比表格行 ──
  const fiscalRows = useMemo(() => {
    const rows = FY_MONTHS.map(m => {
      const cur  = selectedFYs.has('current')  ? getValue('current',  m) : undefined
      const prev = selectedFYs.has('previous') ? getValue('previous', m) : undefined
      const yoy  = (cur !== undefined && prev !== undefined) ? changePct(cur, prev) : undefined
      return { month: m, label: `${m}月`, current: cur, previous: prev, yoy }
    })
    return sortAsc ? rows : [...rows].reverse()
  }, [selectedFYs, valueByYM, sortAsc, currentFYStart])

  // ── 日度表格行 ──
  const dailyRows = useMemo(() => {
    const rows = dailyData.map((d, i) => ({
      label: d.date, value: d.value,
      dod: changePct(d.value, dailyData[i - 1]?.value ?? null),
    }))
    return sortAsc ? rows : [...rows].reverse()
  }, [dailyData, sortAsc])

  const showBoth = selectedFYs.has('current') && selectedFYs.has('previous')

  return (
    <div style={{ display: 'grid', gap: 20, width: '100%', minWidth: 0 }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: '#60a5fa', fontSize: 12, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>
            指数详情
          </div>
          <h2 style={{ margin: '0 0 4px', color: '#f1f5f9', fontWeight: 700, fontSize: 22, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {idxInfo.name}指数
            {isMock  && <span style={{ marginLeft: 8, fontSize: 12, color: '#6b7280', fontWeight: 400 }}>（模拟）</span>}
            {isDaily && !isMock && <span style={{ marginLeft: 8, fontSize: 12, color: '#4ade80', fontWeight: 400 }}>· 日度指标</span>}
          </h2>
        </div>

        {/* 控制栏 */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', flexShrink: 0 }}>
          {/* 维度 */}
          <div className="ind-range-btns">
            <button type="button" className={`ind-range-btn${dimension === 'daily'     ? ' active' : ''}`} onClick={() => setDimension('daily')}>本月</button>
            <button type="button" className={`ind-range-btn${dimension === 'lastmonth' ? ' active' : ''}`} onClick={() => setDimension('lastmonth')}>上月</button>
            <button type="button" className={`ind-range-btn${dimension === 'monthly'   ? ' active' : ''}`} onClick={() => setDimension('monthly')}>财年</button>
          </div>

          {/* 财年多选（仅财年模式） */}
          {dimension === 'monthly' && (
            <div className="ind-range-btns">
              {(['current', 'previous'] as FYKey[]).map(fy => (
                <button key={fy} type="button"
                  className={`ind-range-btn${selectedFYs.has(fy) ? ' active' : ''}`}
                  onClick={() => toggleFY(fy)}>
                  {fyLabel(fy)}
                </button>
              ))}
            </div>
          )}

          {/* 排序 */}
          <button type="button" className="ind-range-btn" onClick={() => setSortAsc(a => !a)}>
            {sortAsc ? '↑ 正序' : '↓ 倒序'}
          </button>
        </div>
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
              {hasReal && <span style={{ width: 4, height: 4, borderRadius: '50%', background: '#22c55e', flexShrink: 0 }} />}
              {isD      && <span style={{ fontSize: 10, color: '#60a5fa', fontWeight: 700 }}>日</span>}
            </button>
          )
        })}
      </div>

      {error && <div style={{ color: '#f87171', fontSize: 13 }}>{error}</div>}
      {loading && <div style={{ color: '#4b5563', fontSize: 13 }}>加载中…</div>}

      {/* ── 财年对比表 ── */}
      {dimension === 'monthly' && (
        <div className="ind-chart-panel" style={{ padding: '16px 20px', width: '100%', boxSizing: 'border-box' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12, flexWrap: 'wrap' }}>
            <span style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600 }}>财年指数明细</span>
            {showBoth && (
              <div style={{ display: 'flex', gap: 14 }}>
                {(['current', 'previous'] as FYKey[]).filter(f => selectedFYs.has(f)).map(f => (
                  <span key={f} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#8892a4' }}>
                    <span style={{ width: 14, height: 2, background: f === 'current' ? '#3b82f6' : '#f59e0b', borderRadius: 1, display: 'inline-block' }} />
                    {fyLabel(f)}
                  </span>
                ))}
              </div>
            )}
            {isMock && <span style={{ fontSize: 11, color: '#6b7280' }}>（模拟数据）</span>}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr>
                  <th style={{ ...TH, textAlign: 'left' }}>月份</th>
                  {selectedFYs.has('current') && (
                    <th style={{ ...TH, textAlign: 'right', color: '#60a5fa' }}>{fyLabel('current')}</th>
                  )}
                  {selectedFYs.has('previous') && (
                    <th style={{ ...TH, textAlign: 'right', color: '#f59e0b' }}>{fyLabel('previous')}</th>
                  )}
                  {showBoth && (
                    <th style={{ ...TH, textAlign: 'right' }}>同比</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {fiscalRows.map(row => {
                  const isCurrentMonth = (() => {
                    const now = new Date()
                    return row.month === now.getMonth() + 1
                  })()
                  return (
                    <tr key={row.month} style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      background: isCurrentMonth ? 'rgba(59,130,246,0.06)' : 'transparent',
                    }}>
                      <td style={{ padding: '9px 12px', color: isCurrentMonth ? '#60a5fa' : '#94a3b8', fontFamily: 'monospace', fontWeight: isCurrentMonth ? 600 : 400 }}>
                        {row.label}
                        {isCurrentMonth && <span style={{ marginLeft: 6, fontSize: 10, color: '#60a5fa' }}>▶ 本月</span>}
                      </td>
                      {selectedFYs.has('current') && (
                        <td style={{ padding: '9px 12px', textAlign: 'right', color: row.current == null ? '#374151' : '#f1f5f9', fontWeight: row.current != null ? 600 : 400 }}>
                          {fmtVal(row.current ?? null)}
                        </td>
                      )}
                      {selectedFYs.has('previous') && (
                        <td style={{ padding: '9px 12px', textAlign: 'right', color: row.previous == null ? '#374151' : '#94a3b8' }}>
                          {fmtVal(row.previous ?? null)}
                        </td>
                      )}
                      {showBoth && (
                        <td style={{ padding: '9px 12px', textAlign: 'right' }}>
                          {fmtChg(row.yoy ?? null)}
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── 日度数据表 ── */}
      {(dimension === 'daily' || dimension === 'lastmonth') && (
        <div className="ind-chart-panel" style={{ padding: '16px 20px', width: '100%', boxSizing: 'border-box' }}>
          <div style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>
            {dimension === 'daily' ? '本月' : '上月'}日度明细（{(() => {
              if (dimension === 'daily') {
                const now = new Date()
                return `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, '0')}`
              }
              const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1)
              return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}`
            })()}）
          </div>
          {dailyData.length === 0 ? (
            <div style={{ color: '#4b5563', textAlign: 'center', padding: '24px 0' }}>
              {isDaily ? '暂无本月日度数据' : '该指标为月度粒度，请在配置管理中将计算粒度改为「按日」'}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ ...TH, textAlign: 'left' }}>日期</th>
                    <th style={{ ...TH, textAlign: 'right' }}>指数值</th>
                    <th style={{ ...TH, textAlign: 'right' }}>日环比</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyRows.map(row => (
                    <tr key={row.label} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '9px 12px', color: '#94a3b8', fontFamily: 'monospace' }}>{row.label}</td>
                      <td style={{ padding: '9px 12px', textAlign: 'right', color: '#f1f5f9', fontWeight: 600 }}>
                        {fmtVal(row.value)}
                      </td>
                      <td style={{ padding: '9px 12px', textAlign: 'right' }}>{fmtChg(row.dod)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── 分项明细（仅财年模式） ── */}
      {dimension === 'monthly' && !isMock && (subMetrics.filter(sm => sm.data.some(d => d.value !== null)).length > 0 || subLoading) && (
        <div className="ind-chart-panel" style={{ padding: '16px 20px', width: '100%', boxSizing: 'border-box' }}>
          <div style={{ color: '#94a3b8', fontSize: 13, fontWeight: 600, marginBottom: 12 }}>分项数据明细（近24月）</div>
          {subLoading ? (
            <div style={{ color: '#4b5563', textAlign: 'center', padding: '20px 0' }}>加载中…</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr>
                    <th style={{ ...TH, textAlign: 'left', position: 'sticky', left: 0, background: '#141722', zIndex: 1 }}>分项</th>
                    <th style={{ ...TH }}>单位</th>
                    {(sortAsc ? periods : [...periods].reverse()).map(p => (
                      <th key={`${p.year}-${p.month}`} style={{ ...TH, textAlign: 'right' }}>{fmtPeriod(p.year, p.month)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {subMetrics.filter(sm => sm.data.some(d => d.value !== null)).map(sm => {
                    const orderedData = sortAsc ? sm.data : [...sm.data].reverse()
                    return (
                      <tr key={sm.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '9px 12px', color: '#e2e8f0', fontWeight: 500, position: 'sticky', left: 0, background: '#141722', whiteSpace: 'nowrap' }}>
                          {sm.name || sm.code}
                          <span style={{ marginLeft: 6, color: '#4b5563', fontSize: 11, fontFamily: 'monospace' }}>({sm.code})</span>
                        </td>
                        <td style={{ padding: '9px 12px', color: '#6b7280', whiteSpace: 'nowrap' }}>{sm.unit || '—'}</td>
                        {orderedData.map((d, i) => (
                          <td key={i} style={{ padding: '9px 12px', textAlign: 'right', color: d.value == null ? '#374151' : '#60a5fa', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                            {d.value == null ? '—' : d.value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
