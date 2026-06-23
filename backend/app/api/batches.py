from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.core.config import settings
from app.models import ParseJob, UploadBatch
from app.schemas import ActionResult, BatchOut, ParseProgressOut
from app.services.parser import parse_batch

router = APIRouter(tags=["batches"])


@router.get("/batches", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db)) -> list[UploadBatch]:
    return list(db.scalars(select(UploadBatch).order_by(UploadBatch.created_at.desc())).all())


@router.get("/batches/{batch_no}", response_model=BatchOut)
def get_batch(batch_no: str, db: Session = Depends(get_db)) -> UploadBatch:
    return find_batch(db, batch_no)


@router.post("/batches/{batch_no}/parse", response_model=ActionResult)
def parse(
    batch_no: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ActionResult:
    batch = find_batch(db, batch_no)
    job = get_or_create_parse_job(db, batch)
    if job.status in {"queued", "running"}:
        return ActionResult(batch_no=batch.batch_no, status=job.status, message="该批次正在解析中。")

    reset_parse_job(job, batch)
    batch.status = "parsing"
    db.commit()
    background_tasks.add_task(run_parse_job, batch.batch_no)
    return ActionResult(batch_no=batch.batch_no, status=job.status, message="已启动后台解析。")


@router.get("/batches/{batch_no}/parse-progress", response_model=ParseProgressOut)
def get_parse_progress(batch_no: str, db: Session = Depends(get_db)) -> ParseJob:
    job = db.scalar(select(ParseJob).where(ParseJob.batch_no == batch_no))
    if not job:
        raise HTTPException(status_code=404, detail="该批次还没有解析进度。")
    return job



def find_batch(db: Session, batch_no: str) -> UploadBatch:
    batch = db.scalar(select(UploadBatch).where(UploadBatch.batch_no == batch_no))
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在。")
    return batch


def get_or_create_parse_job(db: Session, batch: UploadBatch) -> ParseJob:
    job = db.scalar(select(ParseJob).where(ParseJob.batch_no == batch.batch_no))
    if job:
        return job

    job = ParseJob(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        status="not_started",
        total_files=len(batch.files),
    )
    db.add(job)
    db.flush()
    return job


def reset_parse_job(job: ParseJob, batch: UploadBatch) -> None:
    now = datetime.utcnow()
    job.status = "queued"
    job.total_files = len(batch.files)
    job.processed_files = 0
    job.parsed_files = 0
    job.skipped_files = 0
    job.failed_files = 0
    job.current_filename = ""
    job.message = "等待后台解析。"
    job.error_message = ""
    job.started_at = None
    job.finished_at = None
    job.updated_at = now


def run_parse_job(batch_no: str) -> None:
    db = SessionLocal()
    try:
        batch = find_batch(db, batch_no)
        job = get_or_create_parse_job(db, batch)
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        job.message = "后台解析已开始。"
        batch.status = "parsing"
        db.commit()

        def update_progress(progress: dict) -> None:
            job.status = progress.get("status", job.status)
            job.total_files = progress.get("total_files", job.total_files)
            job.processed_files = progress.get("processed_files", job.processed_files)
            job.parsed_files = progress.get("parsed_files", job.parsed_files)
            job.skipped_files = progress.get("skipped_files", job.skipped_files)
            job.failed_files = progress.get("failed_files", job.failed_files)
            job.current_filename = progress.get("current_filename", job.current_filename)
            job.message = progress.get("message", job.message)
            job.updated_at = datetime.utcnow()
            db.commit()

        message = parse_batch(batch, db, progress_callback=update_progress)
        job.status = batch.status
        job.message = message
        job.current_filename = ""
        job.finished_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.scalar(select(ParseJob).where(ParseJob.batch_no == batch_no))
        batch = db.scalar(select(UploadBatch).where(UploadBatch.batch_no == batch_no))
        if job:
            job.status = "parse_failed"
            job.error_message = str(exc)
            job.message = "后台解析失败。"
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
        if batch:
            batch.status = "parse_failed"
        db.commit()
    finally:
        db.close()
