const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    window.location.reload()
  }
}

export type UploadOptions = {
  report_types: string[]
  uploaders: string[]
  allowed_extensions: string[]
  departments: string[]
  sites: string[]
}

export type UploadFileRecord = {
  id: number
  original_filename: string
  stored_path: string
  file_size: number
  file_type: string
  detected_report_name: string
  status: string
  created_at: string
}

export type UploadBatch = {
  id: number
  batch_no: string
  report_name: string
  report_type: string
  department: string
  site: string
  factory: string
  report_date: string
  uploader: string
  remark: string
  status: string
  created_at: string
  files: UploadFileRecord[]
}

export type ParseProgress = {
  batch_no: string
  status: string
  total_files: number
  processed_files: number
  parsed_files: number
  skipped_files: number
  failed_files: number
  current_filename: string
  message: string
  error_message: string
  started_at: string | null
  finished_at: string | null
  updated_at: string
}

export type UploadReportInput = {
  reportName: string
  reportType: string
  department: string
  site: string
  reportDate: string
  uploader: string
  remark: string
  files: File[]
}

export type MetricItem = {
  metric_name: string
  metric_value: string
  unit: string
  date: string
  department: string
  source: string
  status: string
  updated_at: string
}

export type MetricCard = {
  label: string
  value: string
  unit: string
}

export type MetricTrendPoint = {
  period: string
  value: number
}

export type MetricAnalysisRow = {
  dimension: string
  metric_value: number
  unit: string
  panen_kg: number | null
  jumlah_janjang: number | null
  akp_percent: number | null
  luas_ha: number | null
  worker_type: string | null
  actual_workers: number | null
  present_workers: number | null
  attendance_rate: number | null
  actual_today_ton: number | null
  actual_to_date_ton: number | null
  bbc_ton: number | null
  daily_target_ton: number | null
  actual_vs_bbc_percent: number | null
}

export type DashboardStats = {
  today_production_ton: number | null
  mtd_production_ton: number | null
  today_attendance_rate: number | null
  data_date: string | null
  total_batches: number
  parsed_batches: number
}

export type MetricAnalysisResponse = {
  subject: string
  metric: string
  period_type: string
  group_by: string
  cards: MetricCard[]
  trends: MetricTrendPoint[]
  rows: MetricAnalysisRow[]
}

export type MetricDimensionOptions = {
  sites: string[]
  divisions: string[]
  bloks: string[]
  worker_types: string[]
}

export type MetricAnalysisQuery = {
  subject: string
  metric: string
  periodType: string
  groupBy: string
  startDate: string
  endDate: string
  site: string
  division: string
  blok: string
  workerType: string
}

export type HarvestReportLinks = {
  html: string
  xlsx: string
  png: string
}

export type HarvestReportStatus = {
  report_name: string
  latest_report_date: string | null
  latest_batch_no: string
  latest_batch_status: string
  available: boolean
  links: HarvestReportLinks
  message: string
}

export async function getDashboardStats() {
  return request<DashboardStats>('/dashboard/stats')
}

export async function submitProductionEntry(payload: {
  report_date: string; site: string; department: string
  rows: Array<{ division: string; luas_ha?: number | null; bbc_ton?: number | null; actual_today_ton?: number | null; actual_to_date_ton?: number | null; remaining_bbc_ton?: number | null; remaining_effective_days?: number | null; daily_target_ton?: number | null }>
}) {
  return postJson('/entry/production-monitoring', payload)
}

export async function submitAkpEntry(payload: {
  report_date: string; site: string; department: string
  rows: Array<{ division: string; blok?: string; sap?: string; luas_ha?: number | null; panen_count?: number | null; akp_percent?: number | null; panen_kg?: number | null; jumlah_janjang?: number | null; tk_panen?: number | null; keterangan?: string }>
}) {
  return postJson('/entry/akp-density', payload)
}

export async function submitAttendanceEntry(payload: {
  report_date: string; site: string; department: string
  rows: Array<{ worker_type: string; afdeling?: string; luas_ha?: number | null; kebutuhan_pemanen?: number | null; actual_pemanen?: number | null; hadir?: number | null; ijin?: number | null; cuti?: number | null; sakit?: number | null; mangkir?: number | null; total_karyawan?: number | null }>
}) {
  return postJson('/entry/attendance', payload)
}

