from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DwdAgriAkpDensityDaily, DwdAgriAttendanceDaily, DwdAgriHarvestDaily, UploadBatch
from app.schemas import DashboardStats, MetricAnalysisResponse, MetricAnalysisRow, MetricCard, MetricDimensionOptions, MetricTrendPoint

router = APIRouter(tags=["query"])

AKP_METRICS = {"panen_kg", "jumlah_janjang", "akp_percent", "luas_ha"}
ATTENDANCE_METRICS = {"attendance_rate", "present_workers", "actual_workers"}
PRODUCTION_METRICS = {"actual_today_ton", "actual_to_date_ton", "bbc_ton", "daily_target_ton", "actual_vs_bbc_percent"}


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)) -> DashboardStats:
    # 新模型：dwd_agri_harvest_daily，字段 actual_kg / mtd_actual_kg
    latest_prod_date: Optional[date] = db.scalar(
        select(func.max(DwdAgriHarvestDaily.report_date))
    )
    today_production = 0.0
    mtd_production = 0.0
    if latest_prod_date:
        prod_records = list(
            db.scalars(
                select(DwdAgriHarvestDaily).where(DwdAgriHarvestDaily.report_date == latest_prod_date)
            ).all()
        )
        today_production = sum_float(r.actual_kg for r in prod_records)
        mtd_production = sum_float(r.mtd_actual_kg for r in prod_records)

    # 新模型：dwd_agri_attendance_daily，字段 own_total + contractor_total / total_present
    latest_att_date: Optional[date] = db.scalar(
        select(func.max(DwdAgriAttendanceDaily.report_date))
    )
    today_attendance_rate = None
    if latest_att_date:
        att_records = list(
            db.scalars(
                select(DwdAgriAttendanceDaily).where(DwdAgriAttendanceDaily.report_date == latest_att_date)
            ).all()
        )
        actual = sum_float((r.own_total or 0) + (r.contractor_total or 0) for r in att_records)
        present = sum_float(r.total_present for r in att_records)
        if actual > 0:
            today_attendance_rate = round(present / actual * 100, 1)

    total_batches: int = db.scalar(select(func.count(UploadBatch.id))) or 0
    parsed_batches: int = db.scalar(
        select(func.count(UploadBatch.id)).where(UploadBatch.status == "parsed")
    ) or 0

    return DashboardStats(
        today_production_ton=round(today_production / 1000, 2) if today_production else None,
        mtd_production_ton=round(mtd_production / 1000, 2) if mtd_production else None,
        today_attendance_rate=today_attendance_rate,
        data_date=latest_prod_date,
        total_batches=total_batches,
        parsed_batches=parsed_batches,
    )


@router.get("/query/dimensions", response_model=MetricDimensionOptions)
def query_dimensions(db: Session = Depends(get_db)) -> MetricDimensionOptions:
    akp_sites = db.scalars(select(DwdAgriAkpDensityDaily.site).distinct()).all()
    attendance_sites = db.scalars(select(DwdAgriAttendanceDaily.site).distinct()).all()
    divisions = db.scalars(
        select(DwdAgriAkpDensityDaily.division).distinct()
    ).all()
    bloks = db.scalars(
        select(DwdAgriAkpDensityDaily.blok).distinct()
    ).all()
    worker_types = db.scalars(
        select(DwdAgriAttendanceDaily.worker_type).distinct()
    ).all()
    return MetricDimensionOptions(
        sites=sorted(clean_options([*akp_sites, *attendance_sites])),
        divisions=sorted(clean_options(divisions)),
        bloks=sorted(option for option in clean_options(bloks) if not is_total_label(option)),
        worker_types=sorted(clean_options(worker_types)),
    )


