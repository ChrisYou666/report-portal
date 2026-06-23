import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent, TitleComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getIndexCalc, getSubMetricDetail } from '../services/api'
import type { IndexCalcResult, IndexCalcSeries, SubMetricTimeSeries } from '../services/api'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, CanvasRenderer])

const COLORS = ['#0d9488', '#38bdf8', '#fb923c', '#a78bfa', '#34d399', '#f472b6', '#facc15', '#60a5fa']

function fmtPeriod(year: number, month: number) {
  return `${year}/${String(month).padStart(2, '0')}`
}

function fmtVal(v: number | null | undefined, decimals = 1) {
  if (v == null) return '—'
  return v.toLocaleString('zh-CN', { maximumFractionDigits: decimals })
}

function mom(data: { value: number | null }[]) {
  if (data.length < 2) return null
  const cur = data[data.length - 1].value
  const prev = data[data.length - 2].value
  if (cur == null || prev == null || prev === 0) return null
  return ((cur - prev) / Math.abs(prev)) * 100
}

function useChart(ref: React.RefObject<HTMLDivElement | null>) {
  const chartRef = useRef<echarts.ECharts | null>(null)
  useEffect(() => {
    if (!ref.current) return
    chartRef.current = echarts.init(ref.current)
    const ro = new ResizeObserver(() => chartRef.current?.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [ref])
  return chartRef
}

// ── Main composite chart ──────────────────────────────────────
function CompositeChart({ data, label }: { data: { year: number; month: number; value: number | null }[]; label: string }) {
  const divRef = useRef<HTMLDivElement>(null)
  const chartRef = useChart(divRef)

  useEffect(() => {
    if (!chartRef.current) return
    const xData = data.map(d => fmtPeriod(d.year, d.month))
    const yData = data.map(d => d.value)
    chartRef.current.setOption({
      tooltip: { trigger: 'axis', formatter: (p: any) => `${p[0].name}<br/>${label}：${fmtVal(p[0].value, 2)}` },
      grid: { top: 20, right: 24, bottom: 36, left: 56 },
      xAxis: { type: 'category', data: xData, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b', fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11 }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
      series: [{
        name: label,
        type: 'line',
        data: yData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: '#0d9488', width: 2.5 },
        itemStyle: { color: '#0d9488' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(13,148,136,0.18)' }, { offset: 1, color: 'rgba(13,148,136,0)' }] } },
      }],
    })
  }, [data, label, chartRef])

  return <div ref={divRef} style={{ height: 220 }} />
}

// ── Multi-line index chart ────────────────────────────────────
function MultiIndexChart({ indices }: { indices: IndexCalcSeries[] }) {
  const divRef = useRef<HTMLDivElement>(null)
  const chartRef = useChart(divRef)

  useEffect(() => {
    if (!chartRef.current || indices.length === 0) return
    const allPeriods = indices[0].data.map(d => fmtPeriod(d.year, d.month))
    chartRef.current.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 11 } },
      grid: { top: 12, right: 16, bottom: 48, left: 48 },
      xAxis: { type: 'category', data: allPeriods, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b', fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11 }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
      series: indices.map((idx, i) => ({
        name: idx.name,
        type: 'line',
        data: idx.data.map(d => d.value),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: COLORS[i % COLORS.length], width: 2 },
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    })
  }, [indices, chartRef])

  return <div ref={divRef} style={{ height: 240 }} />
}

// ── Sub-metric drill-down chart ───────────────────────────────
function SubMetricChart({ series, indexName }: { series: SubMetricTimeSeries[]; indexName: string }) {
  const divRef = useRef<HTMLDivElement>(null)
  const chartRef = useChart(divRef)

  useEffect(() => {
    if (!chartRef.current || series.length === 0) return
    const allPeriods = series[0].data.map(d => fmtPeriod(d.year, d.month))
    chartRef.current.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 11 } },
      grid: { top: 12, right: 16, bottom: 48, left: 52 },
      xAxis: { type: 'category', data: allPeriods, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b', fontSize: 10 } },
      yAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 11 }, splitLine: { lineStyle: { color: '#f1f5f9' } } },
      series: series.map((sm, i) => ({
        name: sm.name || sm.code,
        type: 'bar',
        data: sm.data.map(d => d.value),
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    })
  }, [series, chartRef])

  return (
    <div className="analysis-panel" style={{ marginTop: 16 }}>
      <div className="panel-title">
        <h2 style={{ fontSize: 15 }}>{indexName} — 分项明细</h2>
      </div>
      <div ref={divRef} style={{ height: 220 }} />
    </div>
  )
}