export async function getUploadOptions() {
  return request<UploadOptions>('/upload-options')
}

export async function getBatches() {
  return request<UploadBatch[]>('/batches')
}

export async function getMetrics() {
  return request<{ items: MetricItem[] }>('/query/metrics')
}

export async function getMetricDimensions() {
  return request<MetricDimensionOptions>('/query/dimensions')
}

export async function getMetricAnalysis(query: MetricAnalysisQuery) {
  const params = new URLSearchParams()
  params.set('subject', query.subject)
  params.set('metric', query.metric)
  params.set('period_type', query.periodType)
  params.set('group_by', query.groupBy)
  if (query.startDate) params.set('start_date', query.startDate)
  if (query.endDate) params.set('end_date', query.endDate)
  if (query.site) params.set('site', query.site)
  if (query.division) params.set('division', query.division)
  if (query.blok) params.set('blok', query.blok)
  if (query.workerType) params.set('worker_type', query.workerType)
  return request<MetricAnalysisResponse>(`/query/analysis?${params.toString()}`)
}

export async function parseBatch(batchNo: string) {
  return postAction(`/batches/${batchNo}/parse`)
}

export async function getParseProgress(batchNo: string) {
  return request<ParseProgress>(`/batches/${batchNo}/parse-progress`)
}

export async function getHarvestReportStatus() {
  return request<HarvestReportStatus>('/reports/harvest/status')
}

export async function generateTodayHarvestReport() {
  return postAction('/reports/harvest/generate-today')
}

export async function pushLatestHarvestReport() {
  return postAction('/reports/harvest/push-latest')
}

export async function uploadReports(input: UploadReportInput) {
  const formData = new FormData()
  formData.append('report_name', input.reportName)
  formData.append('report_type', input.reportType)
  formData.append('department', input.department)
  formData.append('site', input.site)
  formData.append('factory', '')
  formData.append('report_date', input.reportDate)
  formData.append('uploader', input.uploader)
  formData.append('remark', input.remark)

  for (const file of input.files) {
    formData.append('files', file)
  }

  const response = await fetch(`${API_BASE_URL}/uploads`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)

  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }

  return response.json() as Promise<UploadBatch>
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() })
  handleUnauthorized(response)
  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }
  if (!isJsonResponse(response)) {
    throw new Error('API response is not JSON. Check FastAPI on port 8000.')
  }
  return response.json() as Promise<T>
}

async function postJson<T = { message: string }>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await readErrorMessage(response))
  return response.json() as Promise<T>
}

async function postAction(path: string) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) {
    throw new Error(await readErrorMessage(response))
  }
  if (!isJsonResponse(response)) {
    throw new Error('API response is not JSON. Check FastAPI on port 8000.')
  }
  return response.json() as Promise<{ batch_no: string; status: string; message: string }>
}

// ── Index types ───────────────────────────────────────────────

export type SubMetricDef = {
  id: number
  index_id: number
  code: string
  name: string
  unit: string
  source_type: 'manual' | 'db_sync' | 'fixed'
  fixed_value: number | null
  db_table: string | null
  db_field: string | null
  db_aggregation: string
  db_date_col: string
  db_extra_where: string | null
  fiscal_start_month: number | null
  sort_order: number
}

export type IndexDef = {
  id: number
  code: string
  name: string
  formula: string
  description: string
  sort_order: number
  is_active: boolean
  granularity: 'monthly' | 'daily'
  sub_metrics: SubMetricDef[]
}

export type IndexDefIn = {
  code: string
  name: string
  formula: string
  description: string
  sort_order: number
  is_active: boolean
  granularity: 'monthly' | 'daily'
}

export type SubMetricIn = {
  code: string
  name: string
  unit: string
  source_type: 'manual' | 'db_sync' | 'fixed'
  fixed_value: number | null
  db_table: string | null
  db_field: string | null
  db_aggregation: string
  db_date_col: string
  db_extra_where: string | null
  fiscal_start_month: number | null
  sort_order: number
}