@router.get("/query/analysis", response_model=MetricAnalysisResponse)
def query_analysis(
    subject: str = Query("production_monitoring"),
    metric: str = Query("actual_today_ton"),
    period_type: str = Query("day"),
    group_by: str = Query("division"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    site: str = "",
    division: str = "",
    blok: str = "",
    worker_type: str = "",
    db: Session = Depends(get_db),
) -> MetricAnalysisResponse:
    if subject == "attendance":
        return query_attendance_analysis(
            db=db,
            metric=metric if metric in ATTENDANCE_METRICS else "attendance_rate",
            period_type=period_type,
            group_by=group_by,
            start_date=start_date,
            end_date=end_date,
            site=site,
            worker_type=worker_type,
        )

    if subject == "akp_density":
        return query_akp_analysis(
            db=db,
            metric=metric if metric in AKP_METRICS else "panen_kg",
            period_type=period_type,
            group_by=group_by,
            start_date=start_date,
            end_date=end_date,
            site=site,
            division=division,
            blok=blok,
        )

    return query_production_analysis(
        db=db,
        metric=metric if metric in PRODUCTION_METRICS else "actual_today_ton",
        period_type=period_type,
        group_by=group_by,
        start_date=start_date,
        end_date=end_date,
        site=site,
        division=division,
    )


def query_akp_analysis(
    *,
    db: Session,
    metric: str,
    period_type: str,
    group_by: str,
    start_date: Optional[date],
    end_date: Optional[date],
    site: str,
    division: str,
    blok: str,
) -> MetricAnalysisResponse:
    statement = select(DwdAgriAkpDensityDaily)
    if start_date:
        statement = statement.where(DwdAgriAkpDensityDaily.report_date >= start_date)
    if end_date:
        statement = statement.where(DwdAgriAkpDensityDaily.report_date <= end_date)
    if site:
        statement = statement.where(DwdAgriAkpDensityDaily.site == site)
    if division:
        statement = statement.where(DwdAgriAkpDensityDaily.division == division)
    if blok:
        statement = statement.where(DwdAgriAkpDensityDaily.blok == blok)

    records = list(db.scalars(statement).all())
    groups: dict[str, list[DwdAgriAkpDensityDaily]] = defaultdict(list)
    trends: dict[str, list[DwdAgriAkpDensityDaily]] = defaultdict(list)
    for record in records:
        groups[akp_dimension(record, group_by)].append(record)
        trends[period_key(record.report_date, period_type)].append(record)

    rows = [
        build_akp_row(dimension, metric, rows)
        for dimension, rows in sorted(groups.items(), key=lambda item: item[0])
    ]
    trend_points = [
        MetricTrendPoint(period=period, value=metric_value(metric, build_akp_totals(rows)))
        for period, rows in sorted(trends.items(), key=lambda item: item[0])
    ]
    totals = build_akp_totals(records)
    return MetricAnalysisResponse(
        subject="akp_density",
        metric=metric,
        period_type=normalize_period(period_type),
        group_by=group_by,
        cards=[
            MetricCard(label="Panen Kg", value=format_number(totals["panen_kg"]), unit="kg"),
            MetricCard(label="Janjang", value=format_number(totals["jumlah_janjang"])),
            MetricCard(label="平均 AKP", value=format_number(totals["akp_percent"]), unit="%"),
            MetricCard(label="Luas Ha", value=format_number(totals["luas_ha"]), unit="ha"),
        ],
        trends=trend_points,
        rows=rows,
    )


def query_attendance_analysis(
    *,
    db: Session,
    metric: str,
    period_type: str,
    group_by: str,
    start_date: Optional[date],
    end_date: Optional[date],
    site: str,
    worker_type: str,
) -> MetricAnalysisResponse:
    statement = select(DwdAgriAttendanceDaily).where(
        DwdAgriAttendanceDaily.section == "daily_attendance",
        DwdAgriAttendanceDaily.row_label == "detail",
    )
    if start_date:
        statement = statement.where(DwdAgriAttendanceDaily.report_date >= start_date)
    if end_date:
        statement = statement.where(DwdAgriAttendanceDaily.report_date <= end_date)
    if site:
        statement = statement.where(DwdAgriAttendanceDaily.site == site)
    if worker_type:
        statement = statement.where(DwdAgriAttendanceDaily.worker_type == worker_type)

    records = list(db.scalars(statement).all())
    groups: dict[str, list[DwdAgriAttendanceDaily]] = defaultdict(list)
    trends: dict[str, list[DwdAgriAttendanceDaily]] = defaultdict(list)
    for record in records:
        groups[attendance_dimension(record, group_by)].append(record)
        trends[period_key(record.report_date, period_type)].append(record)

    rows = [
        build_attendance_row(dimension, metric, rows)
        for dimension, rows in sorted(groups.items(), key=lambda item: item[0])
    ]
    trend_points = [
        MetricTrendPoint(period=period, value=metric_value(metric, build_attendance_totals(rows)))
        for period, rows in sorted(trends.items(), key=lambda item: item[0])
    ]
    totals = build_attendance_totals(records)
    return MetricAnalysisResponse(
        subject="attendance",
        metric=metric,
        period_type=normalize_period(period_type),
        group_by=group_by,
        cards=[
            MetricCard(label="出勤率", value=format_number(totals["attendance_rate"]), unit="%"),
            MetricCard(label="出勤人数", value=format_number(totals["present_workers"])),
            MetricCard(label="实际人数", value=format_number(totals["actual_workers"])),
            MetricCard(label="记录行数", value=str(len(records))),
        ],
        trends=trend_points,
        rows=rows,
    )


def build_akp_row(dimension: str, metric: str, rows: list[DwdAgriAkpDensityDaily]) -> MetricAnalysisRow:
    totals = build_akp_totals(rows)
    return MetricAnalysisRow(
        dimension=dimension,
        metric_value=metric_value(metric, totals),
        unit=metric_unit(metric),
        panen_kg=totals["panen_kg"],
        jumlah_janjang=totals["jumlah_janjang"],
        akp_percent=totals["akp_percent"],
        luas_ha=totals["luas_ha"],
    )


def build_attendance_row(dimension: str, metric: str, rows: list[DwdAgriAttendanceDaily]) -> MetricAnalysisRow:
    totals = build_attendance_totals(rows)
    worker_types = {row.worker_type for row in rows if row.worker_type}
    return MetricAnalysisRow(
        dimension=dimension,
        metric_value=metric_value(metric, totals),
        unit=metric_unit(metric),
        worker_type=", ".join(sorted(worker_types)) if worker_types else None,
        actual_workers=totals["actual_workers"],
        present_workers=totals["present_workers"],
        attendance_rate=totals["attendance_rate"],
        luas_ha=totals["luas_ha"],
    )


def build_akp_totals(rows: list[DwdAgriAkpDensityDaily]) -> dict[str, float]:
    akp_values = [row.akp_percent for row in rows if row.akp_percent is not None]
    return {
        "panen_kg": sum_float(row.panen_kg for row in rows),
        "jumlah_janjang": sum_float(row.jumlah_janjang for row in rows),
        "akp_percent": sum(akp_values) / len(akp_values) if akp_values else 0,
        "luas_ha": sum_float(row.luas_ha for row in rows),
    }


def build_attendance_totals(rows: list[DwdAgriAttendanceDaily]) -> dict[str, float]:
    actual_workers = sum_float(row.actual_total for row in rows)
    present_workers = sum_float(row.total_present for row in rows)
    return {
        "actual_workers": actual_workers,
        "present_workers": present_workers,
        "attendance_rate": present_workers / actual_workers * 100 if actual_workers else 0,
        "luas_ha": sum_float(row.luas_ha for row in rows),
    }


def akp_dimension(row: DwdAgriAkpDensityDaily, group_by: str) -> str:
    if group_by == "company":
        return "全公司"
    if group_by == "site":
        return row.site or "未填写园区"
    if group_by == "blok":
        return row.blok or "未填写 Blok"
    return row.division or "未填写小区"


def attendance_dimension(row: DwdAgriAttendanceDaily, group_by: str) -> str:
    if group_by == "company":
        return "全公司"
    if group_by == "site":
        return row.site or "未填写园区"
    if group_by == "worker_type":
        return worker_type_label(row.worker_type)
    return row.afdeling or "未填写小区"


def period_key(value: date, period_type: str) -> str:
    normalized = normalize_period(period_type)
    if normalized == "month":
        return value.strftime("%Y-%m")
    if normalized == "week":
        year, week, _ = value.isocalendar()
        return f"{year}-W{week:02d}"
    return value.isoformat()


def normalize_period(period_type: str) -> str:
    return period_type if period_type in {"day", "week", "month"} else "day"


def metric_value(metric: str, totals: dict[str, float]) -> float:
    return totals.get(metric, 0)


def metric_unit(metric: str) -> str:
    return {
        "panen_kg": "kg",
        "jumlah_janjang": "",
        "akp_percent": "%",
        "luas_ha": "ha",
        "attendance_rate": "%",
        "present_workers": "人",
        "actual_workers": "人",
    }.get(metric, "")


def sum_float(values: Iterable[Optional[float]]) -> float:
    return sum(value for value in values if value is not None)


def clean_options(values: Iterable[str]) -> list[str]:
    return [value for value in {item.strip() for item in values if item and item.strip()} if value]


def is_total_label(value: str) -> bool:
    normalized = value.replace(" ", "").upper()
    return normalized.startswith("SUBTOTAL") or normalized.startswith("TOTAL")


def format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def worker_type_label(worker_type: str) -> str:
    return {"harvester": "铲果工", "maintenance": "养护工"}.get(worker_type, worker_type or "未识别")


def query_production_analysis(
    *,
    db: Session,
    metric: str,
    period_type: str,
    group_by: str,
    start_date: Optional[date],
    end_date: Optional[date],
    site: str,
    division: str,
) -> MetricAnalysisResponse:
    statement = select(DwdAgriHarvestDaily).where(DwdAgriHarvestDaily.division == "detail")
    if start_date:
        statement = statement.where(DwdAgriHarvestDaily.report_date >= start_date)
    if end_date:
        statement = statement.where(DwdAgriHarvestDaily.report_date <= end_date)
    if site:
        statement = statement.where(DwdAgriHarvestDaily.site == site)
    if division:
        statement = statement.where(DwdAgriHarvestDaily.division == division)

    records = list(db.scalars(statement).all())
    groups: dict[str, list[DwdAgriHarvestDaily]] = defaultdict(list)
    trends: dict[str, list[DwdAgriHarvestDaily]] = defaultdict(list)
    for record in records:
        groups[production_dimension(record, group_by)].append(record)
        trends[period_key(record.report_date, period_type)].append(record)

    rows = [
        build_production_row(dim, metric, recs)
        for dim, recs in sorted(groups.items(), key=lambda x: x[0])
    ]
    trend_points = [
        MetricTrendPoint(period=period, value=metric_value(metric, build_production_totals(recs)))
        for period, recs in sorted(trends.items(), key=lambda x: x[0])
    ]
    totals = build_production_totals(records)
    return MetricAnalysisResponse(
        subject="production_monitoring",
        metric=metric,
        period_type=normalize_period(period_type),
        group_by=group_by,
        cards=[
            MetricCard(label="当日产量", value=format_number(totals["actual_today_ton"]), unit="吨"),
            MetricCard(label="月累计产量", value=format_number(totals["actual_to_date_ton"]), unit="吨"),
            MetricCard(label="月目标(BBC)", value=format_number(totals["bbc_ton"]), unit="吨"),
            MetricCard(label="日目标", value=format_number(totals["daily_target_ton"]), unit="吨"),
        ],
        trends=trend_points,
        rows=rows,
    )


def production_dimension(row: DwdAgriHarvestDaily, group_by: str) -> str:
    if group_by == "company":
        return "全公司"
    if group_by == "site":
        return row.site or "未填写园区"
    return row.division or "未填写小区"


def build_production_row(dimension: str, metric: str, rows: list[DwdAgriHarvestDaily]) -> MetricAnalysisRow:
    totals = build_production_totals(rows)
    return MetricAnalysisRow(
        dimension=dimension,
        metric_value=metric_value(metric, totals),
        unit=production_metric_unit(metric),
        actual_today_ton=totals["actual_today_ton"],
        actual_to_date_ton=totals["actual_to_date_ton"],
        bbc_ton=totals["bbc_ton"],
        daily_target_ton=totals["daily_target_ton"],
        actual_vs_bbc_percent=totals["actual_vs_bbc_percent"],
    )


def build_production_totals(rows: list[DwdAgriHarvestDaily]) -> dict[str, float]:
    pct_values = [r.actual_vs_bbc_percent for r in rows if r.actual_vs_bbc_percent is not None]
    return {
        "actual_today_ton": sum_float(r.actual_today_ton for r in rows),
        "actual_to_date_ton": sum_float(r.actual_to_date_ton for r in rows),
        "bbc_ton": sum_float(r.bbc_ton for r in rows),
        "daily_target_ton": sum_float(r.daily_target_ton for r in rows),
        "actual_vs_bbc_percent": sum(pct_values) / len(pct_values) if pct_values else 0.0,
    }


def production_metric_unit(metric: str) -> str:
    return {
        "actual_today_ton": "吨",
        "actual_to_date_ton": "吨",
        "bbc_ton": "吨",
        "daily_target_ton": "吨",
        "actual_vs_bbc_percent": "%",
    }.get(metric, "")
