import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { useI18n } from '../i18n'
import type { UploadMessages } from '../i18n'
import { getBatches, getUploadOptions, uploadReports } from '../services/api'
import type { UploadBatch } from '../services/api'

type ReportType = '日报' | '周报' | '月报'

type UploadForm = {
  reportName: string
  reportType: ReportType
  department: string
  site: string
  reportDate: string
  uploader: string
  remark: string
}

const reportTypes: ReportType[] = ['日报', '周报', '月报']

const allowedExtensions = ['xlsx', 'xls', 'csv', 'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg']
const fallbackUploaders = ['王浩源', '张杰铭', '王云豪']
const fallbackDepartments = ['农业', '工业']
const fallbackSites = ['七园', '八园']

const maxRecentRecords = 5

function createInitialForm(): UploadForm {
  return {
    reportName: '',
    reportType: '日报',
    department: '',
    site: '',
    reportDate: getYesterdayDateString(),
    uploader: '',
    remark: '',
  }
}

function UploadPage() {
  const { t } = useI18n()
  const uploadText = t.upload
  const [form, setForm] = useState<UploadForm>(() => createInitialForm())
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [uploaders, setUploaders] = useState<string[]>(fallbackUploaders)
  const [departments, setDepartments] = useState<string[]>(fallbackDepartments)
  const [sites, setSites] = useState<string[]>(fallbackSites)
  const [records, setRecords] = useState<UploadBatch[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const dragDepthRef = useRef(0)

  const selectedFileText = useMemo(() => {
    if (files.length === 0) return uploadText.supportFiles
    const totalSize = files.reduce((sum, currentFile) => sum + currentFile.size, 0)
    return `${uploadText.selectedFiles} ${files.length} ${uploadText.filesUnit} / ${uploadText.total} ${formatFileSize(totalSize)}`
  }, [files, uploadText])

  const todayStr = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const uploadedFileCount = useMemo(
    () =>
      records
        .filter((batch) => batch.created_at.slice(0, 10) === todayStr)
        .reduce((sum, batch) => sum + batch.files.length, 0),
    [records, todayStr],
  )

  const visibleRecords = useMemo(() => records.slice(0, maxRecentRecords), [records])

  useEffect(() => {
    loadInitialData()
  }, [])

  async function loadInitialData() {
    setIsLoading(true)
    setError('')
    try {
      const options = await getUploadOptions()
      setUploaders(options.uploaders?.length ? options.uploaders : fallbackUploaders)
      setDepartments(options.departments?.length ? options.departments : fallbackDepartments)
      setSites(options.sites?.length ? options.sites : fallbackSites)
    } catch (currentError) {
      setUploaders(fallbackUploaders)
      setDepartments(fallbackDepartments)
      setSites(fallbackSites)
      setError(getErrorMessage(currentError, t.common.operationFailed))
    }

    try {
      const batches = await getBatches()
      setRecords(batches)
    } catch (currentError) {
      setError(getErrorMessage(currentError, t.common.operationFailed))
    } finally {
      setIsLoading(false)
    }
  }

  function updateForm<K extends keyof UploadForm>(key: K, value: UploadForm[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function handleFileChange(selectedFiles: FileList | File[] | null) {
    setError('')
    setMessage('')
    if (!selectedFiles || selectedFiles.length === 0) {
      setFiles([])
      return
    }

    const fileList = Array.from(selectedFiles)
    const invalidFile = fileList.find((currentFile) => {
      const extension = currentFile.name.split('.').pop()?.toLowerCase()
      return !extension || !allowedExtensions.includes(extension)
    })

    if (invalidFile) {
      setFiles([])
      setError(`${uploadText.invalidFilePrefix}${invalidFile.name}${uploadText.invalidFileSuffix}`)
      return
    }

    setFiles(fileList)
  }

  function hasDraggedFiles(event: DragEvent<HTMLElement>) {
    return Array.from(event.dataTransfer.types).includes('Files')
  }

  function handlePageDragEnter(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (!hasDraggedFiles(event)) return
    dragDepthRef.current += 1
    setIsDragging(true)
  }

  function handlePageDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (!hasDraggedFiles(event)) return
    event.dataTransfer.dropEffect = 'copy'
    setIsDragging(true)
  }

  function handlePageDragLeave(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (!hasDraggedFiles(event)) return
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
    if (dragDepthRef.current === 0) {
      setIsDragging(false)
    }
  }

  function handlePageDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    event.stopPropagation()
    dragDepthRef.current = 0
    setIsDragging(false)
    handleFileChange(Array.from(event.dataTransfer.files))
  }

  async function handleSubmit() {
    const validationError = validateForm(form, files, uploadText)
    if (validationError) {
      setError(validationError)
      return
    }

    setIsSubmitting(true)
    setError('')
    setMessage('')

    try {
      const inferredReportName = inferReportName(files[0]?.name ?? '') || files[0]?.name || uploadText.defaultReportValue
      const batch = await uploadReports({ ...form, reportName: inferredReportName, files })
      setFiles([])
      setMessage(`${uploadText.uploadSuccessPrefix}${batch.batch_no}，正在后台 AI 解析`)
      setRecords(await getBatches())
    } catch (currentError) {
      setError(getErrorMessage(currentError, t.common.operationFailed))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section
      className={`upload-page${isDragging ? ' is-dragging' : ''}`}
      onDragEnter={handlePageDragEnter}
      onDragOver={handlePageDragOver}
      onDragLeave={handlePageDragLeave}
      onDrop={handlePageDrop}
    >
      <div className="page-header">
        <div>
          <div className="title-row">
            <h1>{uploadText.title}</h1>
          </div>
          <p>{uploadText.description}</p>
        </div>
        <div className="summary-card">
          <span>{uploadText.todayUpload}</span>
          <strong>{uploadedFileCount}</strong>
        </div>
      </div>

      <div className="upload-grid">
        <form className="upload-card" onSubmit={(event) => event.preventDefault()}>
          <div className="card-title">
            <h2>{uploadText.basicInfo}</h2>
            <span>{uploadText.fillOnce}</span>
          </div>

          <div className="form-grid">
            <label className="field">
              <span>{uploadText.reportType}</span>
              <select
                value={form.reportType}
                onChange={(event) => updateForm('reportType', event.target.value as ReportType)}
              >
                {reportTypes.map((type) => (
                  <option key={type} value={type}>
                    {uploadText.reportTypes[type]}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>{uploadText.department}</span>
              <select
                value={form.department}
                onChange={(event) => updateForm('department', event.target.value)}
              >
                <option value="">{uploadText.selectDepartment}</option>
                {departments.map((department) => (
                  <option key={department} value={department}>
                    {uploadText.departmentOptions[department] ?? department}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>{uploadText.site}</span>
              <select
                value={form.site}
                onChange={(event) => updateForm('site', event.target.value)}
              >
                <option value="">{uploadText.selectSite}</option>
                {sites.map((site) => (
                  <option key={site} value={site}>
                    {uploadText.siteOptions[site] ?? site}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>{uploadText.reportDate}</span>
              <input
                type="date"
                value={form.reportDate}
                onChange={(event) => updateForm('reportDate', event.target.value)}
              />
            </label>

            <label className="field">
              <span>{uploadText.uploader}</span>
              <select value={form.uploader} onChange={(event) => updateForm('uploader', event.target.value)}>
                <option value="">{uploadText.selectUploader}</option>
                {uploaders.map((uploader) => (
                  <option key={uploader}>{uploader}</option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>{uploadText.remark}</span>
              <input value={form.remark} onChange={(event) => updateForm('remark', event.target.value)} />
            </label>
          </div>

          <label className={`file-upload${isDragging ? ' is-dragging' : ''}`}>
            <input
              type="file"
              multiple
              accept=".xlsx,.xls,.csv,.pdf,.doc,.docx,.png,.jpg,.jpeg"
              onChange={(event) => handleFileChange(event.target.files)}
            />
            <strong>{files.length > 0 ? uploadText.selectedFile : uploadText.chooseFile}</strong>
            <span>{selectedFileText}</span>
          </label>

          {files.length > 0 && (
            <div className="selected-files">
              {files.map((currentFile) => (
                <div className="selected-file" key={`${currentFile.name}-${currentFile.size}`}>
                  <span>{inferReportName(currentFile.name) || currentFile.name}</span>
                  <small>
                    {currentFile.name} / {formatFileSize(currentFile.size)}
                  </small>
                </div>
              ))}
            </div>
          )}

          {error && <div className="form-error">{error}</div>}
          {message && <div className="form-message">{message}</div>}

          <button className="primary-button" type="button" disabled={isSubmitting} onClick={handleSubmit}>
            {isSubmitting ? uploadText.submitting : uploadText.submit}
          </button>
        </form>

        <aside className="upload-card">
          <div className="card-title">
            <h2>{uploadText.recentUpload}</h2>
            <span>{uploadText.localRecord} · {visibleRecords.length}/{records.length}</span>
          </div>

          <div className="record-list">
            {isLoading ? (
              <div className="empty-state">{t.common.loading}</div>
            ) : records.length === 0 ? (
              <div className="empty-state">{uploadText.empty}</div>
            ) : (
              visibleRecords.map((record) => (
                <article className="record-card" key={record.batch_no}>
                  <div>
                    <strong>{record.report_name}</strong>
                    <span>{record.batch_no}</span>
                  </div>
                  <p>{record.files.map((file) => file.original_filename).join(' / ')}</p>
                  <dl>
                    <div>
                      <dt>{uploadText.date}</dt>
                      <dd>{record.report_date}</dd>
                    </div>
                    <div>
                      <dt>{uploadText.department}</dt>
                      <dd>{record.department}</dd>
                    </div>
                    <div>
                      <dt>{uploadText.site}</dt>
                      <dd>{record.site || '-'}</dd>
                    </div>
                    <div>
                      <dt>{uploadText.status}</dt>
                      <dd>{formatStatus(record.status, t.status)}</dd>
                    </div>
                  </dl>
                  <div className="record-files">
                    {record.files.map((file) => (
                      <span key={file.id}>
                        {file.detected_report_name} · {formatFileSize(file.file_size)} · {formatStatus(file.status, t.status)}
                        {file.stored_path.startsWith('http') && (
                          <a href={file.stored_path} target="_blank" rel="noreferrer">
                            {uploadText.openFile}
                          </a>
                        )}
                      </span>
                    ))}
                  </div>
                </article>
              ))
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}

function validateForm(form: UploadForm, fileList: File[], t: UploadMessages) {
  if (!form.department.trim()) return t.requiredDepartment
  if (!form.reportDate) return t.requiredDate
  if (!form.uploader.trim()) return t.requiredUploader
  if (fileList.length === 0) return t.requiredFile
  return ''
}

function inferReportName(fileName: string) {
  return fileName
    .replace(/\.[^.]+$/, '')
    .replace(/[_-]?\d{4}[._-]?\d{1,2}[._-]?\d{1,2}/g, '')
    .replace(/[_-]?\d{8}/g, '')
    .replace(/[_-]+/g, ' ')
    .trim()
}

function formatFileSize(size: number) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatStatus(status: string, statusMap: Record<string, string>) {
  return statusMap[status] ?? status
}

function getYesterdayDateString() {
  const date = new Date()
  date.setDate(date.getDate() - 1)
  return date.toISOString().slice(0, 10)
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error) return error.message
  return fallback
}

export default UploadPage
