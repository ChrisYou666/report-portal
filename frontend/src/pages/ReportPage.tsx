import { useEffect, useState } from 'react'
import {
  generateTodayHarvestReport,
  getHarvestReportStatus,
  pushLatestHarvestReport,
} from '../services/api'
import type { HarvestReportLinks, HarvestReportStatus } from '../services/api'

const emptyLinks: HarvestReportLinks = { html: '', png: '', xlsx: '' }

function ReportPage() {
  const [report, setReport] = useState<HarvestReportStatus | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [workingAction, setWorkingAction] = useState('')

  useEffect(() => {
    void loadReportStatus()
  }, [])

  async function loadReportStatus() {
    setLoading(true)
    setError('')
    try {
      setReport(await getHarvestReportStatus())
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载日报信息失败')
    } finally {
      setLoading(false)
    }
  }

  async function runAction(actionName: string, action: () => Promise<{ message: string }>) {
    setWorkingAction(actionName)
    setMessage('')
    setError('')
    try {
      const result = await action()
      setMessage(result.message)
      await loadReportStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    } finally {
      setWorkingAction('')
    }
  }

  const rows = [
    {
      key: 'agriculture-production',
      name: '农业产量监控日报',
      domain: '农业',
      latestDate: report?.latest_report_date ?? '—',
      status: report?.available ? '已生成' : '未生成',
      batchNo: report?.latest_batch_no || '—',
      available: Boolean(report?.available),
      links: report?.links ?? emptyLinks,
      enabled: true,
    },
    {
      key: 'factory-production',
      name: '工厂产量日报',
      domain: '工业',
      latestDate: '—',
      status: '未接入',
      batchNo: '—',
      available: false,
      links: emptyLinks,
      enabled: false,
    },
  ]

  return (
    <section className="portal-page">
      <div className="page-title-section">
        <p className="page-eyebrow">报表管理</p>
        <h1>日报管理</h1>
        <p className="page-desc">统一管理固定输出的日报，查看最新日期、报表链接，并执行生成和发送操作。</p>
      </div>

      <div className="page-action-bar">
        <button
          className="btn-ghost"
          type="button"
          disabled={loading}
          onClick={loadReportStatus}
        >
          刷新
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-message">{message}</div>}

      <div className="data-card">
        {loading ? (
          <div className="empty-state">加载中...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>报表名称</th>
                <th>业务域</th>
                <th>最新日期</th>
                <th>状态</th>
                <th>来源批次</th>
                <th>报表链接</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className={row.enabled ? '' : 'row-disabled'}>
                  <td>
                    <strong>{row.name}</strong>
                    <small style={{ display: 'block', color: '#94a3b8', marginTop: 2 }}>
                      {row.enabled ? '上传表单汇总生成' : '后续接入'}
                    </small>
                  </td>
                  <td>{row.domain}</td>
                  <td>{row.latestDate}</td>
                  <td>
                    <span className={`status-dot ${row.available ? 'status-active' : ''}`}>
                      {row.status}
                    </span>
                  </td>
                  <td><span style={{ fontFamily: 'monospace', fontSize: 12 }}>{row.batchNo}</span></td>
                  <td>
                    <div className="row-actions">
                      <ReportLink label="HTML" href={row.links.html} disabled={!row.available} />
                      <ReportLink label="图片" href={row.links.png} disabled={!row.available} />
                      <ReportLink label="Excel" href={row.links.xlsx} disabled={!row.available} />
                    </div>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="btn-row"
                        type="button"
                        disabled={!row.enabled || Boolean(workingAction)}
                        onClick={() => runAction('generate', generateTodayHarvestReport)}
                      >
                        {workingAction === 'generate' && row.enabled ? '生成中...' : '生成今日'}
                      </button>
                      <button
                        className="btn-row"
                        type="button"
                        disabled={!row.enabled || !row.available || Boolean(workingAction)}
                        onClick={() => runAction('push', pushLatestHarvestReport)}
                      >
                        {workingAction === 'push' && row.enabled ? '发送中...' : '发送'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

function ReportLink({ label, href, disabled }: { label: string; href: string; disabled: boolean }) {
  if (disabled || !href) {
    return <span className="btn-row" style={{ opacity: 0.35, cursor: 'default' }}>{label}</span>
  }
  return (
    <a className="btn-row" href={href} target="_blank" rel="noreferrer">
      {label}
    </a>
  )
}

export default ReportPage
