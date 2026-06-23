from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import UploadBatch
from app.schemas import ActionResult, HarvestReportLinks, HarvestReportStatus
from app.services.notifier import push_batch_report
from app.services.report_generator import (
    HARVEST_REPORT_NAME,
    generate_batch_report,
    get_generated_report_image_paths,
    get_generated_report_paths,
    get_generated_report_workbook_paths,
)

router = APIRouter(tags=["reports"])

ELIGIBLE_BATCH_STATUSES = {"parsed", "report_generated", "pushed", "push_skipped"}


@router.get("/reports/harvest/status", response_model=HarvestReportStatus)
def get_harvest_report_status(db: Session = Depends(get_db)) -> HarvestReportStatus:
    batch = find_latest_harvest_batch(db, require_generated=False)
    if not batch:
        return HarvestReportStatus(
            report_name=HARVEST_REPORT_NAME,
            message="暂无可生成产量监控日报的批次。",
        )

    links = build_report_links(batch)
    available = report_files_exist(batch)
    return HarvestReportStatus(
        report_name=HARVEST_REPORT_NAME,
        latest_report_date=batch.report_date,
        latest_batch_no=batch.batch_no,
        latest_batch_status=batch.status,
        available=available,
        links=links if available else HarvestReportLinks(),
        message="最新产量监控日报已生成。" if available else "最新批次尚未生成日报。",
    )


@router.post("/reports/harvest/generate-today", response_model=ActionResult)
def generate_today_harvest_report(db: Session = Depends(get_db)) -> ActionResult:
    batch = find_latest_harvest_batch(db, require_generated=False)
    if not batch:
        raise HTTPException(status_code=404, detail="没有可生成日报的已解析批次。")

    report_path = generate_batch_report(batch, db)
    db.commit()
    return ActionResult(
        batch_no=batch.batch_no,
        status=batch.status,
        message=f"{HARVEST_REPORT_NAME}已生成：{report_path}",
    )


@router.post("/reports/harvest/push-latest", response_model=ActionResult)
def push_latest_harvest_report(db: Session = Depends(get_db)) -> ActionResult:
    batch = find_latest_harvest_batch(db, require_generated=True)
    if not batch:
        raise HTTPException(status_code=404, detail="没有可发送的已生成日报，请先生成日报。")

    message = push_batch_report(batch)
    db.commit()
    return ActionResult(batch_no=batch.batch_no, status=batch.status, message=message)


def find_latest_harvest_batch(db: Session, *, require_generated: bool) -> UploadBatch | None:
    statement = select(UploadBatch).where(UploadBatch.status.in_(ELIGIBLE_BATCH_STATUSES))
    batches = db.scalars(statement.order_by(UploadBatch.report_date.desc(), UploadBatch.created_at.desc())).all()
    if require_generated:
        return next((batch for batch in batches if report_files_exist(batch)), None)
    return batches[0] if batches else None


def report_files_exist(batch: UploadBatch) -> bool:
    paths = [
        *get_generated_report_paths(batch).values(),
        *get_generated_report_workbook_paths(batch).values(),
        *get_generated_report_image_paths(batch).values(),
    ]
    return all(path.exists() for path in paths)


def build_report_links(batch: UploadBatch) -> HarvestReportLinks:
    html_path = next(iter(get_generated_report_paths(batch).values()))
    xlsx_path = next(iter(get_generated_report_workbook_paths(batch).values()))
    png_path = next(iter(get_generated_report_image_paths(batch).values()))
    return HarvestReportLinks(
        html=storage_url(html_path),
        xlsx=storage_url(xlsx_path),
        png=storage_url(png_path),
    )


def storage_url(path: Path) -> str:
    storage_root = Path(settings.storage_dir).resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(storage_root)
    except ValueError:
        return ""
    return "/storage/" + relative.as_posix()
