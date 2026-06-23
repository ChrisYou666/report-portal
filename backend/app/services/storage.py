from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings


ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv", "pdf", "doc", "docx", "png", "jpg", "jpeg"}


def generate_batch_no() -> str:
    return f"B{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid4().hex[:4].upper()}"


def file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def allowed_file_type(filename: str) -> bool:
    return file_extension(filename) in ALLOWED_EXTENSIONS


def detect_report_name(filename: str) -> str:
    stem = Path(filename).stem
    for token in ["_", "-"]:
        stem = stem.replace(token, " ")
    parts = [part for part in stem.split() if not part.isdigit()]
    return " ".join(parts).strip()


async def save_upload_file(file: UploadFile, batch_no: str) -> tuple[str, int]:
    storage_root = Path(settings.storage_dir) / "originals" / batch_no
    storage_root.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "upload.bin").name
    target = storage_root / safe_name

    size = 0
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            output.write(chunk)

    return str(target), size