export type SmSyncItem = { year: number; month: number; value: number | null }
export type SmSyncResult = { synced: number; sub_metric_id: number; items: SmSyncItem[] }

export type CompositeFormula = { label: string; formula: string }

export type IndexDataPoint = { year: number; month: number; value: number | null }

export type IndexCalcSeries = {
  id: number
  code: string
  name: string
  formula: string
  granularity: 'monthly' | 'daily'
  sub_metrics: { id: number; code: string; name: string; unit: string }[]
  data: IndexDataPoint[]
}

export type DailyDataPoint = { date: string; value: number | null }

export type IndexCalcResult = {
  composite: { label: string; formula: string; data: IndexDataPoint[] }
  indices: IndexCalcSeries[]
}

export type SubMetricTimeSeries = {
  id: number
  code: string
  name: string
  unit: string
  data: IndexDataPoint[]
}

export type IndexDataEntryItem = {
  sub_metric_id: number
  value: number | null
  source: string
  remark: string
}

export type AgriProductionItem = {
  year: number
  month: number
  cumulative_tons: number
  value: number
}

export type AgriSyncResult = {
  synced: number
  sub_metric_id: number
  items: AgriProductionItem[]
}

export type HarvestPipelineSyncResult = {
  job_id: string
  status: 'running' | 'success' | 'failed'
  months: number
  source_tables: string[]
  current_step: string
  current_table: string
  current_rows: number
  ods_rows: Record<string, number>
  dwd_rows: number
  message: string
  error: string
  started_at: string | null
  finished_at: string | null
  logs: string[]
}

export type HarvestDailyPreviewItem = {
  date: string
  production_bg: number
  production_ag: number
  unit: string
  row_count: number
}

export type HarvestMonitorResult = {
  prod_field?: string   // 实际查询的产量字段名，如 production_ag / production_bg
  summary: {
    min_date: string | null
    max_date: string | null
    expected_date: string
    total_rows: number
    estate_count: number
    latest_built_at: string | null
    days_lag: number | null
  }
  estates: Array<{
    company_code: string
    company_name: string
    estate_code: string
    estate_name: string
    latest_date: string | null
    days_lag: number | null
    days_with_data_7d: number
    latest_production_ag: number
    row_count: number
    status: 'ok' | 'lagging' | 'stale' | 'no_data'
  }>
}

// ── Index API functions ───────────────────────────────────────

export async function getIndices() {
  return request<IndexDef[]>('/indices')
}

export async function createIndex(body: IndexDefIn) {
  return postJson<IndexDef>('/indices', body)
}

export async function updateIndex(id: number, body: IndexDefIn) {
  return putJson<IndexDef>(`/indices/${id}`, body)
}

export async function deleteIndex(id: number) {
  return deleteReq(`/indices/${id}`)
}

export async function addSubMetric(indexId: number, body: SubMetricIn) {
  return postJson<SubMetricDef>(`/indices/${indexId}/sub-metrics`, body)
}

export async function updateSubMetric(smId: number, body: SubMetricIn) {
  return putJson<SubMetricDef>(`/sub-metrics/${smId}`, body)
}

export async function deleteSubMetric(smId: number) {
  return deleteReq(`/sub-metrics/${smId}`)
}

export async function getCompositeFormula() {
  return request<CompositeFormula>('/system-config/composite-formula')
}

export async function updateCompositeFormula(body: CompositeFormula) {
  return putJson('/system-config/composite-formula', body)
}

export async function getIndexData(year: number, month: number) {
  return request<IndexDataEntryItem[]>(`/index-data/${year}/${month}`)
}

export async function upsertIndexData(payload: {
  period_year: number
  period_month: number
  entries: IndexDataEntryItem[]
}) {
  return putJson('/index-data', payload)
}

export async function getIndexCalc(months = 12) {
  return request<IndexCalcResult>(`/index-calc?months=${months}`)
}

export async function getIndexDailyCalc(
  indexId: number,
  year?: number,
  month?: number,
): Promise<DailyDataPoint[]> {
  const params = new URLSearchParams({ index_id: String(indexId) })
  if (year)  params.set('year',  String(year))
  if (month) params.set('month', String(month))
  return request<DailyDataPoint[]>(`/index-calc/daily?${params}`)
}

