import { useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getIndexCalc, getIndexDailyCalc } from '../services/api'
import type { IndexCalcSeries, DailyDataPoint } from '../services/api'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

// ── 指数定义 ──────────────────────────────────────────────────
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
type SelectedIndex = 'composite' | IndexId
type FYKey   = 'current' | 'previous'

function normalizeIndexId(value: string | null | undefined): SelectedIndex | null {
  if (value === 'composite') return 'composite'
  return INDICES.some(idx => idx.id === value) ? value as IndexId : null
}

function searchValue(name: string): string | null {
  const search = new URLSearchParams(window.location.search)
  const direct = search.get(name)
  if (direct) return direct

  const marker = window.location.hash.indexOf('?')
  if (marker < 0) return null
  return new URLSearchParams(window.location.hash.slice(marker + 1)).get(name)
}

function initialSelectedIndex(): SelectedIndex {
  return (
    normalizeIndexId(searchValue('index')) ||
    normalizeIndexId(searchValue('subEntityId')) ||
    'composite'
  )
}

// 每个财年 5 月的目标值（9月从 103 起线性增长，5月 fyPos=8 时达到目标值）
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

// 财年月份顺序
const FY_MONTHS = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]
const FY_X_DATA = FY_MONTHS.map(m => `${m}月`)

// 9月基准 103，5月（fyPos=8）精确等于目标值，其余月份含小幅噪声确保整体向上
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

// ── 多线图（支持虚线） ────────────────────────────────────────
type Series = { id: IndexId; name: string; color: string; data: (number | null)[]; dashed?: boolean; composite?: boolean }

function MultiLineChart({ xData, series }: { xData: string[]; series: Series[] }) {
  const divRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    if (!divRef.current) return
    chartRef.current = echarts.init(divRef.current, 'dark')
    const ro = new ResizeObserver(() => chartRef.current?.resize())
    ro.observe(divRef.current)
    return () => { ro.disconnect(); chartRef.current?.dispose(); chartRef.current = null }
  }, [])

  useEffect(() => {
    if (!chartRef.current) return
    const single = series.length === 1

    const allVals = series.flatMap(s => s.data.filter((v): v is number => v !== null))
    const minVal  = allVals.length ? Math.min(...allVals) : 0
    const maxVal  = allVals.length ? Math.max(...allVals) : 200
    const yMin = allVals.length ? Math.floor(minVal - 2) : undefined
    const yMax = allVals.length ? Math.ceil(maxVal + 2)  : undefined
    const compact = (divRef.current?.clientWidth ?? window.innerWidth) <= 520 || window.innerWidth <= 720
    const tooltipRows = compact ? 8 : 30

    chartRef.current.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        confine: true,
        backgroundColor: '#1e2130',
        borderColor: 'rgba(255,255,255,0.1)',
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        axisPointer: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
        extraCssText: compact
          ? 'max-width:260px;max-height:220px;overflow-y:auto;white-space:normal;'
          : 'max-width:520px;',
        formatter: (params: any[]) => {
          const active = params.filter(p => p.value != null)
          if (!active.length) return params[0]?.name ?? ''
          let s = `<div style="font-weight:600;color:#94a3b8;margin-bottom:5px">${params[0]?.name}</div>`
          active.slice(0, tooltipRows).forEach(p => {
            s += `<div style="display:flex;align-items:center;gap:8px;margin:2px 0">
              <span style="display:inline-block;width:14px;height:2px;background:${p.color};border-radius:1px;opacity:${p.data?.dashed?0.6:1}"></span>
              <span style="color:#cbd5e1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.seriesName}</span>
              <span style="font-weight:700;color:#fff;margin-left:auto;padding-left:16px">${Number(p.value).toFixed(2)}</span>
            </div>`
          })
          if (active.length > tooltipRows) {
            s += `<div style="margin-top:4px;color:#6b7280;font-size:11px">还有 ${active.length - tooltipRows} 项</div>`
          }
          return s
        },
      },
      legend: { show: false },
      grid: compact
        ? { top: 16, right: 8, bottom: 58, left: 8, containLabel: true }
        : { top: 20, right: 28, bottom: 52, left: 68 },
      xAxis: {
        type: 'category', data: xData,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisTick: { show: false },
        axisLabel: compact
          ? { color: '#6b7280', fontSize: 10, interval: 0, rotate: xData.length > 8 ? 32 : 0, hideOverlap: false }
          : { color: '#6b7280', fontSize: 11 },
      },
      yAxis: {
        type: 'value', name: '指数值',
        min: yMin,
        max: yMax,
        nameTextStyle: { color: '#6b7280', fontSize: 11, padding: compact ? [0, 0, 0, 0] : [0, 36, 0, 0] },
        axisLabel: { color: '#6b7280', fontSize: compact ? 10 : 11 },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLine: { show: false },
      },
      dataZoom: [{ type: 'inside' }],
      series: series.map(s => ({
        name: s.name,
        type: 'line',
        data: s.data,
        smooth: 0.25,
        connectNulls: false,
        symbol: single || s.composite ? 'circle' : 'none',
        symbolSize: s.composite ? 5 : 4,
        lineStyle: {
          color: s.color,
          width: s.composite ? 3 : single ? 2.5 : 1.8,
          type: s.dashed ? 'dashed' : 'solid',
          opacity: s.dashed ? 0.65 : 1,
        },
        itemStyle: { color: s.color, opacity: s.dashed ? 0.65 : 1 },
        areaStyle: single && !s.dashed ? {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: s.color + '2a' }, { offset: 1, color: s.color + '00' }] },
        } : undefined,
        z: s.composite ? 10 : 1,
      })),
    }, true)
  }, [xData, series])

  return <div ref={divRef} className="ind-chart-box" style={{ height: 440 }} />
}