// ── KPI card ──────────────────────────────────────────────────
function IndexCard({
  idx, onClick, active,
}: {
  idx: IndexCalcSeries
  onClick: () => void
  active: boolean
}) {
  const latest = idx.data[idx.data.length - 1]?.value ?? null
  const change = mom(idx.data)
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        background: active ? 'rgba(13,148,136,0.08)' : '#fff',
        border: `1px solid ${active ? '#0d9488' : '#dbe5f0'}`,
        borderRadius: 8,
        padding: '14px 16px',
        textAlign: 'left',
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
    >
      <div style={{ color: '#64748b', fontSize: 12, marginBottom: 6 }}>{idx.name}</div>
      <div style={{ color: '#0f172a', fontSize: 24, fontWeight: 750, lineHeight: 1 }}>
        {fmtVal(latest, 2)}
      </div>
      {change != null && (
        <div style={{ marginTop: 6, fontSize: 12, color: change >= 0 ? '#0d9488' : '#dc2626' }}>
          {change >= 0 ? '▲' : '▼'} {Math.abs(change).toFixed(1)}%
          <span style={{ color: '#94a3b8', marginLeft: 4 }}>环比</span>
        </div>
      )}
    </button>
  )
}

// ── Page ──────────────────────────────────────────────────────
export default function IndexDashboardPage() {
  const [result, setResult] = useState<IndexCalcResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [months, setMonths] = useState(12)
  const [drillIndex, setDrillIndex] = useState<IndexCalcSeries | null>(null)
  const [drillData, setDrillData] = useState<{ index_name: string; sub_metrics: SubMetricTimeSeries[] } | null>(null)
  const [drillLoading, setDrillLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    setDrillIndex(null)
    setDrillData(null)
    getIndexCalc(months)
      .then(setResult)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [months])

  async function handleDrill(idx: IndexCalcSeries) {
    if (drillIndex?.id === idx.id) {
      setDrillIndex(null)
      setDrillData(null)
      return
    }
    setDrillIndex(idx)
    setDrillData(null)
    setDrillLoading(true)
    const last = idx.data[idx.data.length - 1]
    if (!last) { setDrillLoading(false); return }
    try {
      const d = await getSubMetricDetail(idx.id, last.year, last.month, months)
      setDrillData(d)
    } finally {
      setDrillLoading(false)
    }
  }

  const compositeLatest = result?.composite.data[result.composite.data.length - 1]?.value ?? null
  const compositeChange = result ? mom(result.composite.data) : null

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 1200 }}>
      {/* Header */}
      <div className="portal-hero">
        <div>
          <p className="page-eyebrow">经营指数</p>
          <h1 style={{ margin: '6px 0 6px', fontSize: 24, fontWeight: 700, color: '#0f172a' }}>
            {result?.composite.label ?? '综合指数'}
          </h1>
          <p className="page-desc">各项经营指数按月度综合评分</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#64748b', fontSize: 13 }}>显示近</span>
          {[6, 12, 24].map(n => (
            <button
              key={n}
              type="button"
              className={`btn-ghost${months === n ? ' active' : ''}`}
              style={months === n ? { background: '#0f766e', color: '#fff', border: '1px solid #0f766e' } : {}}
              onClick={() => setMonths(n)}
            >
              {n} 个月
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="empty-state">加载中…</div>}
      {error && <div className="form-error">{error}</div>}

      {result && !loading && (
        <>
          {/* Composite KPI + chart */}
          <div className="data-card" style={{ padding: '20px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 16 }}>
              <div>
                <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>{result.composite.label}</div>
                <div style={{ fontSize: 36, fontWeight: 750, color: '#0f172a', lineHeight: 1 }}>
                  {fmtVal(compositeLatest, 2)}
                </div>
                {compositeChange != null && (
                  <div style={{ marginTop: 6, fontSize: 13, color: compositeChange >= 0 ? '#0d9488' : '#dc2626' }}>
                    {compositeChange >= 0 ? '▲' : '▼'} {Math.abs(compositeChange).toFixed(1)}% 环比
                  </div>
                )}
              </div>
              {result.composite.formula && (
                <div style={{ fontSize: 11, color: '#94a3b8', maxWidth: 320, textAlign: 'right', wordBreak: 'break-all' }}>
                  公式：{result.composite.formula}
                </div>
              )}
            </div>
            <CompositeChart data={result.composite.data} label={result.composite.label} />
          </div>

          {/* Sub-index cards */}
          {result.indices.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 10 }}>
              {result.indices.map(idx => (
                <IndexCard
                  key={idx.id}
                  idx={idx}
                  active={drillIndex?.id === idx.id}
                  onClick={() => handleDrill(idx)}
                />
              ))}
            </div>
          )}

          {/* Drill-down */}
          {drillLoading && <div className="empty-state">加载分项数据…</div>}
          {drillData && !drillLoading && (
            <SubMetricChart series={drillData.sub_metrics} indexName={drillData.index_name} />
          )}

          {/* Multi-index trend */}
          {result.indices.length > 0 && (
            <div className="analysis-panel">
              <div className="panel-title">
                <h2 style={{ fontSize: 15 }}>各指数趋势</h2>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>点击上方卡片查看分项明细</span>
              </div>
              <MultiIndexChart indices={result.indices} />
            </div>
          )}

          {result.indices.length === 0 && (
            <div className="empty-state">尚未配置任何指标，请前往「指标管理」添加</div>
          )}
        </>
      )}
    </div>
  )
}
