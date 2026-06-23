from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    report_name: Mapped[str] = mapped_column(String(160))
    report_type: Mapped[str] = mapped_column(String(40))
    department: Mapped[str] = mapped_column(String(120))
    site: Mapped[str] = mapped_column(String(120), default="")
    factory: Mapped[str] = mapped_column(String(120), default="")
    report_date: Mapped[date] = mapped_column(Date)
    uploader: Mapped[str] = mapped_column(String(120))
    remark: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    files: Mapped[list["UploadFileRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="selectin",
    )
    parsed_documents: Mapped[list["ParsedDocument"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="selectin",
    )


class UploadFileRecord(Base):
    __tablename__ = "upload_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)
    file_type: Mapped[str] = mapped_column(String(30))
    detected_report_name: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="files")
    parsed_documents: Mapped[list["ParsedDocument"]] = relationship(
        back_populates="file", cascade="all, delete-orphan", lazy="selectin",
    )


class ParsedDocument(Base):
    __tablename__ = "parsed_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("upload_files.id"), index=True)
    parser_type: Mapped[str] = mapped_column(String(40))
    source_path: Mapped[str] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="parsed")
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped[UploadBatch] = relationship(back_populates="parsed_documents")
    file: Mapped[UploadFileRecord] = relationship(back_populates="parsed_documents")
    fields: Mapped[list["ParsedField"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin",
    )
    structured_records: Mapped[list["ParsedStructuredRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin",
    )


class ParsedField(Base):
    __tablename__ = "parsed_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parsed_document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("upload_files.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(40))
    sheet_name: Mapped[str] = mapped_column(String(160), default="")
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    column_index: Mapped[int] = mapped_column(Integer, default=0)
    field_name: Mapped[str] = mapped_column(String(160), default="")
    field_value: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[ParsedDocument] = relationship(back_populates="fields")


class ParsedStructuredRecord(Base):
    __tablename__ = "parsed_structured_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parsed_document_id: Mapped[int] = mapped_column(ForeignKey("parsed_documents.id"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("upload_files.id"), index=True)
    template_name: Mapped[str] = mapped_column(String(160), default="")
    record_type: Mapped[str] = mapped_column(String(80), default="")
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    record_json: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[ParsedDocument] = relationship(back_populates="structured_records")


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("upload_batches.id"), index=True)
    batch_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    parsed_files: Mapped[int] = mapped_column(Integer, default=0)
    skipped_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    current_filename: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(40), default="viewer")
    department: Mapped[str] = mapped_column(String(120), default="")
    site: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ════════════════════════════════════════════════════════════════════════════════
# DIM 主数据层
# ════════════════════════════════════════════════════════════════════════════════

