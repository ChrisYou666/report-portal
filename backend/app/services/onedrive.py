from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from app.core.config import settings

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_SCOPE = "https://graph.microsoft.com/.default"
FALLBACK_SITE = "未填写园区"

_access_token = ""
_access_token_expires_at = 0.0


@dataclass(frozen=True)
class OneDriveUploadResult:
    item_id: str
    web_url: str
    cloud_path: str
    download_url: str = ""


class OneDriveUploadError(RuntimeError):
    pass


def upload_file_to_onedrive(
    *,
    local_path: str,
    filename: str,
    batch_no: str,
    report_date: date,
    site: str,
) -> OneDriveUploadResult:
    if not settings.onedrive_enabled:
        raise OneDriveUploadError("OneDrive 上传未启用")

    validate_settings()

    folder_path = build_folder_path(report_date=report_date, site=site, batch_no=batch_no)
    return upload_file_to_folder(local_path=local_path, filename=filename, folder_path=folder_path)


def upload_file_to_folder(
    *,
    local_path: str,
    filename: str,
    folder_path: str,
) -> OneDriveUploadResult:
    if not settings.onedrive_enabled:
        raise OneDriveUploadError("OneDrive 上传未启用")

    validate_settings()
    ensure_folder_path(folder_path)

    safe_filename = sanitize_path_part(Path(filename).name) or "upload.bin"
    cloud_path = join_graph_path(folder_path, safe_filename)
    upload_path = quote_graph_path(cloud_path)
    url = f"{GRAPH_BASE_URL}/drives/{settings.onedrive_drive_id}/root:/{upload_path}:/content"

    with Path(local_path).open("rb") as file_obj:
        response = request_with_error(
            "PUT",
            url,
            failure_message="上传文件到 OneDrive 失败",
            headers={
                "Authorization": f"Bearer {get_access_token()}",
                "Content-Type": "application/octet-stream",
            },
            data=file_obj,
            timeout=120,
        )

    if response.status_code not in {200, 201}:
        raise OneDriveUploadError(format_graph_error(response, "上传文件到 OneDrive 失败"))

    payload = response.json()
    return OneDriveUploadResult(
        item_id=payload.get("id", ""),
        web_url=payload.get("webUrl", ""),
        cloud_path=cloud_path,
        download_url=payload.get("@microsoft.graph.downloadUrl", ""),
    )


def upload_report_to_onedrive(
    *,
    local_path: str,
    filename: str,
    batch_no: str,
    report_date: date,
    site: str,
    report_name: str,
) -> OneDriveUploadResult:
    folder_path = build_report_folder_path(
        report_date=report_date,
        site=site,
        batch_no=batch_no,
        report_name=report_name,
    )
    return upload_file_to_folder(local_path=local_path, filename=filename, folder_path=folder_path)


def build_folder_path(*, report_date: date, site: str, batch_no: str) -> str:
    site_name = sanitize_path_part(site) or FALLBACK_SITE
    values = {
        "year": f"{report_date.year:04d}",
        "month": f"{report_date.month:02d}",
        "day": f"{report_date.day:02d}",
        "date": report_date.isoformat(),
        "site": site_name,
        "batch_no": sanitize_path_part(batch_no),
    }
    relative_path = settings.onedrive_path_template.format(**values).strip("/")
    return join_graph_path(settings.onedrive_root_folder, relative_path)


def build_report_folder_path(*, report_date: date, site: str, batch_no: str, report_name: str) -> str:
    site_name = sanitize_path_part(site) or FALLBACK_SITE
    values = {
        "year": f"{report_date.year:04d}",
        "month": f"{report_date.month:02d}",
        "day": f"{report_date.day:02d}",
        "date": report_date.isoformat(),
        "site": site_name,
        "batch_no": sanitize_path_part(batch_no),
        "report_name": sanitize_path_part(report_name),
    }
    relative_path = settings.onedrive_report_path_template.format(**values).strip("/")
    return join_graph_path(settings.onedrive_report_root_folder, relative_path)


