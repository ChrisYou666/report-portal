import { Fragment, useEffect, useMemo, useState } from 'react'
import { getBatches, getParseProgress, parseBatch } from '../services/api'
import type { ParseProgress, UploadBatch } from '../services/api'
import { useI18n } from '../i18n'

type BatchStatusFilter = 'all' | 'uploaded' | 'parsed'

const pageSize = 10
const workflowSteps = ['uploaded', 'parsed']
const runningStatuses = ['queued', 'running', 'parsing']

const labels = {
  all: '全部批次',
  uploaded: '已上传',
  parsed: '已解析',
  batchNo: '批次',
  date: '日期',
  department: '部门',
  site: '园区/工厂',
  files: '文件',
  flow: '流程',
  actions: '操作',
  totalPrefix: '共',
  totalSuffix: '条',
  pagePrefix: '第',
  pageSuffix: '页',
  emptyFiltered: '当前筛选条件下没有批次。',
  previous: '上一页',
  next: '下一页',
}

function BatchPage() {
  const { t } = useI18n()
  const [batches, setBatches] = useState<UploadBatch[]>([])
  const [progressByBatch, setProgressByBatch] = useState<Record<string, ParseProgress>>({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [activeBatchNo, setActiveBatchNo] = useState('')
  const [statusFilter, setStatusFilter] = useState<BatchStatusFilter>('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [modalBatchNo, setModalBatchNo] = useState<string | null>(null)
  const modalBatch = modalBatchNo ? batches.find((b) => b.batch_no === modalBatchNo) ?? null : null

  const runningBatchNos = useMemo(() => {
    const fromProgress = Object.values(progressByBatch)
      .filter((p) => isProgressRunning(p.status))
      .map((p) => p.batch_no)
    const fromBatches = batches
      .filter((b) => runningStatuses.includes(b.status))
      .map((b) => b.batch_no)
    return Array.from(new Set([...fromProgress, ...fromBatches]))
  }, [batches, progressByBatch])

  const filteredBatches = useMemo(
    () => batches.filter((b) => batchMatchesFilter(b, progressByBatch[b.batch_no], statusFilter)),
    [batches, progressByBatch, statusFilter],
  )

  const totalPages = Math.max(1, Math.ceil(filteredBatches.length / pageSize))
  const pagedBatches = useMemo(
    () => filteredBatches.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [filteredBatches, currentPage],
  )

  const filterOptions = useMemo(
    () => [
      { value: 'all' as const, label: labels.all, count: batches.length },
      { value: 'uploaded' as const, label: labels.uploaded, count: countByFilter(batches, progressByBatch, 'uploaded') },
      { value: 'parsed' as const, label: labels.parsed, count: countByFilter(batches, progressByBatch, 'parsed') },
    ],
    [batches, progressByBatch],
  )

  useEffect(() => { loadBatches() }, [])
  useEffect(() => { setCurrentPage(1) }, [statusFilter])
  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages)
  }, [currentPage, totalPages])

  useEffect(() => {
    if (runningBatchNos.length === 0) return
    const timer = window.setInterval(() => {
      for (const batchNo of runningBatchNos) loadProgress(batchNo)
      loadBatches()
    }, 1500)
    return () => window.clearInterval(timer)
  }, [runningBatchNos])

  async function loadBatches() {
    try {
      setBatches(await getBatches())
    } catch (e) {
      setError(e instanceof Error ? e.message : t.batch.loadFailed)
    }
  }

  async function loadProgress(batchNo: string) {
    try {
      const progress = await getParseProgress(batchNo)
      setProgressByBatch((cur) => ({ ...cur, [batchNo]: progress }))
    } catch {
      // ParseJob 在解析启动后才会创建
    }
  }

  function openModal(batchNo: string) {
    setModalBatchNo(batchNo)
    if (!progressByBatch[batchNo]) loadProgress(batchNo)
  }

  function closeModal() {
    setModalBatchNo(null)
  }

  async function handleReparse(batchNo: string) {
    setActiveBatchNo(batchNo)
    setError('')
    setMessage('')
    try {
      await parseBatch(batchNo)
      setMessage(t.batch.actionCompleted)
      await loadBatches()
      await loadProgress(batchNo)
    } catch (e) {
      setError(e instanceof Error ? e.message : t.batch.actionFailed)
    } finally {
      setActiveBatchNo('')
    }
  }

  return (
    <section className="portal-page">
      <header className="section-header">
        <div>
          <span>{t.batch.eyebrow}</span>
          <h1>{t.batch.title}</h1>
          <p>{t.batch.description}</p>
        </div>
      </header>

      {error && <div className="form-error">{error}</div>}
      {message && <div className="form-message">{message}</div>}

      <div className="batch-table-panel">
        {batches.length === 0 ? (
          <div className="empty-state">{t.batch.empty}</div>
        ) : (
          <>
            <div className="batch-list-toolbar">
              <div className="batch-filter-tabs">
                {filterOptions.map((opt) => (
                  <button
                    className={statusFilter === opt.value ? 'active' : ''}
                    key={opt.value}
                    type="button"
                    onClick={() => setStatusFilter(opt.value)}
                  >
                    {opt.label}
                    <span>{opt.count}</span>
                  </button>
                ))}
              </div>
              <div className="batch-page-summary">
                {labels.totalPrefix} {filteredBatches.length} {labels.totalSuffix} · {labels.pagePrefix} {currentPage}/
                {totalPages} {labels.pageSuffix}
              </div>
            </div>

            {filteredBatches.length === 0 ? (
              <div className="empty-state">{labels.emptyFiltered}</div>
            ) : (
              <>
                <table className="batch-table">
                  <thead>
                    <tr>
                      <th>{labels.batchNo}</th>
                      <th>{labels.date}</th>
                      <th>{labels.department}</th>
                      <th>{labels.site}</th>
                      <th>{labels.files}</th>
                      <th>{labels.flow}</th>
                      <th>{labels.actions}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedBatches.map((batch) => {
                      const progress = progressByBatch[batch.batch_no]
                      const currentStatus = progress?.status ?? batch.status
                      const isParsing = progress
                        ? isProgressRunning(progress.status)
                        : runningStatuses.includes(batch.status)
                      return (
                        <Fragment key={batch.batch_no}>
                          <tr>
                            <td>
                              <strong className="batch-no">{batch.batch_no}</strong>
                              <small>{batch.uploader}</small>
                            </td>
                            <td>{batch.report_date}</td>
                            <td>{batch.department}</td>
                            <td>{batch.site || '-'}</td>
                            <td>
                              <span className="file-count">{batch.files.length}</span>
                              <small className="file-names">{formatFileNames(batch)}</small>
                            </td>
                            <td>
                              <div className="pipeline compact">
                                {workflowSteps.map((step) => (
                                  <span className={isStepDone(currentStatus, step) ? 'done' : ''} key={step}>
                                    {formatStatus(step, t.status)}
                                  </span>
                                ))}
                                {isParsing && (
                                  <span className="parsing-indicator">{t.batch.parsing}</span>
                                )}
                              </div>
                            </td>
                            <td>
                              <div className="batch-actions compact">
                                <button
                                  type="button"
                                  onClick={() => openModal(batch.batch_no)}
                                >
                                  {t.batch.detail}
                                </button>
                              </div>
                            </td>
                          </tr>
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>

                <div className="batch-pagination">
                  <button type="button" disabled={currentPage <= 1} onClick={() => setCurrentPage((p) => p - 1)}>
                    {labels.previous}
                  </button>
                  <span>{currentPage} / {totalPages}</span>
                  <button type="button" disabled={currentPage >= totalPages} onClick={() => setCurrentPage((p) => p + 1)}>
                    {labels.next}
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>

      {modalBatch && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h3>{t.batch.detail}</h3>
                <small>{modalBatch.batch_no} · {modalBatch.report_date} · {modalBatch.site || modalBatch.department}</small>
              </div>
              <button type="button" className="modal-close" onClick={closeModal}>✕</button>
            </div>
            <div className="modal-body">
              <BatchDetailPanel
                batch={modalBatch}
                progress={progressByBatch[modalBatch.batch_no]}
                isParsing={
                  progressByBatch[modalBatch.batch_no]
                    ? isProgressRunning(progressByBatch[modalBatch.batch_no].status)
                    : runningStatuses.includes(modalBatch.status)
                }
                isReparsing={activeBatchNo === modalBatch.batch_no}
                onReparse={handleReparse}
                statusMap={t.status}
                labels={t.batch}
              />
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

// ─── 批次详情面板 ───────────────────────────────────────────────────────────────

function BatchDetailPanel({
  batch,
  progress,
  isParsing,
  isReparsing,
  onReparse,
  statusMap,
  labels,
}: {
  batch: UploadBatch
  progress: ParseProgress | undefined
  isParsing: boolean
  isReparsing: boolean
  onReparse: (batchNo: string) => void
  statusMap: Record<string, string>
  labels: {
    uploadedFiles: string
    parseStatus: string
    reparse: string
    reparsing: string
    noParseRecord: string
    progress: string
    currentFile: string
    parsedCount: string
    skippedCount: string
    failedCount: string
  }
}) {
  const parseStatus = progress?.status ?? batch.status
  const canReparse = ['parsed', 'parse_failed', 'parse_skipped'].includes(parseStatus) && !isParsing

  return (
    <div className="batch-detail-panel">
      {/* 文件列表 */}
      <div className="batch-detail-section">
        <h4 className="batch-detail-section-title">{labels.uploadedFiles}</h4>
        <table className="batch-file-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>大小</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {batch.files.map((file) => (
              <tr key={file.id}>
                <td>
                  <a href={fileStorageUrl(file.stored_path)} target="_blank" rel="noreferrer">
                    {file.original_filename}
                  </a>
                </td>
                <td>{file.file_type.toUpperCase()}</td>
                <td>{formatFileSize(file.file_size)}</td>
                <td>{statusMap[file.status] ?? file.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 解析状态 */}
      <div className="batch-detail-section">
        <h4 className="batch-detail-section-title">{labels.parseStatus}</h4>
        {progress ? (
          <div className="batch-detail-parse">
            <ParseProgressPanel progress={progress} labels={labels} statusMap={statusMap} />
            {canReparse && (
              <button
                type="button"
                className="reparse-btn"
                disabled={isReparsing}
                onClick={() => onReparse(batch.batch_no)}
              >
                {isReparsing ? labels.reparsing : labels.reparse}
              </button>
            )}
          </div>
        ) : (
          <p className="parse-status-empty">{labels.noParseRecord}</p>
        )}
      </div>
    </div>
  )
}

// ─── 解析进度子面板 ─────────────────────────────────────────────────────────────

function ParseProgressPanel({
  progress,
  labels,
  statusMap,
}: {
  progress: ParseProgress
  labels: { progress: string; currentFile: string; parsedCount: string; skippedCount: string; failedCount: string }
  statusMap: Record<string, string>
}) {
  const percent =
    progress.total_files > 0 ? Math.round((progress.processed_files / progress.total_files) * 100) : 0
  return (
    <div className="parse-progress">
      <div className="parse-progress-header">
        <span>{labels.progress}</span>
        <strong>{percent}%</strong>
      </div>
      <div className="parse-progress-bar" aria-label={labels.progress}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="parse-progress-meta">
        <span>
          {progress.processed_files}/{progress.total_files} · {formatStatus(progress.status, statusMap)}
        </span>
        {progress.current_filename && (
          <span>{labels.currentFile}: {progress.current_filename}</span>
        )}
      </div>
      <div className="parse-progress-counts">
        <span>{labels.parsedCount}: {progress.parsed_files}</span>
        <span>{labels.skippedCount}: {progress.skipped_files}</span>
        <span>{labels.failedCount}: {progress.failed_files}</span>
      </div>
      {(progress.error_message || progress.message) && (
        <p className="parse-progress-message">{progress.error_message || progress.message}</p>
      )}
    </div>
  )
}

// ─── 纯函数工具 ────────────────────────────────────────────────────────────────

const statusOrder = ['uploaded', 'parsing', 'running', 'queued', 'parsed']

function isStepDone(currentStatus: string, stepStatus: string) {
  if (['parse_failed', 'parse_skipped'].includes(currentStatus)) return stepStatus === 'uploaded'
  if (runningStatuses.includes(currentStatus)) return stepStatus === 'uploaded'
  return statusOrder.indexOf(currentStatus) >= statusOrder.indexOf(stepStatus)
}

function batchMatchesFilter(batch: UploadBatch, progress: ParseProgress | undefined, filter: BatchStatusFilter) {
  if (filter === 'all') return true
  const status = progress?.status ?? batch.status
  if (filter === 'uploaded') return status === 'uploaded'
  return ['queued', 'running', 'parsing', 'parsed', 'parse_failed', 'parse_skipped'].includes(status)
}

function countByFilter(
  batches: UploadBatch[],
  progressByBatch: Record<string, ParseProgress>,
  filter: BatchStatusFilter,
) {
  return batches.filter((b) => batchMatchesFilter(b, progressByBatch[b.batch_no], filter)).length
}

function isProgressRunning(status: string) {
  return runningStatuses.includes(status)
}

function formatStatus(status: string, statusMap: Record<string, string>) {
  return statusMap[status] ?? status
}

function formatFileNames(batch: UploadBatch) {
  const names = batch.files.map((f) => f.original_filename)
  if (names.length <= 2) return names.join(' / ')
  return `${names.slice(0, 2).join(' / ')} +${names.length - 2}`
}

function fileStorageUrl(storedPath: string): string {
  if (storedPath.startsWith('http://') || storedPath.startsWith('https://')) return storedPath
  const normalized = storedPath.replace(/\\/g, '/')
  return normalized.startsWith('/') ? normalized : '/' + normalized
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default BatchPage