// ── 页面 ──────────────────────────────────────────────────────
export default function IndicatorDashboard() {
  const [selectedId, setSelectedId]   = useState<SelectedIndex>(() => initialSelectedIndex())
  const [dimension, setDimension]     = useState<'monthly' | 'daily' | 'lastmonth'>('monthly')
  const [selectedFYs, setSelectedFYs] = useState<Set<FYKey>>(new Set<FYKey>(['current']))

  // API 数据
  const [realData, setRealData]   = useState<Record<string, (number | null)[]>>({})
  const [granMap, setGranMap]     = useState<Record<string, 'monthly' | 'daily'>>({})
  const [idMap, setIdMap]         = useState<Record<string, number>>({})
  const [dailyMap, setDailyMap]   = useState<Record<string, DailyDataPoint[]>>({})

  // 财年工具
  const currentFYStart = useMemo(() => {
    const now = new Date(), m = now.getMonth() + 1
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

  // 始终拉取 24 月（覆盖两个财年）
  useEffect(() => {
    let cancelled = false
    import('@microsoft/teams-js')
      .then(({ app }) => app.initialize().then(() => app.getContext()))
      .then(context => {
        const next = normalizeIndexId(context.page?.subPageId)
        if (!cancelled && next) setSelectedId(next)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const periods24 = useMemo(() => prevMonths(24), [])

  useEffect(() => {
    getIndexCalc(24)
      .then(result => {
        const data: Record<string, (number | null)[]> = {}
        const gran: Record<string, 'monthly' | 'daily'> = {}
        const ids:  Record<string, number> = {}
        for (const idx of result.indices) {
          const vals = idx.data.map((d: { value: number | null }) => d.value)
          if (vals.some((v: number | null) => v !== null)) data[idx.code] = vals
          gran[idx.code] = (idx as IndexCalcSeries).granularity ?? 'monthly'
          ids[idx.code]  = idx.id
        }
        setRealData(data); setGranMap(gran); setIdMap(ids)
      })
      .catch(() => {})
  }, [])

  // 日度数据
  useEffect(() => {
    if (dimension === 'monthly') { setDailyMap({}); return }
    let yr: number, mo: number
    if (dimension === 'daily') {
      const now = new Date(); yr = now.getFullYear(); mo = now.getMonth() + 1
    } else {
      const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1)
      yr = d.getFullYear(); mo = d.getMonth() + 1
    }
    const dailyIds = Object.entries(granMap)
      .filter(([, g]) => g === 'daily')
      .map(([code]) => ({ code, id: idMap[code] }))
      .filter(x => x.id != null)

    Promise.allSettled(
      dailyIds.map(({ code, id }) =>
        getIndexDailyCalc(id, yr, mo).then(pts => ({ code, pts }))
      )
    ).then(results => {
      const map: Record<string, DailyDataPoint[]> = {}
      for (const r of results)
        if (r.status === 'fulfilled') map[r.value.code] = r.value.pts
      setDailyMap(map)
    })
  }, [dimension, granMap, idMap])

  // 月度值查找表 (年月 → 值)
  const valueByYM = useMemo(() => {
    const buildMap = (id: IndexId, iPos: number): Record<string, number | null> => {
      const m: Record<string, number | null> = {}
      if (realData[id]) {
        periods24.forEach((p, i) => { m[`${p.year}-${p.month}`] = realData[id][i] ?? null })
      } else {
        const juneTarget = MOCK_JUNE_TARGETS[id] ?? 165
        const FY_START = 9
        const now = new Date()
        const curYM = `${now.getFullYear()}-${now.getMonth() + 1}`
        periods24.forEach(({ year, month }) => {
          const key = `${year}-${month}`
          if (key === curYM) { m[key] = null; return }  // 当月未完成，不显示
          const fyPos = ((month - FY_START + 12) % 12)
          const fyYear = month >= FY_START ? year : year - 1
          const seed = (iPos + 1) * 7919 + fyYear * 31 + fyPos * 113
          m[key] = mockFYValue(seed, fyPos, juneTarget)
        })
      }
      return m
    }
    return Object.fromEntries(INDICES.map((idx, i) => [idx.id, buildMap(idx.id, i)]))
  }, [realData, periods24])

  function getFYData(id: IndexId, fy: FYKey): (number | null)[] {
    const sy = fyStartYear(fy)
    const ym = valueByYM[id] ?? {}
    return FY_MONTHS.map(m => {
      const year = m >= 9 ? sy : sy + 1
      return ym[`${year}-${m}`] ?? null
    })
  }

  const isComposite  = selectedId === 'composite'
  const showBothFY   = selectedFYs.size > 1
  const isDailyDim   = dimension === 'daily' || dimension === 'lastmonth'

  // 日度数据只需拉所有日度指标
  const dailyXData = useMemo(() => {
    const dates = new Set<string>()
    INDICES.forEach(idx => {
      if (granMap[idx.id] === 'daily') (dailyMap[idx.id] ?? []).forEach(d => dates.add(d.date))
    })
    return [...dates].sort()
  }, [dailyMap, granMap])

  // ── 全部子指数 series（用于子指数图和综合计算）──
  const allFiscalSeries: Series[] = useMemo(() => {
    const result: Series[] = []
    for (const idx of INDICES) {
      for (const fy of (['current', 'previous'] as FYKey[])) {
        if (!selectedFYs.has(fy)) continue
        result.push({
          id: idx.id, name: idx.name, color: idx.color,
          data: getFYData(idx.id, fy),
          dashed: fy === 'previous',
        })
      }
    }
    return result
  }, [selectedFYs, valueByYM, currentFYStart])

  const allDailySeries: Series[] = useMemo(() => {
    return INDICES
      .filter(idx => granMap[idx.id] === 'daily' && dailyMap[idx.id]?.length)
      .map(idx => {
        const pts = dailyMap[idx.id]
        const dateMap = Object.fromEntries(pts.map(p => [p.date, p.value]))
        return { id: idx.id, name: idx.name, color: idx.color, data: dailyXData.map(d => dateMap[d] ?? null) }
      })
  }, [dailyMap, dailyXData, granMap])

  const allSubSeries = isDailyDim ? allDailySeries : allFiscalSeries

  // ── 综合指数 series（allSubSeries 的各期均值）──
  const compositeSeries: Series[] = useMemo(() => {
    if (allSubSeries.length === 0) return []
    const groups = [false, true].map(d => allSubSeries.filter(s => !!s.dashed === d))
    return groups.filter(g => g.length > 0).map(g => {
      const dashed = !!g[0].dashed
      const data = g[0].data.map((_, i) => {
        const vals = g.map(s => s.data[i]).filter((v): v is number => v !== null)
        return vals.length > 0 ? Math.round(vals.reduce((a, b) => a + b, 0) * 100) / 100 : null
      })
      const label = showBothFY
        ? `92综合指数 ${dashed ? fyLabel('previous') : fyLabel('current')}`
        : '92综合指数'
      return { id: 'composite' as IndexId, name: label, color: '#f8fafc', data, dashed, composite: true }
    })
  }, [allSubSeries, showBothFY])

  // ── 单指标 series ──
  const singleSeries: Series[] = useMemo(() => {
    if (isComposite) return []
    const idx = INDICES.find(i => i.id === selectedId)!
    if (isDailyDim) {
      const pts = dailyMap[selectedId as IndexId]
      if (!pts?.length) return []
      const dateMap = Object.fromEntries(pts.map(p => [p.date, p.value]))
      return [{ id: idx.id, name: idx.name, color: idx.color, data: dailyXData.map(d => dateMap[d] ?? null) }]
    }
    return (['current', 'previous'] as FYKey[])
      .filter(fy => selectedFYs.has(fy))
      .map(fy => ({
        id: idx.id, name: showBothFY ? `${idx.name} ${fyLabel(fy)}` : idx.name,
        color: idx.color, data: getFYData(idx.id, fy), dashed: fy === 'previous',
      }))
  }, [isComposite, selectedId, isDailyDim, dailyMap, dailyXData, selectedFYs, valueByYM, showBothFY])

  const currentXData = isDailyDim ? dailyXData : FY_X_DATA

  // ── 卡片数据生成 ──
  function makeCardData(seriesList: Series[]) {
    return seriesList.filter(s => s.data.some(v => v !== null)).map(s => {
      let li = -1, pi = -1
      for (let i = s.data.length - 1; i >= 0; i--) {
        if (s.data[i] !== null) { if (li === -1) li = i; else if (pi === -1) { pi = i; break } }
      }
      const lv = li >= 0 ? s.data[li] as number : null
      const pv = pi >= 0 ? s.data[pi] as number : null
      const delta = lv !== null && pv !== null ? lv - pv : null
      const pct   = delta !== null && pv !== null && pv !== 0 ? (delta / Math.abs(pv)) * 100 : null
      return { id: s.id, name: s.name, color: s.color, dashed: s.dashed, composite: s.composite,
               latestVal: lv, latestDate: li >= 0 ? currentXData[li] : null,
               prevDate:  pi >= 0 ? currentXData[pi] : null, delta, pct }
    })
  }

  const compositeCardData = useMemo(() => makeCardData(compositeSeries), [compositeSeries, currentXData])
  const subCardData       = useMemo(() => makeCardData(allSubSeries.filter(s => !s.dashed)), [allSubSeries, currentXData])
  const singleCardData    = useMemo(() => makeCardData(singleSeries), [singleSeries, currentXData])

  const dailyMonthLabel = useMemo(() => {
    if (dimension === 'daily') {
      const now = new Date()
      return `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, '0')}`
    }
    const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 1)
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}`
  }, [dimension])

  // ── 卡片渲染组件 ──
  function renderCard(c: ReturnType<typeof makeCardData>[0], large = false) {
    if (large) {
      const deltaColor = c.delta !== null && c.delta >= 0 ? '#4ade80' : '#f87171'
      return (
        <div className="ind-summary-card" style={{
          background: 'linear-gradient(135deg,#1e2130,#232840)',
          borderRadius: 10, padding: '14px 24px',
          border: '1px solid rgba(255,255,255,0.08)',
          borderLeft: '4px solid rgba(255,255,255,0.3)',
          display: 'flex', alignItems: 'center', gap: 20, whiteSpace: 'nowrap',
        }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ffffff', flexShrink: 0 }} />
          <span style={{ fontSize: 22, fontWeight: 700, color: '#ffffff' }}>{c.name}</span>
          <span style={{ fontSize: 14, color: '#94a3b8' }}>{c.latestDate ?? '—'}</span>
          <span style={{ fontSize: 30, fontWeight: 700, color: '#ffffff', lineHeight: 1 }}>
            {c.latestVal !== null ? c.latestVal.toFixed(2) : '—'}
          </span>
          {c.prevDate && <span style={{ fontSize: 13, color: '#94a3b8', marginLeft: 60 }}>vs {c.prevDate}</span>}
          {c.delta !== null && (
            <span style={{ fontSize: 16, fontWeight: 600, color: deltaColor }}>
              {c.delta >= 0 ? '▲' : '▼'}{Math.abs(c.delta).toFixed(2)}
            </span>
          )}
          {c.pct !== null && (
            <span style={{ fontSize: 14, color: deltaColor }}>
              {c.pct >= 0 ? '+' : ''}{c.pct.toFixed(2)}%
            </span>
          )}
        </div>
      )
    }
    return (
      <div className="ind-compact-card" style={{
        background: '#1a1d2a', borderRadius: 10, padding: '10px 14px',
        border: `1px solid ${c.color}30`,
        borderLeft: `3px solid ${c.color}${c.dashed ? '80' : 'cc'}`,
        display: 'flex', alignItems: 'center', gap: 12, minWidth: 0,
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 3, display: 'flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.color, flexShrink: 0 }} />
            {c.name}
            {c.dashed && <span style={{ fontSize: 10, color: '#4b5563' }}>上期</span>}
          </div>
          <div style={{ fontSize: 10, color: '#4b5563' }}>{c.latestDate ?? '—'}</div>
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', lineHeight: 1, flexShrink: 0 }}>
          {c.latestVal !== null ? c.latestVal.toFixed(2) : '—'}
        </div>
        {c.delta !== null && c.pct !== null ? (
          <div style={{ marginLeft: 'auto', textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: c.delta >= 0 ? '#4ade80' : '#f87171', whiteSpace: 'nowrap' }}>
              {c.delta >= 0 ? '▲' : '▼'}{Math.abs(c.delta).toFixed(2)}
            </div>
            <div style={{ fontSize: 11, color: c.delta >= 0 ? '#4ade80' : '#f87171', whiteSpace: 'nowrap' }}>
              {c.delta >= 0 ? '+' : ''}{c.pct.toFixed(2)}%
            </div>
            {c.prevDate && <div style={{ fontSize: 10, color: '#374151' }}>vs {c.prevDate}</div>}
          </div>
        ) : (
          <div style={{ marginLeft: 'auto', fontSize: 11, color: '#374151' }}>—</div>
        )}
      </div>
    )
  }

  function renderLegend(seriesList: Series[]) {
    if (seriesList.length <= 1) return null
    return (
      <div className="ind-legend" style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        {seriesList.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#8892a4' }}>
            <span style={{ display: 'inline-block', width: 18, height: 2, borderRadius: s.dashed ? 0 : 1,
              background: s.dashed ? 'none' : s.color, borderTop: s.dashed ? `2px dashed ${s.color}` : 'none', opacity: s.dashed ? 0.65 : 1 }} />
            {s.name}
          </div>
        ))}
      </div>
    )
  }

  const dimHint = isDailyDim
    ? <div style={{ fontSize: 12, color: '#6b7280' }}>{dimension === 'daily' ? '本月' : '上月'}（{dailyMonthLabel}）按日数据，仅标注「<span style={{ color: '#60a5fa', fontWeight: 700 }}>日</span>」的指标有当日曲线</div>
    : showBothFY
      ? <div style={{ display: 'flex', gap: 20, fontSize: 12, color: '#6b7280' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ display: 'inline-block', width: 18, height: 2, background: '#94a3b8', borderRadius: 1 }} />实线 = {fyLabel('current')}</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ display: 'inline-block', width: 18, height: 2, background: 'none', borderTop: '2px dashed #94a3b8', opacity: 0.5 }} />虚线 = {fyLabel('previous')}</span>
        </div>
      : null

  return (
    <div className="ind-dashboard-grid" style={{ display: 'grid', gap: 20, width: '100%', minWidth: 0 }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ color: '#60a5fa', fontSize: 12, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>经营指数</div>
          <h2 style={{ margin: '0 0 4px', color: '#f1f5f9', fontWeight: 700, fontSize: 22 }}>指数趋势总览</h2>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="ind-range-btns">
            <button type="button" className={`ind-range-btn${dimension === 'daily'     ? ' active' : ''}`} onClick={() => setDimension('daily')}>本月</button>
            <button type="button" className={`ind-range-btn${dimension === 'lastmonth' ? ' active' : ''}`} onClick={() => setDimension('lastmonth')}>上月</button>
            <button type="button" className={`ind-range-btn${dimension === 'monthly'   ? ' active' : ''}`} onClick={() => setDimension('monthly')}>财年</button>
          </div>
          {dimension === 'monthly' && (
            <div className="ind-range-btns">
              {(['current', 'previous'] as FYKey[]).map(fy => (
                <button key={fy} type="button" className={`ind-range-btn${selectedFYs.has(fy) ? ' active' : ''}`} onClick={() => toggleFY(fy)}>{fyLabel(fy)}</button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── 单选选择器 ── */}
      <div className="ind-index-chip-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
        {/* 92综合指数 */}
        <button type="button" onClick={() => setSelectedId('composite')} style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '6px 16px', borderRadius: 20, border: '1px solid', fontSize: 14, cursor: 'pointer', transition: 'all 0.15s',
          background:  isComposite ? 'rgba(248,250,252,0.12)' : 'rgba(255,255,255,0.04)',
          borderColor: isComposite ? 'rgba(248,250,252,0.4)'  : 'rgba(255,255,255,0.1)',
          color:       isComposite ? '#f8fafc' : '#6b7280', fontWeight: isComposite ? 700 : 400,
        }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: isComposite ? '#f8fafc' : '#374151', flexShrink: 0 }} />
          92综合指数
        </button>

        {INDICES.map(idx => {
          const on      = selectedId === idx.id
          const isDaily = granMap[idx.id] === 'daily'
          return (
            <button key={idx.id} type="button" onClick={() => setSelectedId(idx.id)} style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '6px 15px', borderRadius: 20, border: '1px solid', fontSize: 14, cursor: 'pointer', transition: 'all 0.15s',
              background:  on ? idx.color + '20' : 'rgba(255,255,255,0.04)',
              borderColor: on ? idx.color + '80' : 'rgba(255,255,255,0.1)',
              color:       on ? '#f1f5f9' : '#6b7280', fontWeight: on ? 600 : 400,
            }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: on ? idx.color : '#374151', flexShrink: 0 }} />
              {idx.name}
              {isDaily && <span style={{ fontSize: 10, color: '#60a5fa', fontWeight: 700 }}>日</span>}
            </button>
          )
        })}
      </div>

      {dimHint}

      {isComposite ? (
        <>
          {/* ── 综合指数卡片 ── */}
          {compositeCardData.length > 0 && renderCard(compositeCardData[0], true)}

          {/* ── 综合指数折线图 ── */}
          <div className="ind-chart-panel" style={{ padding: '20px 20px 14px' }}>
            <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 600, marginBottom: 8 }}>92综合指数走势</div>
            {compositeSeries.length === 0
              ? <div style={{ textAlign: 'center', color: '#374151', padding: '60px 0' }}>暂无数据</div>
              : <MultiLineChart xData={currentXData} series={compositeSeries} />}
          </div>
          {renderLegend(compositeSeries)}

          {/* ── 13个子指数卡片 ── */}
          {subCardData.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
              {subCardData.map((c, i) => <div key={i}>{renderCard(c, false)}</div>)}
            </div>
          )}

          {/* ── 13个子指数折线图 ── */}
          <div className="ind-chart-panel" style={{ padding: '20px 20px 14px' }}>
            <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 600, marginBottom: 8 }}>各子指数走势</div>
            {allSubSeries.length === 0
              ? <div style={{ textAlign: 'center', color: '#374151', padding: '60px 0' }}>暂无数据</div>
              : <MultiLineChart xData={currentXData} series={allSubSeries} />}
          </div>
          {renderLegend(allSubSeries)}
        </>
      ) : (
        <>
          {/* ── 单指标卡片 ── */}
          {singleCardData.length > 0 && renderCard(singleCardData[0], true)}

          {/* ── 单指标折线图 ── */}
          <div className="ind-chart-panel" style={{ padding: '20px 20px 14px' }}>
            {singleSeries.length === 0
              ? <div style={{ textAlign: 'center', color: '#374151', padding: '80px 0' }}>
                  {isDailyDim ? '该指标暂无日度数据（需配置粒度为「按日」）' : '暂无数据'}
                </div>
              : <MultiLineChart xData={currentXData} series={singleSeries} />}
          </div>
          {renderLegend(singleSeries)}
        </>
      )}
    </div>
  )
}