export async function getDbTables(): Promise<string[]> {
  return request<string[]>('/db-schema/tables')
}

export async function getDbColumns(table: string): Promise<{ name: string; type: string }[]> {
  return request<{ name: string; type: string }[]>(`/db-schema/columns?table=${encodeURIComponent(table)}`)
}

export async function previewSubMetricSync(smId: number, months = 12) {
  return request<SmSyncItem[]>(`/sub-metrics/${smId}/sync/preview?months=${months}`)
}

export async function syncSubMetric(smId: number, months = 12): Promise<SmSyncResult> {
  const response = await fetch(`${API_BASE_URL}/sub-metrics/${smId}/sync?months=${months}`, {
    method: 'POST', headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await readErrorMessage(response))
  return response.json() as Promise<SmSyncResult>
}

export async function syncSapHarvestPipeline(months = 2): Promise<HarvestPipelineSyncResult> {
  const response = await fetch(`${API_BASE_URL}/sap-harvest/sync?months=${months}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await readErrorMessage(response))
  return response.json() as Promise<HarvestPipelineSyncResult>
}

export async function getSapHarvestPipelineStatus(jobId: string): Promise<HarvestPipelineSyncResult> {
  return request<HarvestPipelineSyncResult>(`/sap-harvest/sync/${jobId}`)
}

export async function getCurrentSapHarvestPipeline(): Promise<HarvestPipelineSyncResult | null> {
  return request<HarvestPipelineSyncResult | null>('/sap-harvest/sync-current')
}

export async function getSapHarvestDailyPreview(days = 7): Promise<HarvestDailyPreviewItem[]> {
  return request<HarvestDailyPreviewItem[]>(`/sap-harvest/daily-preview?days=${days}`)
}

export async function getSapHarvestMonitor(
  refresh = false,
  field?: string,
): Promise<HarvestMonitorResult> {
  const params = new URLSearchParams()
  if (refresh) params.set('refresh', 'true')
  if (field)   params.set('field', field)
  const qs = params.toString()
  return request<HarvestMonitorResult>(`/sap-harvest/monitor${qs ? `?${qs}` : ''}`)
}

export async function previewAgriProduction(months = 12) {
  return request<AgriProductionItem[]>(`/agri-index/production/preview?months=${months}`)
}

export async function syncAgriProduction(subMetricId: number, months = 12): Promise<AgriSyncResult> {
  const response = await fetch(`${API_BASE_URL}/agri-index/production/sync?sub_metric_id=${subMetricId}&months=${months}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await readErrorMessage(response))
  return response.json() as Promise<AgriSyncResult>
}

export async function getSubMetricDetail(indexId: number, year: number, month: number, months = 12) {
  return request<{ index_name: string; sub_metrics: SubMetricTimeSeries[] }>(
    `/index-calc/sub-metrics/${year}/${month}?index_id=${indexId}&months=${months}`,
  )
}

// ── Scheduled Sync types ─────────────────────────────────────

export type ScheduledSyncIn = {
  name: string
  sync_type: 'sub_metric' | 'sap_harvest' | 'agri_production'
  sub_metric_id: number | null
  months: number
  cron_minute: string
  cron_hour: string
  cron_day: string
  cron_month: string
  cron_dow: string
  enabled: boolean
}

export type ScheduledSyncOut = ScheduledSyncIn & {
  id: number
  last_run_at: string | null
  last_status: 'success' | 'failed' | 'running' | null
  last_message: string | null
  created_by: string
  created_at: string
  updated_at: string
}

// ── Teams 通知配置 ────────────────────────────────────────────

export type TeamsConfig = {
  webhook_url: string
  notify_on: string   // "success" | "failure" | "success,failure" | ""
}

export async function getTeamsConfig(): Promise<TeamsConfig> {
  return request<TeamsConfig>('/system-config/teams')
}

export async function updateTeamsConfig(body: TeamsConfig): Promise<TeamsConfig> {
  return putJson<TeamsConfig>('/system-config/teams', body)
}

export async function testTeamsWebhook(): Promise<{ ok: boolean; response: string }> {
  return postJson('/system-config/teams/test', {})
}

export async function getScheduledSyncs(): Promise<ScheduledSyncOut[]> {
  return request<ScheduledSyncOut[]>('/scheduled-syncs')
}

export async function createScheduledSync(body: ScheduledSyncIn): Promise<ScheduledSyncOut> {
  return postJson<ScheduledSyncOut>('/scheduled-syncs', body)
}

export async function updateScheduledSync(id: number, body: ScheduledSyncIn): Promise<ScheduledSyncOut> {
  return putJson<ScheduledSyncOut>(`/scheduled-syncs/${id}`, body)
}

export async function deleteScheduledSync(id: number): Promise<void> {
  return deleteReq(`/scheduled-syncs/${id}`)
}

export async function triggerScheduledSync(id: number): Promise<ScheduledSyncOut> {
  return postJson<ScheduledSyncOut>(`/scheduled-syncs/${id}/run`, {})
}

export type TeamsBotConversation = {
  id: number
  conversation_id: string
  tenant_id: string
  team_id: string
  channel_id: string
  conversation_type: string
  name: string
  user_aad_object_id: string
  user_name: string
  last_seen_at: string
  created_at: string
  updated_at: string
}

export type TeamsBotStatus = {
  app_id_configured: boolean
  app_password_configured: boolean
  validate_incoming: boolean
  messaging_endpoint: string
}

export type IndexNotificationConfig = {
  id: number
  index_code: string
  index_name: string
  teams_conversation_id: number | null
  teams_conversation_name: string
  cron_minute: string
  cron_hour: string
  cron_day: string
  cron_month: string
  cron_dow: string
  enabled: boolean
  last_run_at: string | null
  last_status: 'success' | 'failed' | 'running' | 'skipped' | null
  last_message: string | null
  updated_by: string
  updated_at: string
}

export type IndexNotificationInput = {
  teams_conversation_id: number | null
  cron_minute: string
  cron_hour: string
  cron_day: string
  cron_month: string
  cron_dow: string
  enabled: boolean
}

export async function getTeamsBotStatus(): Promise<TeamsBotStatus> {
  return request<TeamsBotStatus>('/teams-bot/status')
}

export async function getTeamsBotConversations(): Promise<TeamsBotConversation[]> {
  return request<TeamsBotConversation[]>('/teams-bot/conversations')
}

export async function testTeamsBotConversation(id: number): Promise<{ ok: boolean; response: unknown }> {
  return postJson(`/teams-bot/conversations/${id}/test`, {})
}

export async function getIndexNotifications(): Promise<IndexNotificationConfig[]> {
  return request<IndexNotificationConfig[]>('/index-notifications')
}

export async function updateIndexNotification(
  indexCode: string,
  body: IndexNotificationInput,
): Promise<IndexNotificationConfig> {
  return putJson<IndexNotificationConfig>(`/index-notifications/${indexCode}`, body)
}

export async function testIndexNotification(indexCode: string): Promise<IndexNotificationConfig> {
  return postJson<IndexNotificationConfig>(`/index-notifications/${indexCode}/test`, {})
}

export type InitDbPreview = { file: string; size_kb: number; statement_count: number }
export type InitDbResult  = { ok: boolean; executed: number; skipped: number; errors: string[]; message: string }

export async function previewInitDb(): Promise<InitDbPreview> {
  const response = await fetch(`${API_BASE_URL}/admin/init-db/preview`, {
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export async function runInitDb(): Promise<InitDbResult> {
  return postJson<InitDbResult>('/admin/init-db', {})
}

async function putJson<T = { ok: boolean }>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PUT',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await readErrorMessage(response))
  if (response.status === 204) return {} as T
  return response.json() as Promise<T>
}

async function deleteReq(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error(await readErrorMessage(response))
}

async function readErrorMessage(response: Response) {
  try {
    const data = await response.json()
    return data.detail ?? response.statusText
  } catch {
    return response.statusText
  }
}

function isJsonResponse(response: Response) {
  return response.headers.get('content-type')?.includes('application/json') ?? false
}
