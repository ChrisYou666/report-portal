from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UploadFileOut(BaseModel):
    id: int
    original_filename: str
    stored_path: str
    file_size: int
    file_type: str
    detected_report_name: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchOut(BaseModel):
    id: int
    batch_no: str
    report_name: str
    report_type: str
    department: str
    site: str
    factory: str
    report_date: date
    uploader: str
    remark: str
    status: str
    created_at: datetime
    files: list[UploadFileOut]

    model_config = ConfigDict(from_attributes=True)


class ActionResult(BaseModel):
    batch_no: str
    status: str
    message: str


class HarvestReportLinks(BaseModel):
    html: str = ""
    xlsx: str = ""
    png: str = ""


class HarvestReportStatus(BaseModel):
    report_name: str
    latest_report_date: Optional[date] = None
    latest_batch_no: str = ""
    latest_batch_status: str = ""
    available: bool = False
    links: HarvestReportLinks = Field(default_factory=HarvestReportLinks)
    message: str = ""


class ParseProgressOut(BaseModel):
    batch_no: str
    status: str
    total_files: int
    processed_files: int
    parsed_files: int
    skipped_files: int
    failed_files: int
    current_filename: str
    message: str
    error_message: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadOptions(BaseModel):
    report_types: list[str]
    uploaders: list[str]
    allowed_extensions: list[str]
    departments: list[str]
    sites: list[str]


class MetricItem(BaseModel):
    metric_name: str
    metric_value: str
    unit: str
    date: str
    department: str
    source: str
    status: str
    updated_at: str


class MetricCard(BaseModel):
    label: str
    value: str
    unit: str = ""


class MetricTrendPoint(BaseModel):
    period: str
    value: float


class MetricAnalysisRow(BaseModel):
    dimension: str
    metric_value: float
    unit: str
    panen_kg: Optional[float] = None
    jumlah_janjang: Optional[float] = None
    akp_percent: Optional[float] = None
    luas_ha: Optional[float] = None
    worker_type: Optional[str] = None
    actual_workers: Optional[float] = None
    present_workers: Optional[float] = None
    attendance_rate: Optional[float] = None
    actual_today_ton: Optional[float] = None
    actual_to_date_ton: Optional[float] = None
    bbc_ton: Optional[float] = None
    daily_target_ton: Optional[float] = None
    actual_vs_bbc_percent: Optional[float] = None


class DashboardStats(BaseModel):
    today_production_ton: Optional[float] = None
    mtd_production_ton: Optional[float] = None
    today_attendance_rate: Optional[float] = None
    data_date: Optional[date] = None
    total_batches: int = 0
    parsed_batches: int = 0


class MetricAnalysisResponse(BaseModel):
    subject: str
    metric: str
    period_type: str
    group_by: str
    cards: list[MetricCard]
    trends: list[MetricTrendPoint]
    rows: list[MetricAnalysisRow]


class MetricDimensionOptions(BaseModel):
    sites: list[str]
    divisions: list[str]
    bloks: list[str]
    worker_types: list[str]


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    display_name: str
    role: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    department: str
    site: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "viewer"
    department: str = ""
    site: str = ""


class UserUpdate(BaseModel):
    password: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    site: Optional[str] = None
    is_active: Optional[bool] = None
