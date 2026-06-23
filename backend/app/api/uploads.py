from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import ParseJob, UploadBatch, UploadFileRecord
from app.schemas import BatchOut, UploadOptions
from app.services.onedrive import OneDriveUploadError, upload_file_to_onedrive
from app.services.storage import (
    ALLOWED_EXTENSIONS,
    allowed_file_type,
    detect_report_name,
    file_extension,
    generate_batch_no,
    save_upload_file,
)

router = APIRouter(tags=["uploads"])

REPORT_TYPES = ["日报", "周报", "月报"]
AUTHORIZED_UPLOADERS = ["王浩源", "张杰铭", "王云豪"]
DEPARTMENTS = ["农业", "工业"]
SITES = ["七园", "八园"]


@router.get("/upload-options", response_model=UploadOptions)
def get_upload_options() -> UploadOptions:
    return UploadOptions(
        report_types=REPORT_TYPES,
        uploaders=AUTHORIZED_UPLOADERS,
        allowed_extensions=sorted(ALLOWED_EXTENSIONS),
        departments=DEPARTMENTS,
        sites=SITES,
    )


@router.post("/uploads", response_model=BatchOut)
async def upload_reports(
    background_tasks: BackgroundTasks,
    report_name: str = Form(...),
    report_type: str = Form(...),
    department: str = Form(...),
    site: str = Form(""),
    factory: str = Form(""),
    report_date: date = Form(...),
    uploader: str = Form(...),
    remark: str = Form(""),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> UploadBatch:
    if not files:
        raise HTTPException(status_code=400, detail="至少需要上传一个文件")

    if report_type not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的报表类型：{report_type}")

    if uploader not in AUTHORIZED_UPLOADERS:
        raise HTTPException(status_code=403, detail=f"上传人无权限：{uploader}")

    if department not in DEPARTMENTS:
        raise HTTPException(status_code=400, detail=f"不支持的部门：{department}")

    if site and site not in SITES:
        raise HTTPException(status_code=400, detail=f"不支持的园区：{site}")

    invalid_file = next((file for file in files if not allowed_file_type(file.filename or "")), None)
    if invalid_file:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{invalid_file.filename}")

    batch = UploadBatch(
        batch_no=generate_batch_no(),
        report_name=report_name,
        report_type=report_type,
        department=department,
        site=site,
        factory=factory,
        report_date=report_date,
        uploader=uploader,
        remark=remark,
        status="uploaded",
    )
    db.add(batch)
    db.flush()

    batch_cloud_upload_failed = False
    for file in files:
        local_path, file_size = await save_upload_file(file, batch.batch_no)
        filename = file.filename or "upload.bin"
        stored_path = local_path
        file_status = "uploaded"

        if settings.onedrive_enabled:
            try:
                upload_result = upload_file_to_onedrive(
                    local_path=local_path,
                    filename=filename,
                    batch_no=batch.batch_no,
                    report_date=report_date,
                    site=site,
                )
                stored_path = upload_result.web_url or upload_result.cloud_path
                file_status = "cloud_uploaded"
            except OneDriveUploadError:
                batch_cloud_upload_failed = True
                file_status = "cloud_upload_failed"

        db.add(
            UploadFileRecord(
                batch_id=batch.id,
                original_filename=filename,
                stored_path=stored_path,
                file_size=file_size,
                file_type=file_extension(filename),
                detected_report_name=detect_report_name(filename) or report_name,
                status=file_status,
            )
        )

    db.commit()

    # 上传完成后立即启动后台 AI 解析，无论云端上传是否成功（本地文件始终可用）
    from app.api.batches import run_parse_job  # 延迟导入避免循环引用

    batch.status = "parsing"
    parse_job = ParseJob(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        status="queued",
        total_files=len(batch.files),
        message="上传完成，等待后台 AI 解析。",
    )
    db.add(parse_job)
    db.commit()
    background_tasks.add_task(run_parse_job, batch.batch_no)

    db.refresh(batch)
    return batch
