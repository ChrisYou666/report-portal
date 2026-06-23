from __future__ import annotations

import shutil
import sys
import os
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from app.core.config import settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import (  # noqa: E402
    DwdAkpDensityDaily,
    DwdHarvesterAttendanceDaily,
    ParseJob,
    ParsedDocument,
    ParsedField,
    ParsedStructuredRecord,
    UploadBatch,
    UploadFileRecord,
)
from app.services.onedrive import GRAPH_BASE_URL, get_access_token, quote_graph_path  # noqa: E402


def main() -> None:
    init_db()
    sharepoint_results = clear_sharepoint_history()
    db_results = clear_database_history()
    local_results = clear_local_history()

    print("SHAREPOINT")
    for line in sharepoint_results:
        print(f"- {line}")
    print("DATABASE")
    for line in db_results:
        print(f"- {line}")
    print("LOCAL")
    for line in local_results:
        print(f"- {line}")


def clear_sharepoint_history() -> list[str]:
    if not settings.onedrive_enabled:
        return ["OneDrive/SharePoint disabled; skipped."]

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    results: list[str] = []
    for folder in [settings.onedrive_root_folder, settings.onedrive_report_root_folder]:
        folder = folder.strip("/")
        if not folder:
            continue
        item = get_drive_item_by_path(folder, headers)
        if not item:
            results.append(f"{folder}: not found.")
            continue
        response = requests.delete(
            f"{GRAPH_BASE_URL}/drives/{settings.onedrive_drive_id}/items/{item['id']}",
            headers=headers,
            timeout=60,
        )
        if response.status_code not in {200, 202, 204}:
            raise RuntimeError(f"Failed to delete SharePoint folder {folder}: HTTP {response.status_code} {response.text[:300]}")
        results.append(f"{folder}: deleted.")
    return results


def get_drive_item_by_path(path: str, headers: dict[str, str]) -> dict | None:
    response = requests.get(
        f"{GRAPH_BASE_URL}/drives/{settings.onedrive_drive_id}/root:/{quote_graph_path(path)}:",
        headers=headers,
        timeout=60,
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"Failed to inspect SharePoint path {path}: HTTP {response.status_code} {response.text[:300]}")
    return response.json()


def clear_database_history() -> list[str]:
    delete_order = [
        ParseJob,
        DwdAkpDensityDaily,
        DwdHarvesterAttendanceDaily,
        ParsedField,
        ParsedStructuredRecord,
        ParsedDocument,
        UploadFileRecord,
        UploadBatch,
    ]
    db = SessionLocal()
    try:
        results: list[str] = []
        for model in delete_order:
            count = db.query(model).delete(synchronize_session=False)
            results.append(f"{model.__tablename__}: deleted {count}")
        db.commit()
        return results
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def clear_local_history() -> list[str]:
    results: list[str] = []
    for relative_path in ["originals", "reports"]:
        storage_root = Path(settings.storage_dir)
        if not storage_root.is_absolute():
            storage_root = BACKEND_ROOT / storage_root
        path = storage_root / relative_path
        if path.exists():
            shutil.rmtree(path)
            results.append(f"{path}: deleted.")
        path.mkdir(parents=True, exist_ok=True)
        results.append(f"{path}: recreated.")
    return results


if __name__ == "__main__":
    main()