class DimCompany(Base):
    """公司主数据 — 组织架构顶层"""
    __tablename__ = "dim_company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_id: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(60), default="Indonesia")
    is_active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    external_id: Mapped[str] = mapped_column(String(120), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DimSite(Base):
    """园区主数据 — 公司下的农业生产单元"""
    __tablename__ = "dim_site"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True, default="")
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_id: Mapped[str] = mapped_column(String(120), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(60), default="Indonesia")
    is_active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    external_id: Mapped[str] = mapped_column(String(120), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DimFactory(Base):
    """工厂主数据 — 公司下的加工厂（POM/KCP/精炼）"""
    __tablename__ = "dim_factory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True, default="")
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_id: Mapped[str] = mapped_column(String(120), default="")
    factory_type: Mapped[str] = mapped_column(String(40), default="")  # pom | kcp | refinery
    location: Mapped[str] = mapped_column(String(200), default="")
    capacity_ton_per_hour: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    external_id: Mapped[str] = mapped_column(String(120), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DimDivision(Base):
    """小区/Afdeling 主数据 — 园区下的管理单元"""
    __tablename__ = "dim_division"
    __table_args__ = (UniqueConstraint("site_code", "code", name="uq_dim_division_site_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True, default="")
    site_code: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_id: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    external_id: Mapped[str] = mapped_column(String(120), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DimBlok(Base):
    """地块主数据 — 小区下的最小生产单元"""
    __tablename__ = "dim_blok"
    __table_args__ = (UniqueConstraint("site_code", "division_code", "code", name="uq_dim_blok"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_code: Mapped[str] = mapped_column(String(40), index=True, default="")
    site_code: Mapped[str] = mapped_column(String(40), index=True)
    division_code: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    luas_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    planting_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    maturity_stage: Mapped[str] = mapped_column(String(40), default="")  # TM | scout | immature
    palm_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # stems per hectare
    is_active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    external_id: Mapped[str] = mapped_column(String(120), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataSourceConfig(Base):
    __tablename__ = "data_source_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(40))
    host: Mapped[str] = mapped_column(String(255), default="")
    port: Mapped[int] = mapped_column(Integer, default=5432)
    database_name: Mapped[str] = mapped_column(String(120), default="")
    username: Mapped[str] = mapped_column(String(120), default="")
    password_enc: Mapped[str] = mapped_column(Text, default="")
    api_url: Mapped[str] = mapped_column(String(500), default="")
    api_method: Mapped[str] = mapped_column(String(10), default="GET")
    api_headers_enc: Mapped[str] = mapped_column(Text, default="")
    api_response_path: Mapped[str] = mapped_column(String(255), default="")
    sync_query: Mapped[str] = mapped_column(Text, default="")
    target_entity: Mapped[str] = mapped_column(String(40))
    field_mapping: Mapped[str] = mapped_column(Text, default="{}")
    is_active: Mapped[bool] = mapped_column(default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_status: Mapped[str] = mapped_column(String(40), default="")
    last_sync_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ════════════════════════════════════════════════════════════════════════════════
# DWD 明细数据层
#
# 设计原则：
#   1. 粒度明确 — 日表存日事实，月表存月事实，不混用
#   2. 窄表优先 — 用维度列（work_type/material_category）代替横向展开的宽列
#   3. 只存原始事实 — 完成率、差异等派生指标在 DWS 层用 SQL 计算
#   4. 命名规范 — dwd_agri_* / dwd_factory_*，清晰区分业务域
#
# 公共列说明（每张表都有）：
#   batch_id / file_id / source_record_id — 可空，手动录入时为 NULL
#   site    — 园区/工厂，所有多园区聚合查询的核心维度
#   quality_status / quality_message — 数据质量标记
# ════════════════════════════════════════════════════════════════════════════════


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 铲果与产量
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriHarvestDaily(Base):
    """
    铲果日产量
    粒度：日 × 园区 × 小区
    只存当日实际产量和月累计，月度目标(BBC/预算)独立放 DwdAgriProductionTargetMonthly
    """
    __tablename__ = "dwd_agri_harvest_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", name="uq_agri_harvest_daily"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    mature_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtd_actual_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriProductionTargetMonthly(Base):
    """
    月度产量目标（BBC + 预算）
    粒度：月 × 园区 × 小区  （report_date 存月份首日，如 2025-01-01）
    合并原来的 dwd_production_budget_monthly + dwd_production_estimate_daily 中的月目标部分
    """
    __tablename__ = "dwd_agri_production_target_monthly"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", name="uq_agri_production_target"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    mature_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbc_ton: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_ton: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yield_ton_per_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriAkpDensityDaily(Base):
    """
    AKP 铲果密度采样
    粒度：日 × 园区 × 小区 × Blok（采样级）
    """
    __tablename__ = "dwd_agri_akp_density_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", "blok", name="uq_agri_akp_density"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    blok: Mapped[str] = mapped_column(String(80), default="")
    sap: Mapped[str] = mapped_column(String(80), default="")
    luas_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tt_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    panen_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    akp_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    panen_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    jumlah_janjang: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tk_panen: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    keterangan: Mapped[str] = mapped_column(String(255), default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriHarvestLossDaily(Base):
    """
    铲果损失检查（QC）
    粒度：检查日 × 园区 × 小区 × Blok
    """
    __tablename__ = "dwd_agri_harvest_loss_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", "blok", name="uq_agri_harvest_loss"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    blok: Mapped[str] = mapped_column(String(80), default="")
    inspector: Mapped[str] = mapped_column(String(120), default="")
    bjr_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    harvested_bunches: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    harvested_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_bunches: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_bunch_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_loose_fruit_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lost_loose_fruit_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 损失率在 DWS 层计算，此处只存原始数量
    ditch_bunch_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ditch_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rotten_bunch_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rotten_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fresh_loose_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fresh_loose_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    black_loose_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    black_loose_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriHarvestRotationMonthly(Base):
    """
    铲果周期 Rotasi Panen
    粒度：月 × 园区 × 小区 × Blok（report_date 存月份首日）
    """
    __tablename__ = "dwd_agri_harvest_rotation_monthly"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", "blok", name="uq_agri_harvest_rotation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    blok: Mapped[str] = mapped_column(String(80), default="")
    maturity_stage: Mapped[str] = mapped_column(String(40), default="")
    planting_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    palm_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yph: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prev_month_days_unharvested: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_month_days_unharvested: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_round_harvested_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtd_harvested_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    harvest_round_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriHarvestRotationDistDaily(Base):
    """
    铲果周期分布统计
    粒度：日 × 园区 × 小区
    铲果天数分区段统计，便于分析铲果频率分布
    """
    __tablename__ = "dwd_agri_harvest_rotation_dist_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", name="uq_agri_harvest_rot_dist"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    total_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d_le8_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d_le8_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d9_10_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d9_10_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d11_15_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d11_15_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d16_20_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d16_20_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d21_25_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d21_25_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d_gt25_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    d_gt25_bloks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 各区间占比在 DWS 层计算
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 出勤
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriAttendanceDaily(Base):
    """
    铲果工/养护工出勤
    粒度：日 × 园区 × 小区 × 工种
    worker_type: harvester（铲果工）| maintenance（养护工）
    """
    __tablename__ = "dwd_agri_attendance_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", "worker_type", name="uq_agri_attendance"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    worker_type: Mapped[str] = mapped_column(String(40), default="")
    managed_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    required_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    own_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contractor_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    own_present: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contractor_present: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_present: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 出勤率 = total_present / (own_total + contractor_total)，DWS 层计算
    leave_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annual_leave_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sick_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    absent_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 养护
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriMaintenanceDaily(Base):
    """
    养护作业日报（窄表设计）
    粒度：日 × 园区 × 小区 × 作业类型
    work_type: pruning（铲叶）| weeding_cpt（全面除草）|
               lalang_control（Lalang控制）| selective_spray（选择性打药）
    新增作业类型只需插入新的 work_type 值，无需改表结构
    """
    __tablename__ = "dwd_agri_maintenance_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", "work_type", name="uq_agri_maintenance"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    work_type: Mapped[str] = mapped_column(String(60), default="")
    managed_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_completed_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtd_completed_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 完成率 = daily_completed_ha / managed_area_ha，DWS 层计算
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriFertilizationDaily(Base):
    """
    施肥进度统计
    粒度：日 × 园区 × 小区
    月度目标施肥量也记录在此（每月初更新），日进度与月目标在同一粒度下可关联
    """
    __tablename__ = "dwd_agri_fertilization_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", name="uq_agri_fertilization"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    daily_target_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_actual_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtd_target_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtd_actual_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_target_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monthly_target_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 各种完成率在 DWS 层计算
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 库存（物料统一表）
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriMaterialInventoryDaily(Base):
    """
    农业物料库存（合并化肥 + 农药 + 铲果工具）
    粒度：日 × 园区 × 物料编码 × 库位
    material_category: fertilizer（化肥）| pesticide（农药）| tools（铲果工具）
    统一一张表而非三张，新增物料类别只加 category 值即可
    """
    __tablename__ = "dwd_agri_material_inventory_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "material_code", "storage_location", name="uq_agri_material_inv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    material_category: Mapped[str] = mapped_column(String(40), default="")
    material_code: Mapped[str] = mapped_column(String(80), default="")
    material_name: Mapped[str] = mapped_column(String(200), default="")
    unit: Mapped[str] = mapped_column(String(20), default="")
    storage_location: Mapped[str] = mapped_column(String(80), default="")
    opening_stock: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_inbound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_outbound: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closing_stock: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriOilStorageDaily(Base):
    """
    园区油库监控
    粒度：日 × 园区 × 油罐（tank_code: tank1/tank2/drum）
    早晚各一次读数，用 reading_time 区分：morning / evening
    """
    __tablename__ = "dwd_agri_oil_storage_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "tank_code", "reading_time", name="uq_agri_oil_storage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    tank_code: Mapped[str] = mapped_column(String(20), default="")
    reading_time: Mapped[str] = mapped_column(String(10), default="")  # morning / evening
    reading_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 打尺测量值（cm）
    stock_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 由打尺值换算的升数
    sap_book_stock: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    inbound_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_outbound_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    system_outbound_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 机械
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriEquipmentDaily(Base):
    """
    设备状态与维修跟踪
    粒度：日 × 园区 × 设备编号
    """
    __tablename__ = "dwd_agri_equipment_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "equipment_code", name="uq_agri_equipment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    equipment_category: Mapped[str] = mapped_column(String(40), default="")
    equipment_code: Mapped[str] = mapped_column(String(80), default="")
    equipment_type: Mapped[str] = mapped_column(String(40), default="")
    equipment_model: Mapped[str] = mapped_column(String(80), default="")
    is_normal: Mapped[Optional[bool]] = mapped_column(nullable=True)
    is_working: Mapped[Optional[bool]] = mapped_column(nullable=True)
    has_maintenance: Mapped[Optional[bool]] = mapped_column(nullable=True)
    damage_description: Mapped[str] = mapped_column(Text, default="")
    repair_location: Mapped[str] = mapped_column(String(80), default="")
    breakdown_time: Mapped[str] = mapped_column(String(30), default="")
    estimated_repair_time: Mapped[str] = mapped_column(String(30), default="")
    repair_status: Mapped[str] = mapped_column(String(40), default="")
    downtime_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriEquipmentFuelMonthly(Base):
    """
    机械HM和油耗监控（月度）
    粒度：月 × 园区 × 设备编号（report_date 存月份首日）
    """
    __tablename__ = "dwd_agri_equipment_fuel_monthly"
    __table_args__ = (UniqueConstraint("report_date", "site", "equipment_code", name="uq_agri_equipment_fuel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    equipment_type: Mapped[str] = mapped_column(String(40), default="")
    equipment_code: Mapped[str] = mapped_column(String(80), default="")
    hm_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fuel_liters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calibration_hm_per_liter: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # actual hm_per_liter 和 variance 在 DWS 计算
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 运输
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriTbsTransportDaily(Base):
    """
    TBS 送厂运输明细（事务级）
    粒度：运输单（SPB）× 日期 × 园区
    """
    __tablename__ = "dwd_agri_tbs_transport_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "spb_no", name="uq_agri_tbs_transport"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    spb_no: Mapped[str] = mapped_column(String(80), default="")
    destination_factory: Mapped[str] = mapped_column(String(120), default="")
    trip_no: Mapped[str] = mapped_column(String(40), default="")
    driver_name: Mapped[str] = mapped_column(String(120), default="")
    license_plate: Mapped[str] = mapped_column(String(40), default="")
    vehicle_code: Mapped[str] = mapped_column(String(40), default="")
    source_division: Mapped[str] = mapped_column(String(80), default="")
    bunch_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loose_fruit_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    seal_time: Mapped[str] = mapped_column(String(30), default="")
    security_depart_time: Mapped[str] = mapped_column(String(30), default="")
    weighbridge_time: Mapped[str] = mapped_column(String(30), default="")
    weighbridge_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriHarvestPlanDaily(Base):
    """
    当天铲果运输计划
    粒度：日 × 园区 × 小区
    """
    __tablename__ = "dwd_agri_harvest_plan_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "division", name="uq_agri_harvest_plan"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    division: Mapped[str] = mapped_column(String(80), default="")
    harvest_area_ha: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    akp_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leftover_h1_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leftover_h2_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leftover_h3_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    planned_harvest_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    planned_trips: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    planned_delivery_time: Mapped[str] = mapped_column(String(30), default="")
    leftover_remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ────────────────────────────────────────────────────────────────────────────────
# 农业 — 其他
# ────────────────────────────────────────────────────────────────────────────────

class DwdAgriRainfallDaily(Base):
    """
    降雨量日报
    粒度：日 × 园区
    """
    __tablename__ = "dwd_agri_rainfall_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", name="uq_agri_rainfall"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    rainfall_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mtd_rainfall_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rain_start_time: Mapped[str] = mapped_column(String(20), default="")
    rain_end_time: Mapped[str] = mapped_column(String(20), default="")
    duration_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdAgriSeedlingTransportDaily(Base):
    """
    每日运苗情况统计（事务级）
    粒度：运苗单（MRIS）× 日期 × 园区
    """
    __tablename__ = "dwd_agri_seedling_transport_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "mris_no", name="uq_agri_seedling_transport"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    mris_no: Mapped[str] = mapped_column(String(80), default="")
    transport_purpose: Mapped[str] = mapped_column(String(120), default="")
    destination_site: Mapped[str] = mapped_column(String(120), default="")
    destination_blok: Mapped[str] = mapped_column(String(80), default="")
    daily_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ════════════════════════════════════════════════════════════════════════════════
# 工厂 DWD
# ════════════════════════════════════════════════════════════════════════════════

class DwdFactoryGradingDaily(Base):
    """
    分级报告（事务级）
    粒度：收果单（SPB）× 日期 × 工厂
    """
    __tablename__ = "dwd_factory_grading_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "spb_no", name="uq_factory_grading"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    spb_no: Mapped[str] = mapped_column(String(80), default="")
    source_company: Mapped[str] = mapped_column(String(80), default="")
    source_estate_division: Mapped[str] = mapped_column(String(80), default="")
    vehicle: Mapped[str] = mapped_column(String(40), default="")
    blok: Mapped[str] = mapped_column(String(80), default="")
    bunch_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 各等级果串数量（原始计数，不存百分比）
    unripe_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    under_ripe_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ripe_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    over_ripe_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    empty_bunch_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    parthenocarpic_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dura_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    long_stalk_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    small_fruit_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rotten_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brondolan_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 重量（吨）
    weight_before_grading_ton: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_after_grading_ton: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rejected_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 各级别百分比和扣重率在 DWS 计算
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdFactoryWeighbridgeDaily(Base):
    """
    地磅单（事务级）
    粒度：票据号 × 日期 × 工厂
    """
    __tablename__ = "dwd_factory_weighbridge_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "ticket_no", name="uq_factory_weighbridge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    ticket_no: Mapped[str] = mapped_column(String(80), default="")
    direction: Mapped[str] = mapped_column(String(10), default="")
    transaction_type: Mapped[str] = mapped_column(String(40), default="")
    product: Mapped[str] = mapped_column(String(80), default="")
    vehicle: Mapped[str] = mapped_column(String(40), default="")
    customer: Mapped[str] = mapped_column(String(120), default="")
    transporter: Mapped[str] = mapped_column(String(120), default="")
    gross_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tare_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    netto_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bunch_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loose_fruit_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bjr_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    out_items: Mapped[str] = mapped_column(String(200), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdFactoryPomProductionDaily(Base):
    """
    POM 毛棕榈油厂生产绩效
    粒度：日 × 工厂 × 统计周期（today/monthly）
    period_type: today（当日）| monthly（月累计）
    """
    __tablename__ = "dwd_factory_pom_production_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "period_type", name="uq_factory_pom_production"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    period_type: Mapped[str] = mapped_column(String(20), default="today")
    responsible_person: Mapped[str] = mapped_column(String(120), default="")
    # FFB 收料（各来源分开，便于来源分析）
    own_ffb_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    own_ffb_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plasma_ffb_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plasma_ffb_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    group_ffb_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    group_ffb_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    external_ffb_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    external_ffb_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ffb_processed_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ffb_processed_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ffb_balance_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # CPO 产出
    cpo_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpo_ffa_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpo_moisture_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpo_impurity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pao_blend_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pao_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # CPO 出油率在 DWS 计算（= cpo_production / ffb_processed）
    # Kernel 产出
    kernel_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kernel_moisture_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kernel_impurity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shell_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 销售
    cpo_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    miko_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    kernel_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 运行效率
    processing_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    downtime_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    downtime_reason: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdFactoryKcpProductionDaily(Base):
    """
    KCP 棕仁榨油厂生产绩效
    粒度：日 × 工厂 × 统计周期（today/monthly）
    """
    __tablename__ = "dwd_factory_kcp_production_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "period_type", name="uq_factory_kcp_production"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    period_type: Mapped[str] = mapped_column(String(20), default="today")
    responsible_person: Mapped[str] = mapped_column(String(120), default="")
    own_pk_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    own_pk_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    group_pk_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    group_pk_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    external_pk_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    external_pk_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pk_processed_before_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pk_processed_after_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pk_balance_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pko_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pko_ffa_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pko_moisture_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pko_impurity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    line1_oil_loss_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    line2_oil_loss_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pke_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pke_bags: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    external_crude_meal_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pko_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pke_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    processing_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    downtime_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    downtime_reason: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdFactoryRefineryProductionDaily(Base):
    """
    精炼与包装生产绩效
    粒度：日 × 工厂 × 统计周期（today/monthly）
    """
    __tablename__ = "dwd_factory_refinery_production_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "period_type", name="uq_factory_refinery_production"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    period_type: Mapped[str] = mapped_column(String(20), default="today")
    responsible_person: Mapped[str] = mapped_column(String(120), default="")
    # 原料投入
    cpo_low_acid_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpo_high_acid_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpko_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    olein_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stearin_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdpo_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdst_tank_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdpol_tank_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_input_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 产品产出
    rbdpo_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdpko_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pfad_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pkfad_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdol_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdst_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oilku_1l_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oilku_2l_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_production_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit_processing_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 得率 = total_production / total_input，DWS 层计算
    # 销售
    rbdpo_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdpo_sales_pu_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdpo_sales_asp_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdpko_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pfad_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pkfad_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdol_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rbdst_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oilku_1l_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    oilku_2l_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_sales_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DwdFactoryProductInventoryDaily(Base):
    """
    工厂成品库存
    粒度：日 × 工厂 × 产品类型 × 产品规格 × 罐号
    """
    __tablename__ = "dwd_factory_product_inventory_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "product_type", "product_spec", "tank_no", name="uq_factory_product_inv"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    product_type: Mapped[str] = mapped_column(String(40), default="")
    product_spec: Mapped[str] = mapped_column(String(80), default="")
    storage_location: Mapped[str] = mapped_column(String(80), default="")
    tank_no: Mapped[str] = mapped_column(String(40), default="")
    capacity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_stock: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="")
    ffa_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moisture_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impurity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eom_forecast_stock: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ════════════════════════════════════════════════════════════════════════════════
# 经营指数体系
# ════════════════════════════════════════════════════════════════════════════════

class IndexDefinition(Base):
    """指数定义 — 每条记录代表一个子指数（如农业、期货、工业）"""
    __tablename__ = "index_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    formula: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    # 计算粒度：monthly（按月，默认）| daily（按日，指数值每天更新）
    granularity: Mapped[str] = mapped_column(String(20), default="monthly")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sub_metrics: Mapped[list["IndexSubMetric"]] = relationship(
        back_populates="index_def", cascade="all, delete-orphan",
        lazy="selectin", order_by="IndexSubMetric.sort_order",
    )


class IndexSubMetric(Base):
    """指数分项 — 每个子指数下的原始输入变量（如 A、B、C 或自定义名称）"""
    __tablename__ = "index_sub_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("index_definitions.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120), default="")
    unit: Mapped[str] = mapped_column(String(40), default="")
    source_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual | db_sync | fixed
    fixed_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    db_table: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, default=None)
    db_field: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, default=None)
    db_aggregation: Mapped[str] = mapped_column(String(20), default="SUM")
    db_date_col: Mapped[str] = mapped_column(String(120), default="report_date")
    db_extra_where: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    # 财年累计模式：设置财年起始月（1-12），聚合区间从该财年起始月1日到当月末
    # 例：fiscal_start_month=9 表示每年9月开始的财年
    fiscal_start_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    index_def: Mapped["IndexDefinition"] = relationship(back_populates="sub_metrics")


class IndexDataEntry(Base):
    """月度分项数据 — 每条记录是某分项在某年某月的录入值"""
    __tablename__ = "index_data_entries"
    __table_args__ = (UniqueConstraint("sub_metric_id", "period_year", "period_month", name="uq_index_data_entry"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sub_metric_id: Mapped[int] = mapped_column(ForeignKey("index_sub_metrics.id"), index=True)
    period_year: Mapped[int] = mapped_column(Integer, index=True)
    period_month: Mapped[int] = mapped_column(Integer, index=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemConfig(Base):
    """系统配置 — 键值对存储（如合成指数公式）"""
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduledSync(Base):
    """定时同步任务配置"""
    __tablename__ = "scheduled_syncs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    sync_type: Mapped[str] = mapped_column(String(40))       # sub_metric | sap_harvest | agri_production
    sub_metric_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    months: Mapped[int] = mapped_column(Integer, default=12)
    # 调度：cron 五字段 "分 时 日 月 周"
    cron_minute: Mapped[str] = mapped_column(String(20), default="0")
    cron_hour: Mapped[str] = mapped_column(String(20), default="2")
    cron_day: Mapped[str] = mapped_column(String(20), default="*")
    cron_month: Mapped[str] = mapped_column(String(20), default="*")
    cron_dow: Mapped[str] = mapped_column(String(20), default="*")  # day of week
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # success|failed|running
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TeamsBotConversation(Base):
    """Teams Bot 捕获到的聊天或频道会话，用于后续主动推送。"""
    __tablename__ = "teams_bot_conversations"
    __table_args__ = (UniqueConstraint("conversation_id", name="uq_teams_bot_conversation_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[str] = mapped_column(String(260), index=True)
    service_url: Mapped[str] = mapped_column(Text)
    tenant_id: Mapped[str] = mapped_column(String(120), default="")
    team_id: Mapped[str] = mapped_column(String(160), default="")
    channel_id: Mapped[str] = mapped_column(String(160), default="")
    conversation_type: Mapped[str] = mapped_column(String(40), default="")
    name: Mapped[str] = mapped_column(String(240), default="")
    user_aad_object_id: Mapped[str] = mapped_column(String(160), default="")
    user_name: Mapped[str] = mapped_column(String(240), default="")
    raw_activity: Mapped[str] = mapped_column(Text, default="")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IndexNotificationConfig(Base):
    """每个经营指标的 Teams Bot 定时通知配置。"""
    __tablename__ = "index_notification_configs"
    __table_args__ = (UniqueConstraint("index_code", name="uq_index_notification_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    index_code: Mapped[str] = mapped_column(String(40), index=True)
    index_name: Mapped[str] = mapped_column(String(120))
    teams_conversation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cron_minute: Mapped[str] = mapped_column(String(20), default="0")
    cron_hour: Mapped[str] = mapped_column(String(20), default="9")
    cron_day: Mapped[str] = mapped_column(String(20), default="*")
    cron_month: Mapped[str] = mapped_column(String(20), default="*")
    cron_dow: Mapped[str] = mapped_column(String(20), default="*")
    enabled: Mapped[bool] = mapped_column(default=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DwdFactoryChemicalConsumptionDaily(Base):
    """
    工业药剂消耗（窄表设计）
    粒度：日 × 工厂 × 药剂编码
    chemical_code: caustic_soda | aluminium_sulfate | aero_asc | salt |
                   polymer | scf | oxifite | gr | ps05
    新增药剂类型无需改表结构
    """
    __tablename__ = "dwd_factory_chemical_consumption_daily"
    __table_args__ = (UniqueConstraint("report_date", "site", "chemical_code", name="uq_factory_chemical"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_batches.id"), nullable=True)
    batch_no: Mapped[str] = mapped_column(String(40), default="")
    file_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upload_files.id"), nullable=True)
    source_record_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parsed_structured_records.id"), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    site: Mapped[str] = mapped_column(String(120), default="", index=True)
    chemical_code: Mapped[str] = mapped_column(String(60), default="")
    chemical_name: Mapped[str] = mapped_column(String(120), default="")
    unit: Mapped[str] = mapped_column(String(20), default="kg")
    consumption_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), default="ok")
    quality_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
