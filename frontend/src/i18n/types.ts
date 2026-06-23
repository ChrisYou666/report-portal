export type Language = 'zh' | 'id'

export type ReportTypeKey = '日报' | '周报' | '月报'

export type I18nMessages = {
  languageName: string
  switchLanguage: string
  common: {
    loading: string
    operationFailed: string
  }
  nav: {
    brand: string
    subtitle: string
    dashboard: string
    upload: string
    batches: string
    query: string
    languageZh: string
    languageId: string
  }
  dashboard: {
    eyebrow: string
    title: string
    description: string
    uploadButton: string
    batchesButton: string
    uploadedFiles: string
    uploadBatches: string
    generatedReports: string
    onedriveArchived: string
    loadFailed: string
  }
  upload: {
    title: string
    description: string
    todayUpload: string
    basicInfo: string
    fillOnce: string
    defaultReportName: string
    defaultReportValue: string
    reportType: string
    reportTypes: Record<ReportTypeKey, string>
    department: string
    departmentPlaceholder: string
    selectDepartment: string
    departmentOptions: Record<string, string>
    site: string
    sitePlaceholder: string
    selectSite: string
    siteOptions: Record<string, string>
    reportDate: string
    uploader: string
    selectUploader: string
    remark: string
    chooseFile: string
    selectedFile: string
    supportFiles: string
    selectedFiles: string
    filesUnit: string
    total: string
    invalidFilePrefix: string
    invalidFileSuffix: string
    submit: string
    recentUpload: string
    localRecord: string
    empty: string
    date: string
    status: string
    uploadedStatus: string
    uploadSuccessPrefix: string
    submitting: string
    openFile: string
    requiredReportName: string
    requiredDepartment: string
    requiredDate: string
    requiredUploader: string
    requiredFile: string
  }
  batch: {
    eyebrow: string
    title: string
    description: string
    empty: string
    parse: string
    parsing: string
    detail: string
    reparse: string
    reparsing: string
    uploadedFiles: string
    parseStatus: string
    noParseRecord: string
    loadFailed: string
    actionFailed: string
    actionCompleted: string
    parsingStarted: string
    progress: string
    currentFile: string
    parsedCount: string
    skippedCount: string
    failedCount: string
  }
  query: {
    eyebrow: string
    title: string
    description: string
    subject: string
    subjects: Record<string, string>
    metricName: string
    metricPlaceholder: string
    department: string
    allDepartments: string
    periodType: string
    periods: Record<string, string>
    groupBy: string
    groups: Record<string, string>
    startDate: string
    endDate: string
    site: string
    allSites: string
    division: string
    allDivisions: string
    allBloks: string
    workerType: string
    allWorkerTypes: string
    workerTypes: Record<string, string>
    metrics: Record<string, string>
    metric: string
    value: string
    date: string
    trend: string
    dimension: string
    selectedMetric: string
    presentWorkers: string
    actualWorkers: string
    attendanceRate: string
    source: string
    status: string
    updatedAt: string
    empty: string
    loadFailed: string
    sources: Record<string, string>
  }
  status: Record<string, string>
}

export type UploadMessages = I18nMessages['upload']
