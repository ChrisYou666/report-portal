import { useEffect, useState } from 'react'
import { getDashboardStats, getBatches } from '../services/api'
import type { DashboardStats, UploadBatch } from '../services/api'

type DashboardPageProps = {
  onOpenPage: (page: string) => void
}

function DashboardPage({ onOpenPage }: DashboardPageProps) {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [batches, setBatches] = useState<UploadBatch[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const [s, b] = await Promise.all([getDashboardStats(), getBatches()])
        setStats(s)
        setBatches(b)
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败')
      }
    }
    load()
  }, [])

  const recentBatches = batches.slice(0, 5)

  return (
    <section className="portal-page">
      <div className="page-title-section">
        <p className="page-eyebrow">数据中台门户</p>
        <h1>工作台</h1>
        <p className="page-desc">棕榈油农业数据中台 — 实时汇总生产与出勤指标。</p>
      </div>

      {error && <div className="form-error">{error}</div>}

      {/* 业务 KPI */}
      <div className="metric-grid">
        <div className="metric-card">
          <span>当日产量</span>
          <strong>
            {stats?.today_production_ton != null
              ? formatTon(stats.today_production_ton)
              : <span className="text-muted">暂无数据</span>}
            {stats?.today_production_ton != null && <small> 吨</small>}
          </strong>
          {stats?.data_date && <small className="metric-date">{stats.data_date}</small>}
        </div>
        <div className="metric-card">
          <span>月累计产量</span>
          <strong>
            {stats?.mtd_production_ton != null
              ? formatTon(stats.mtd_production_ton)
              : <span className="text-muted">暂无数据</span>}
            {stats?.mtd_production_ton != null && <small> 吨</small>}
          </strong>
          {stats?.data_date && <small className="metric-date">{stats.data_date.slice(0, 7)}</small>}
        </div>
        <div className="metric-card">
          <span>今日出勤率</span>
          <strong>
            {stats?.today_attendance_rate != null
              ? `${stats.today_attendance_rate.toFixed(1)}`
              : <span className="text-muted">暂无数据</span>}
            {stats?.today_attendance_rate != null && <small> %</small>}
          </strong>
        </div>
        <div className="metric-card">
          <span>批次总数</span>
          <strong>{stats?.total_batches ?? '--'}</strong>
          <small className="metric-date">已解析 {stats?.parsed_batches ?? '--'}</small>
        </div>
      </div>

      {/* 快捷操作 */}
      <div className="page-action-bar" style={{ marginTop: 28 }}>
        <button className="btn-primary" type="button" onClick={() => onOpenPage('upload')}>
          ↑ 上传报表
        </button>
        <button className="btn-ghost" type="button" onClick={() => onOpenPage('query')}>
          ⊙ 指标分析
        </button>
        <button className="btn-ghost" type="button" onClick={() => onOpenPage('batches')}>
          ⊞ 批次流程
        </button>
      </div>

      {/* 最近批次 */}
      {recentBatches.length > 0 && (
        <div className="data-card" style={{ marginTop: 24 }}>
          <div style={{ padding: '14px 20px 10px', borderBottom: '1px solid #f1f5f9' }}>
            <strong style={{ fontSize: 13, color: '#374151' }}>最近上传批次</strong>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>批次号</th>
                <th>日期</th>
                <th>部门</th>
                <th>园区</th>
                <th>文件数</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {recentBatches.map(batch => (
                <tr key={batch.batch_no}>
                  <td><strong className="batch-no">{batch.batch_no}</strong></td>
                  <td>{batch.report_date}</td>
                  <td>{batch.department}</td>
                  <td>{batch.site || '—'}</td>
                  <td>{batch.files.length}</td>
                  <td><BatchStatusBadge status={batch.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {batches.length > 5 && (
            <div style={{ padding: '10px 20px', textAlign: 'right' }}>
              <button className="btn-ghost" type="button" onClick={() => onOpenPage('batches')}>
                查看全部 {batches.length} 个批次 →
              </button>
            </div>
          )}
        </div>
      )}

      {recentBatches.length === 0 && !error && (
        <div className="data-card" style={{ marginTop: 24 }}>
          <div className="empty-state">
            暂无上传批次。<button className="btn-ghost" type="button" style={{ marginLeft: 8 }} onClick={() => onOpenPage('upload')}>立即上传</button>
          </div>
        </div>
      )}
    </section>
  )
}

const STATUS_LABEL: Record<string, string> = {
  uploaded: '待解析',
  parsing: '解析中',
  queued: '排队中',
  running: '解析中',
  parsed: '已解析',
  parse_failed: '解析失败',
  parse_skipped: '已跳过',
}

const STATUS_CLASS: Record<string, string> = {
  parsed: 'status-active',
  parse_failed: 'status-inactive',
  parse_skipped: 'status-inactive',
}

function BatchStatusBadge({ status }: { status: string }) {
  return (
    <span className={`status-dot ${STATUS_CLASS[status] ?? ''}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

function formatTon(val: number): string {
  return val >= 1000
    ? `${(val / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })}k`
    : val.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export default DashboardPage