def ensure_folder_path(folder_path: str) -> None:
    current_path = ""
    for raw_part in split_graph_path(folder_path):
        part = sanitize_path_part(raw_part)
        if not part:
            continue

        current_path = join_graph_path(current_path, part)
        if graph_path_exists(current_path):
            continue

        parent_path = "/".join(split_graph_path(current_path)[:-1])
        create_folder(parent_path=parent_path, folder_name=part)


def graph_path_exists(path: str) -> bool:
    response = request_with_error(
        "GET",
        f"{GRAPH_BASE_URL}/drives/{settings.onedrive_drive_id}/root:/{quote_graph_path(path)}:",
        failure_message=f"检查 OneDrive 路径失败：{path}",
        headers={"Authorization": f"Bearer {get_access_token()}"},
        timeout=30,
    )
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    raise OneDriveUploadError(format_graph_error(response, f"检查 OneDrive 路径失败：{path}"))


def create_folder(*, parent_path: str, folder_name: str) -> None:
    if parent_path:
        url = f"{GRAPH_BASE_URL}/drives/{settings.onedrive_drive_id}/root:/{quote_graph_path(parent_path)}:/children"
    else:
        url = f"{GRAPH_BASE_URL}/drives/{settings.onedrive_drive_id}/root/children"

    response = request_with_error(
        "POST",
        url,
        failure_message=f"创建 OneDrive 文件夹失败：{folder_name}",
        headers={
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        },
        json={
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        },
        timeout=30,
    )
    if response.status_code not in {200, 201, 409}:
        raise OneDriveUploadError(format_graph_error(response, f"创建 OneDrive 文件夹失败：{folder_name}"))


def get_access_token() -> str:
    global _access_token, _access_token_expires_at

    if _access_token and time.time() < _access_token_expires_at - 60:
        return _access_token

    response = request_with_error(
        "POST",
        f"https://login.microsoftonline.com/{settings.onedrive_tenant_id}/oauth2/v2.0/token",
        failure_message="获取 Microsoft Graph token 失败",
        data={
            "client_id": settings.onedrive_client_id,
            "client_secret": settings.onedrive_client_secret,
            "scope": TOKEN_SCOPE,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise OneDriveUploadError(format_graph_error(response, "获取 Microsoft Graph token 失败"))

    payload = response.json()
    _access_token = payload["access_token"]
    _access_token_expires_at = time.time() + int(payload.get("expires_in", 3600))
    return _access_token


def validate_settings() -> None:
    missing_fields = [
        field_name
        for field_name in [
            "onedrive_tenant_id",
            "onedrive_client_id",
            "onedrive_client_secret",
            "onedrive_drive_id",
            "onedrive_root_folder",
        ]
        if not getattr(settings, field_name)
    ]
    if missing_fields:
        raise OneDriveUploadError(f"OneDrive 配置不完整：{', '.join(missing_fields)}")


def request_with_error(
    method: str,
    url: str,
    *,
    failure_message: str,
    **kwargs: Any,
) -> requests.Response:
    try:
        return requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        raise OneDriveUploadError(f"{failure_message}：{exc}") from exc


def join_graph_path(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part and part.strip("/"))


def split_graph_path(path: str) -> list[str]:
    return [part for part in path.strip("/").split("/") if part]


def quote_graph_path(path: str) -> str:
    return quote(path.strip("/"), safe="/")


def sanitize_path_part(value: str) -> str:
    cleaned = value.strip()
    for char in ['"', "*", ":", "<", ">", "?", "\\", "|"]:
        cleaned = cleaned.replace(char, "_")
    return cleaned.strip(". ")


def format_graph_error(response: requests.Response, fallback: str) -> str:
    detail: Any
    try:
        detail = response.json()
    except ValueError:
        detail = response.text

    if isinstance(detail, dict):
        error = detail.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            if message:
                return f"{fallback}。HTTP {response.status_code}: {message}"

    return f"{fallback}。HTTP {response.status_code}: {str(detail)[:300]}"
