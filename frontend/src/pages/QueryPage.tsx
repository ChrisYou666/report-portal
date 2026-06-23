import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getMetricAnalysis, getMetricDimensions } from '../services/api'
import type { MetricAnalysisQuery, MetricAnalysisResponse, MetricAnalysisRow, MetricDimensionOptions } from '../services/api'
import { useI18n } from '../i18n'

const defaultQuery: MetricAnalysisQuery = {
  subject: 'production_monitoring',
  metric: 'actual_today_ton',
  periodType: 'day',
  groupBy: 'division',
  startDate: '',
  endDate: '',
  site: '',
  division: '',
  blok: '',
  workerType: '',
}

const emptyDimensions: MetricDimensionOptions = {
  sites: [],
  divisions: [],
  bloks: [],
  worker_types: [],
}

function QueryPage() {
  const { t } = useI18n()
  const [query, setQuery] = useState<MetricAnalysisQuery>(defaultQuery)
  const [dimensions, setDimensions] = useState<MetricDimensionOptions>(emptyDimensions)
  const [analysis, setAnalysis] = useState<MetricAnalysisResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    async function loadDimensions() {
      try {
        setDimensions(await getMetricDimensions())
      } catch (currentError) {
        setError(currentError instanceof Error ? currentError.message : t.query.loadFailed)
      }
    }

    loadDimensions()
  }, [t.query.loadFailed])

  useEffect(() => {
    async function loadAnalysis() {
      try {
        setLoading(true)
        setError('')
        setAnalysis(await getMetricAnalysis(query))
      } catch (currentError) {
        setError(currentError instanceof Error ? currentError.message : t.query.loadFailed)
      } finally {
        setLoading(false)
      }
    }

    loadAnalysis()
  }, [query, t.query.loadFailed])

  const metricOptions = query.subject === 'attendance' ? attendanceMetrics : query.subject === 'akp_density' ? akpMetrics : productionMetrics
  const groupOptions = query.subject === 'attendance' ? attendanceGroups : query.subject === 'akp_density' ? akpGroups : productionGroups
  const rows = analysis?.rows ?? []
  const maxTrend = useMemo(() => Math.max(...(analysis?.trends.map((item) => item.value) ?? [0]), 0), [analysis])
  const tableColumns = useMemo(() => buildTableColumns(query, t.query), [query, t.query])

  function updateQuery<K extends keyof MetricAnalysisQuery>(key: K, value: MetricAnalysisQuery[K]) {
    setQuery((current) => {
      const next = { ...current, [key]: value }
      if (key === 'subject') {
        if (value === 'attendance') {
          next.metric = 'attendance_rate'
          next.groupBy = 'worker_type'
        } else if (value === 'akp_density') {
          next.metric = 'panen_kg'
          next.groupBy = 'division'
        } else {
          next.metric = 'actual_today_ton'
          next.groupBy = 'division'
        }
        next.division = ''
        next.blok = ''
        next.workerType = ''
      }
      return next
    })
  }

  return (
    <section className="portal-page">
      <header className="section-header">
        <div>
          <span>{t.query.eyebrow}</span>
          <h1>{t.query.title}</h1>
          <p>{t.query.description}</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}

      <div className="query-toolbar analysis-toolbar">
        <label className="field">
          <span>{t.query.subject}</span>
          <select value={query.subject} onChange={(event) => updateQuery('subject', event.target.value)}>
            <option value="production_monitoring">{t.query.subjects.production_monitoring}</option>
            <option value="akp_density">{t.query.subjects.akp_density}</option>
            <option value="attendance">{t.query.subjects.attendance}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.query.metric}</span>
          <select value={query.metric} onChange={(event) => updateQuery('metric', event.target.value)}>
            {metricOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {t.query.metrics[item.value] ?? item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t.query.periodType}</span>
          <select value={query.periodType} onChange={(event) => updateQuery('periodType', event.target.value)}>
            <option value="day">{t.query.periods.day}</option>
            <option value="week">{t.query.periods.week}</option>
            <option value="month">{t.query.periods.month}</option>
          </select>
        </label>
        <label className="field">
          <span>{t.query.groupBy}</span>
          <select value={query.groupBy} onChange={(event) => updateQuery('groupBy', event.target.value)}>
            {groupOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {t.query.groups[item.value] ?? item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t.query.startDate}</span>
          <input type="date" value={query.startDate} onChange={(event) => updateQuery('startDate', event.target.value)} />
        </label>
        <label className="field">
          <span>{t.query.endDate}</span>
          <input type="date" value={query.endDate} onChange={(event) => updateQuery('endDate', event.target.value)} />
        </label>
        <label className="field">
          <span>{t.query.site}</span>
          <select value={query.site} onChange={(event) => updateQuery('site', event.target.value)}>
            <option value="">{t.query.allSites}</option>
            {dimensions.sites.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        {(query.subject === 'akp_density' || query.subject === 'production_monitoring') && (
          <label className="field">
            <span>{t.query.division}</span>
            <select value={query.division} onChange={(event) => updateQuery('division', event.target.value)}>
              <option value="">{t.query.allDivisions}</option>
              {dimensions.divisions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        )}
        {query.subject === 'akp_density' && (
          <label className="field">
            <span>Blok</span>
            <select value={query.blok} onChange={(event) => updateQuery('blok', event.target.value)}>
              <option value="">{t.query.allBloks}</option>
              {dimensions.bloks.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        )}
        {query.subject === 'attendance' && (
          <label className="field">
            <span>{t.query.workerType}</span>
            <select value={query.workerType} onChange={(event) => updateQuery('workerType', event.target.value)}>
              <option value="">{t.query.allWorkerTypes}</option>
              {dimensions.worker_types.map((item) => (
                <option key={item} value={item}>
                  {t.query.workerTypes[item] ?? item}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="metric-grid">
        {(analysis?.cards ?? []).map((card) => (
          <div className="metric-card" key={card.label}>
            <span>{card.label}</span>
            <strong>
              {card.value}
              {card.unit && <small> {card.unit}</small>}
            </strong>
          </div>
        ))}
      </div>

      <div className="analysis-panel">
        <div className="panel-title">
          <h2>{t.query.trend}</h2>
          {loading && <span>{t.common.loading}</span>}
        </div>
        <div className="trend-list">
          {(analysis?.trends ?? []).map((point) => (
            <div className="trend-row" key={point.period}>
              <span>{point.period}</span>
              <div>
                <i style={{ width: `${maxTrend ? Math.max((point.value / maxTrend) * 100, 2) : 0}%` }} />
              </div>
              <strong>{formatNumber(point.value)}</strong>
            </div>
          ))}
          {analysis?.trends.length === 0 && <div className="empty-state">{t.query.empty}</div>}
        </div>
      </div>

      <div className="table-panel">
        <table>
          <thead>
            <tr>
              {tableColumns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.dimension}-${row.metric_value}`}>
                {tableColumns.map((column) => (
                  <td key={column.key}>{column.render(row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="empty-state">{t.query.empty}</div>}
      </div>
    </section>
  )
}

const productionMetrics = [
  { value: 'actual_today_ton', label: '当日产量(吨)' },
  { value: 'actual_to_date_ton', label: '月累计(吨)' },
  { value: 'bbc_ton', label: '月目标BBC(吨)' },
  { value: 'daily_target_ton', label: '日目标(吨)' },
  { value: 'actual_vs_bbc_percent', label: '完成率%' },
]

const productionGroups = [
  { value: 'company', label: '全公司' },
  { value: 'site', label: '园区' },
  { value: 'division', label: '小区' },
]

const akpMetrics = [
  { value: 'panen_kg', label: 'Panen Kg' },
  { value: 'jumlah_janjang', label: 'Janjang' },
  { value: 'akp_percent', label: 'AKP%' },
  { value: 'luas_ha', label: 'Luas Ha' },
]

const attendanceMetrics = [
  { value: 'attendance_rate', label: '出勤率' },
  { value: 'present_workers', label: '出勤人数' },
  { value: 'actual_workers', label: '实际人数' },
]

const akpGroups = [
  { value: 'company', label: '全公司' },
  { value: 'site', label: '园区' },
  { value: 'division', label: '小区' },
  { value: 'blok', label: 'Blok' },
]

const attendanceGroups = [
  { value: 'company', label: '全公司' },
  { value: 'site', label: '园区' },
  { value: 'worker_type', label: '人员类型' },
  { value: 'afdeling', label: '小区' },
]

type QueryLabels = ReturnType<typeof useI18n>['t']['query']
type TableColumn = {
  key: string
  label: string
  render: (row: MetricAnalysisRow) => ReactNode
}

function buildTableColumns(query: MetricAnalysisQuery, labels: QueryLabels): TableColumn[] {
  const selectedMetricLabel = labels.metrics[query.metric] ?? labels.selectedMetric
  const selectedMetricColumn: TableColumn = {
    key: 'selected_metric',
    label: selectedMetricLabel,
    render: (row) => (
      <>
        <strong>{formatNumber(row.metric_value)}</strong> {row.unit}
      </>
    ),
  }
  const contextColumns =
    query.subject === 'attendance'
      ? buildAttendanceColumns(labels)
      : query.subject === 'akp_density'
        ? buildAkpColumns()
        : buildProductionColumns(labels)
  return [
    {
      key: 'dimension',
      label: labels.dimension,
      render: (row) => row.dimension,
    },
    selectedMetricColumn,
    ...contextColumns.filter((column) => column.key !== query.metric),
  ]
}

function buildProductionColumns(labels: QueryLabels): TableColumn[] {
  return [
    { key: 'actual_today_ton', label: labels.metrics['actual_today_ton'] ?? '当日产量', render: (row) => formatNullable(row.actual_today_ton) },
    { key: 'actual_to_date_ton', label: labels.metrics['actual_to_date_ton'] ?? '月累计', render: (row) => formatNullable(row.actual_to_date_ton) },
    { key: 'bbc_ton', label: labels.metrics['bbc_ton'] ?? '月目标', render: (row) => formatNullable(row.bbc_ton) },
    { key: 'daily_target_ton', label: labels.metrics['daily_target_ton'] ?? '日目标', render: (row) => formatNullable(row.daily_target_ton) },
    { key: 'actual_vs_bbc_percent', label: labels.metrics['actual_vs_bbc_percent'] ?? '完成率%', render: (row) => formatNullable(row.actual_vs_bbc_percent) },
  ]
}

function buildAkpColumns(): TableColumn[] {
  return [
    { key: 'panen_kg', label: 'Panen Kg', render: (row) => formatNullable(row.panen_kg) },
    { key: 'jumlah_janjang', label: 'Janjang', render: (row) => formatNullable(row.jumlah_janjang) },
    { key: 'akp_percent', label: 'AKP%', render: (row) => formatNullable(row.akp_percent) },
    { key: 'luas_ha', label: 'Luas Ha', render: (row) => formatNullable(row.luas_ha) },
  ]
}

function buildAttendanceColumns(labels: QueryLabels): TableColumn[] {
  return [
    { key: 'present_workers', label: labels.presentWorkers, render: (row) => formatNullable(row.present_workers) },
    { key: 'actual_workers', label: labels.actualWorkers, render: (row) => formatNullable(row.actual_workers) },
    { key: 'attendance_rate', label: labels.attendanceRate, render: (row) => formatNullable(row.attendance_rate) },
    { key: 'luas_ha', label: 'Luas Ha', render: (row) => formatNullable(row.luas_ha) },
  ]
}

function formatNullable(value: number | null) {
  return value === null ? '-' : formatNumber(value)
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export default QueryPage
